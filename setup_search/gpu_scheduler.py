#!/usr/bin/env python3
"""Autonomous GPU scheduler — keeps idle GPUs productively busy.

The rule-primary trader doesn't call the LLM, so GPU0/GPU1 sit idle. This
scheduler watches GPU utilization; when both are idle for a sustained window,
it runs the next pending task from the manifest (sentiment holdout -> value
head push -> Ptolemy retrain) to completion, logs + checkpoints, and moves on.

Runs forever. Launch via systemd (opentrader-gpu-scheduler.service).
"""

import json
import logging
import os
import subprocess
import time
from pathlib import Path

PROJECT = Path(__file__).resolve().parent.parent
OUT = PROJECT / "data" / "gpu_scheduler"
MANIFEST = Path(__file__).resolve().parent / "auto_tasks.json"
IDLE_THRESHOLD = 30.0   # % GPU util below this = mostly idle (harness still scouts/coaches)
IDLE_CYCLES = 30        # ~5 min of mostly-idle before running the next task
POLL_SEC = 10

OUT.mkdir(parents=True, exist_ok=True)

logging.basicConfig(level=logging.INFO,
                    format="%(asctime)s [scheduler] %(levelname)s %(message)s",
                    handlers=[logging.FileHandler(OUT / "scheduler.log"),
                              logging.StreamHandler()])
log = logging.getLogger("gpu_scheduler")


def gpu_util() -> float:
    """Max GPU utilization across NVIDIA + AMD."""
    util = []
    try:
        out = subprocess.run(["nvidia-smi", "--query-gpu=utilization.gpu",
                              "--format=csv,noheader,nounits"],
                             capture_output=True, text=True, timeout=10)
        util += [float(x.strip()) for x in out.stdout.strip().splitlines() if x.strip().isdigit()]
    except Exception:
        pass
    try:
        out = subprocess.run(["rocm-smi", "--showuse"], capture_output=True, text=True, timeout=10)
        for line in out.stdout.splitlines():
            if "%" in line:
                try:
                    util.append(float(line.split(":")[-1].replace("%", "").strip()))
                except Exception:
                    pass
    except Exception:
        pass
    return max(util) if util else 0.0


def load_manifest():
    return json.loads(MANIFEST.read_text())["tasks"]


def save_manifest(tasks):
    MANIFEST.write_text(json.dumps({"tasks": tasks}, indent=1))


def run_task(task):
    log.info(f"RUN task: {task['name']} ({task['cmd']})")
    task["status"] = "running"
    save_manifest(load_manifest())
    try:
        result = subprocess.run(task["cmd"], shell=True, cwd=str(PROJECT),
                                capture_output=True, text=True, timeout=task.get("timeout", 3600))
        task["status"] = "done" if result.returncode == 0 else "failed"
        task["exit"] = result.returncode
        log.info(f"DONE task {task['name']}: rc={result.returncode}")
        if result.stdout:
            log.info(f"  stdout tail: {result.stdout[-800:]}")
        if result.stderr:
            log.info(f"  stderr tail: {result.stderr[-400:]}")
    except subprocess.TimeoutExpired:
        task["status"] = "timed_out"
        log.warning(f"TIMEOUT task {task['name']}")
    task["last_run"] = time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())
    save_manifest(load_manifest())


def main():
    OUT.mkdir(parents=True, exist_ok=True)
    idle_count = 0
    log.info("GPU scheduler started (rule-primary trader -> idle GPUs run research/training)")
    while True:
        try:
            util = gpu_util()
            if util < IDLE_THRESHOLD:
                idle_count += 1
            else:
                idle_count = 0
            if idle_count >= IDLE_CYCLES:
                tasks = load_manifest()
                pending = [t for t in tasks if t.get("status") in ("pending", "failed", "never_run", None)]
                if pending:
                    run_task(pending[0])
                else:
                    log.info("All tasks complete; waiting for new work")
                idle_count = 0
        except Exception as e:
            log.error(f"scheduler error: {e}")
        time.sleep(POLL_SEC)


if __name__ == "__main__":
    main()
