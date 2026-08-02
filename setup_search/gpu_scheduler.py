#!/usr/bin/env python3
"""Autonomous GPU scheduler v2 — request-activity gating (wayfinder #43).

Research found the util-based gate could never fire (GPU1 is ~100% duty-cycled
by the harness's scout/coach). v2 gates on REQUEST ACTIVITY from the journal:

- GPU0 tasks (sentiment FinBERT): safe when no `slot launch` in 5 min
  (rule-primary never calls qwen). During a run, a launch pauses the task
  (SIGSTOP) and resumes it after 60s quiet — the gpu_sync proxy could shift
  traffic there.
- GPU1 tasks (Ptolemy retrain): coexistence — run only in 60s-quiet windows,
  pause on any new launch, resume after 60s quiet.
- CPU tasks (value-head): always run.

Retry policy: 2 retries then `failed`. `--dry-run` validates the signals
without running tasks (the scheduler's own process-verification step).
"""

import argparse
import json
import logging
import signal
import subprocess
import time
from pathlib import Path

PROJECT = Path(__file__).resolve().parent.parent
OUT = PROJECT / "data" / "gpu_scheduler"
MANIFEST = Path(__file__).resolve().parent / "auto_tasks.json"
POLL_SEC = 15
GPU0_SERVICE = "opentrader-llama-gpu0.service"  # qwen (NVIDIA)
GPU1_SERVICE = "opentrader-llama-gpu1.service"  # qwythos (AMD)

OUT.mkdir(parents=True, exist_ok=True)
logging.basicConfig(level=logging.INFO,
                    format="%(asctime)s [scheduler] %(levelname)s %(message)s",
                    handlers=[logging.FileHandler(OUT / "scheduler.log"),
                              logging.StreamHandler()])
log = logging.getLogger("gpu_scheduler")


def launches_in(service: str, minutes: float) -> int:
    """Count llama-server `slot launch` events in the journal over the window."""
    try:
        r = subprocess.run(
            ["journalctl", "--user", "-u", service, "--since",
             f"{int(minutes)} min ago", "--no-pager"],
            capture_output=True, text=True, timeout=20,
        )
        return r.stdout.count("slot launch")
    except Exception:
        return 0


def gpu0_safe() -> bool:
    return launches_in(GPU0_SERVICE, 5) == 0


def gpu1_quiet() -> bool:
    return launches_in(GPU1_SERVICE, 1) == 0


def load_manifest():
    return json.loads(MANIFEST.read_text())["tasks"]


def save_manifest(tasks):
    MANIFEST.write_text(json.dumps({"tasks": tasks}, indent=1))


def task_safe(task) -> str:
    """Return '' if safe to run, else the reason it's gated."""
    gpu = task.get("gpu", "cpu")
    if gpu == "gpu0":
        return "" if gpu0_safe() else "GPU0 active (launch within 5 min)"
    if gpu == "gpu1":
        return "" if gpu1_quiet() else "GPU1 busy (launch within 60s)"
    return ""


def run_task(task, dry_run=False) -> str:
    """Run a task, pausing on GPU contention; returns status."""
    gpu = task.get("gpu", "cpu")
    if dry_run:
        return "dry-run-ok"
    proc = subprocess.Popen(task["cmd"], shell=True, cwd=str(PROJECT),
                            stdout=open(OUT / f"{task['name']}.out", "w"),
                            stderr=subprocess.STDOUT)
    paused = False
    start = time.time()
    while proc.poll() is None:
        time.sleep(POLL_SEC)
        if gpu == "gpu0":
            if launches_in(GPU0_SERVICE, 5) > 0 and not paused:
                proc.send_signal(signal.SIGSTOP)
                paused = True
                log.info(f"  {task['name']}: GPU0 active -> paused")
            elif paused and gpu0_safe():
                proc.send_signal(signal.SIGCONT)
                paused = False
                log.info(f"  {task['name']}: GPU0 quiet -> resumed")
        elif gpu == "gpu1":
            if not gpu1_quiet() and not paused:
                proc.send_signal(signal.SIGSTOP)
                paused = True
                log.info(f"  {task['name']}: GPU1 busy -> paused")
            elif paused and gpu1_quiet():
                proc.send_signal(signal.SIGCONT)
                paused = False
                log.info(f"  {task['name']}: GPU1 quiet -> resumed")
        if time.time() - start > task.get("timeout", 3600):
            proc.kill()
            return "timed_out"
    rc = proc.returncode
    if paused:
        try:
            proc.send_signal(signal.SIGCONT)
        except Exception:
            pass
    return "done" if rc == 0 else "failed"


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--dry-run", action="store_true",
                    help="Validate signals + report what would run, run nothing")
    ap.add_argument("--once", action="store_true", help="Run one task then exit")
    args = ap.parse_args()

    if args.dry_run:
        print(f"GPU0 launches(5min)={launches_in(GPU0_SERVICE, 5)} "
              f"-> safe={gpu0_safe()}")
        print(f"GPU1 launches(1min)={launches_in(GPU1_SERVICE, 1)} "
              f"-> quiet={gpu1_quiet()}")
        for t in load_manifest():
            print(f"  {t['name']} (gpu={t.get('gpu')}): "
                  f"{task_safe(t) or 'would run'}")
        return

    log.info("GPU scheduler v2 started (request-activity gating)")
    while True:
        try:
            tasks = load_manifest()
            ran = False
            for t in tasks:
                if t.get("status") not in ("pending", "failed"):
                    continue
                if t.get("retries", 0) >= 2:
                    continue
                why = task_safe(t)
                if why:
                    log.debug(f"gated: {t['name']} ({why})")
                    continue
                log.info(f"RUN {t['name']} (gpu={t.get('gpu')})")
                t["status"] = "running"
                save_manifest(tasks)
                status = run_task(t)
                t["status"] = status
                if status == "failed":
                    t["retries"] = t.get("retries", 0) + 1
                    t["status"] = "failed" if t["retries"] >= 2 else "pending"
                t["last_run"] = time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())
                save_manifest(tasks)
                log.info(f"DONE {t['name']}: {status} (retries={t.get('retries', 0)})")
                ran = True
                if args.once:
                    return
                break  # one task per pass; loop re-gates on the next
            if not ran:
                time.sleep(POLL_SEC)
        except Exception as e:
            log.error(f"scheduler error: {e}")
            time.sleep(POLL_SEC)


if __name__ == "__main__":
    main()
