# Research: Eval gate health and what it evaluates

**Ticket:** Eval gate health and what it evaluates
**Date:** 2026-07-31
**Method:** Trace of `training/eval_gate.sh`, `training/eval_deploy.py`, `training/deep_eval.py`, `training/programmatic_teacher.py`, `training/ops_watchdog.py`, crontab, `data/pipeline_eval.log`, `data/eval/reports/`, `data/adapter_registry.json`.

## Finding 1 — The eval gate is deadlocked by design and has not run since ~Jul 15

Cron line:

```
*/30 * * * * flock -n /tmp/opentrader_eval_gate.lock bash .../training/eval_gate.sh >> .../pipeline_eval.log
```

The script itself also acquires the same lock:

```bash
exec 9>"$LOCKFILE"          # /tmp/opentrader_eval_gate.lock
if ! flock -n 9; then
    echo "[eval] Locked — another eval_gate is running. Exiting."
    exit 0
fi
```

Because cron's `flock -n` holds the lock for the *entire* script run, the script's inner `flock -n 9` always fails with EWOULDBLOCK. Every 30-minute invocation exits immediately at "Locked". The gate has been a no-op since the double-lock was introduced.

Evidence:
- `data/pipeline_eval.log` tail: 20+ consecutive `[eval] Locked — another eval_gate is running. Exiting.` lines, no other output.
- `data/eval/reports/` shows the last deep reports are `Ptolemy-S1_deep_20260715_180359.json` and `Ptolemy-S2_deep_20260715_203200.json` (Jul 15) — the gate worked before the double-lock existed.

## Finding 2 — `eval_lock: held_no_holder` is a symptom of the deadlock

`ops_watchdog.py:check_lock()` finds the lock file exists but no process holds it (`fuser` empty). Since the file is touched by every cron attempt, it stays "fresh" (<2h) → reported as `held_no_holder`. After 2h it would be cleared as `stale_cleared` — but the cron keeps touching it, so it flips between `held_no_holder`/`stale_cleared` forever. Not a separate bug; the same root cause.

## Finding 3 — What the gate would evaluate (if it could run)

`training/eval_deploy.py:evaluate_candidate()`:
- Reads candidates from `data/adapter_registry.json` (versions not `active` with status in `completed/pending/rolled_back/superseded` and no `_deep_` report).
- Spawns a dedicated `llama-server` on `:5805` (AMD ROCm build) with the candidate's base GGUF + LoRA (skips LoRA if missing).
- Runs `training.deep_eval.DeepEval.run()` — 7 dimensions:

| Dim | Weight | What it measures | Source of scenarios |
|---|---|---|---|
| signal_accuracy | 0.25 | model's signal vs teacher ground truth | `ProgrammaticTeacher.generate_batch(200)` |
| reasoning_coherence | 0.15 | coherence of reasoning | teacher scenarios |
| confidence_calibration | 0.15 | ECE of confidence vs accuracy | teacher scenarios |
| adversarial_robustness | 0.10 | signal flips under adversarial perturbation | teacher (50) |
| debate_quality | 0.10 | Bull↔BUY / Bear↔SELL alignment | teacher (30) |
| edge_detection | 0.10 | detection of trend/breakout edges | teacher (100) |
| temporal_consistency | 0.15 | consistency across time | teacher (30) |

Scenarios come from `training/programmatic_teacher.py` — a **deterministic synthetic scenario generator** (`PROGRAMMATIC_PATTERNS`: breakout_entry, false_breakout, trend_following, mean_reversion, flash_crash, range_accumulation; seeded `random`). Prices are *simulated*, not real market data.

Promotion rule (`eval_deploy.py`): promote candidate if `deep_eval weighted_score >= active score + 3.0`.

## Finding 4 — Trustworthiness

- The 84% dashboard return (fabricated synthetic paper PnL) is **irrelevant** to DeepEval scores: the gate evaluates models on programmatic scenarios, not the paper-trading record. Two separate pipelines.
- However: the gate does NOT evaluate the model against real trading outcomes either — signal_accuracy's ground truth is the programmatic teacher, not realized market movement. The Ptolemy "S" generations are fine-tuned on trading data, but their promotion score never sees the trading record.
- So "evaluate the model's performance" currently means "score against synthetic scenarios" — neither the (fake) paper returns nor (missing) real-price trades inform the gate.

## Finding 5 — Live conflict with ops_watchdog SIGCONT

`eval_gate.sh` SIGSTOPs the harness to free VRAM, and `ops_watchdog.py:check_harness()` explicitly detects SIGSTOP'd harness and sends SIGCONT every 5 min. If the gate ran, the watchdog would resume the harness mid-eval, competing for VRAM with the eval llama-server on :5805. The trap in eval_gate.sh (`EXIT → SIGCONT`) partially covers crash cases, but the 5-min watchdog makes the stop/resume protocol racy.

Also note: `eval_gate.sh` expects `/home/mrc/src/modelai-llama.cpp/build-wmma/bin/llama-server` — the same ROCm build the harness's ADIR agents (via llama-swap wrappers) use.

## Recommended next step for the ticket

The fix is small and mechanical: drop one of the two `flock` layers (keep cron's outer lock, remove the script's inner `flock -n 9`, or vice versa), then re-run once and verify a deep report is produced. The deeper question (should the gate score real trading outcomes too) belongs to the map's trustworthy-numbers discussion.
