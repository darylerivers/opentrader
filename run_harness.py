#!/usr/bin/env python3
"""Auto-restart harness on source file changes using watchfiles.

Clears __pycache__ on each restart to prevent stale bytecode bugs.
"""

import subprocess, sys, os, signal, time, argparse, shutil, threading, queue
from pathlib import Path

HARNESS_DIR = Path(__file__).resolve().parent

WATCH_PATHS = [
    str(HARNESS_DIR / "harness.py"),
    str(HARNESS_DIR / "risk"),
    str(HARNESS_DIR / "mot"),
    str(HARNESS_DIR / "state"),
    str(HARNESS_DIR / "exchange"),
    str(HARNESS_DIR / "data"),
    str(HARNESS_DIR / "training"),
    str(HARNESS_DIR / "agent"),
    str(HARNESS_DIR / "tools"),
]

EXCLUDED = {
    "__pycache__",
    ".pyc",
    ".git",
    ".venv",
    "rocm_venv",
    "history",
    "training/checkpoints",
}


def clear_pycache(root: Path = None) -> tuple[int, int]:
    """Remove all __pycache__ directories and .pyc files under root."""
    root = root or HARNESS_DIR
    dirs = files = 0
    for pyc_dir in root.rglob("__pycache__"):
        try:
            shutil.rmtree(pyc_dir, ignore_errors=True)
            dirs += 1
        except Exception:
            pass
    for pyc_file in root.rglob("*.pyc"):
        try:
            pyc_file.unlink(missing_ok=True)
            files += 1
        except Exception:
            pass
    return dirs, files


def main():
    parser = argparse.ArgumentParser(description="Auto-restarting harness launcher")
    parser.add_argument(
        "--cooldown", type=int, default=2, help="Debounce seconds after change"
    )
    parser.add_argument(
        "--no-reload", action="store_true", help="Run once, do not watch for changes"
    )
    # ── New: wall-clock timeout ────────────────────────────────────
    parser.add_argument(
        "--max-hours",
        type=int,
        default=0,
        help="Max hours before auto-terminate (0=unlimited)",
    )
    args, unknown = parser.parse_known_args()

    harness_args = (
        unknown
        if unknown
        else [
            "--exchange",
            "finnhub",
            "--no-synthetic",
            "--stage",
            "2",
            "--cash",
            "500",
            "--max-cycles",
            "0",
            "--mot-force",
            "increase",
            "--max-daily-trades",
            "500",
            "--debate-mode",
            "adir",
            "--llama-host",
            "http://127.0.0.1:5801",
            "--parallel-debate",
            "--interval",
            "10",
        ]
    )

    cmd = [sys.executable, str(HARNESS_DIR / "harness.py")] + harness_args

    # ── One-shot mode ──────────────────────────────────────────
    if args.no_reload:
        d, f = clear_pycache()
        print(f"Cleared {d} __pycache__ dirs, {f} .pyc files")
        os.execv(sys.executable, [sys.executable] + cmd[1:])

    # ── Watch mode ─────────────────────────────────────────────
    try:
        from watchfiles import watch
    except ImportError:
        print("watchfiles not installed. Install with: pip install watchfiles")
        print("Running without auto-reload...")
        os.execv(sys.executable, [sys.executable] + cmd[1:])

    proc = None
    last_restart = 0.0
    start_time = time.time()

    def kill_harness():
        nonlocal proc
        if proc and proc.poll() is None:
            proc.send_signal(signal.SIGTERM)
            try:
                proc.wait(timeout=10)
            except subprocess.TimeoutExpired:
                proc.kill()
                proc.wait()

    def start_harness():
        nonlocal proc
        dirs, files = clear_pycache()
        if dirs or files:
            print(f"  🧹 Cleared {dirs} __pycache__ dirs, {files} .pyc files")
        print(f"\n{'=' * 50}")
        print(f"🚀 Starting: {' '.join(cmd)}")
        print(f"{'=' * 50}\n")
        os.environ["WATCHFILES_RUNNING"] = "1"
        proc = subprocess.Popen(cmd, env=os.environ)

    max_seconds = args.max_hours * 3600 if args.max_hours > 0 else 0
    if max_seconds > 0:
        print(f"⏱  Wall-clock timeout: {args.max_hours}h ({max_seconds}s)")
    print(f"👁  Watching for .py changes (cooldown={args.cooldown}s)")
    if max_seconds > 0:
        print(f"   ⏱  Max run time: {args.max_hours}h")
    print()

    start_harness()
    last_restart = time.time()

    # ── File-watcher thread + main poll loop ──────────────────
    change_queue: queue.Queue = queue.Queue()
    stop_event = threading.Event()

    def _watcher():
        """Run watchfiles in a daemon thread, push changes to queue."""
        try:
            for changes in watch(
                *WATCH_PATHS, debounce=args.cooldown * 1000, stop_event=stop_event
            ):
                if stop_event.is_set():
                    break
                py_changes = []
                for _, path_str in changes:
                    if not path_str.endswith(".py"):
                        continue
                    path_lower = path_str.lower()
                    if any(ex in path_lower for ex in EXCLUDED):
                        continue
                    py_changes.append(path_str)
                if py_changes:
                    change_queue.put(py_changes)
        except Exception as e:
            print(f"  ⚠️  Watcher thread error: {e}")

    watcher_thread = threading.Thread(target=_watcher, daemon=True)
    watcher_thread.start()

    crash_count = 0
    MAX_CRASH_RESTARTS = 20  # safety valve

    try:
        while not stop_event.is_set():
            now = time.time()

            # ── Wall-clock timeout ──
            if max_seconds > 0 and (now - start_time) >= max_seconds:
                print(
                    f"\n⏱  Wall-clock timeout reached ({args.max_hours}h). Shutting down."
                )
                stop_event.set()
                break

            # ── Crash detection: restart dead process ──
            if proc and proc.poll() is not None:
                exit_code = proc.returncode
                crash_count += 1
                if crash_count > MAX_CRASH_RESTARTS:
                    print(f"\n❌ {MAX_CRASH_RESTARTS} consecutive crashes — giving up.")
                    stop_event.set()
                    break
                print(
                    f"\n💥 Harness exited (code={exit_code}, crash #{crash_count}). "
                    f"Restarting in {args.cooldown}s..."
                )
                time.sleep(args.cooldown)
                start_harness()
                last_restart = time.time()

            # ── File-change restart (with debounce) ──
            try:
                py_changes = change_queue.get(timeout=1.0)
            except queue.Empty:
                continue  # nothing happened, loop back

            if now - last_restart < args.cooldown + 3:
                continue  # debounce

            rel_paths = [os.path.relpath(p, str(HARNESS_DIR)) for p in py_changes[:5]]
            print(f"\n🔄 {len(py_changes)} file(s) changed: {', '.join(rel_paths)}")
            print(f"  ⏳ Debouncing {args.cooldown}s...")
            time.sleep(args.cooldown)

            now = time.time()
            if max_seconds > 0 and (now - start_time) >= max_seconds:
                print(
                    f"\n⏱  Wall-clock timeout reached ({args.max_hours}h). Shutting down."
                )
                stop_event.set()
                break

            print(f"  🔄 Restarting...")
            kill_harness()
            time.sleep(1)
            start_harness()
            last_restart = time.time()
            crash_count = 0  # reset on successful file-change restart

    except KeyboardInterrupt:
        print("\n👋 Shutting down...")
        stop_event.set()

    finally:
        stop_event.set()
        kill_harness()
        watcher_thread.join(timeout=5)


if __name__ == "__main__":
    main()
