# Overnight Monitor Summary — curriculum-5h

- **Date (UTC):** 2026-08-04, 08:31 → 11:20
- **Monitor start:** 2026-08-04 ~08:40 UTC (first heartbeat c1)
- **Monitor end:** 2026-08-04 11:20 UTC (loop completed)

## Cycles Run
16 heartbeat cycles (~10 min cadence), ending early because the run completed at cycle 16.

## Restarts
**0 restarts.** The loop `curriculum-5h` (pid 871747, `python3 -m arena.loop --iterations 30 --arch-every 2 --distill-every 3`) ran continuously from spawn to `[loop] done`.

## Anomalies Observed
- None requiring intervention.
- GPU0 idle periods (0% util) were verified in each case to occur with **no** `train_momentum_agent` process alive and the loop healthy — classified as normal CPU phases (architect reviews / curriculum gate evaluations). Noted at cycles c2, c7, c12.
- GPU1 (AMD, rocm-smi) sat at ~0–1% the entire run — expected, AMD is only used between Architect reviews. Not treated as an anomaly.
- Several `architect verdict: FAIL` entries appeared (e.g., "not a dict", "duplicate id") — normal candidate-generation churn, loop continued.

## Final Curriculum State
- **Mastered:** 13/15 (s01–s09, s11–s14; remedial: s10-hype-fade-duel, s15-mot-weight)
- **Graduate flag:** `False`

## Final Gate Margins (data/arena/arena_state.json)
- Window `0-500`:   margin **0.010117** (kept_mean 0.013339 vs all_mean 0.003222)
- Window `1000-1250`: margin **0.015543** (kept_mean 0.025040 vs all_mean 0.009497)
- **Gate pass:** `True` (iteration 65, val_mse 0.8937)

## Total Wall Time
~2 h 49 m (loop spawned 08:31:53 UTC → completed 11:20:53 UTC). Loop exited cleanly with `[loop] distill done` → `[loop] done`.
