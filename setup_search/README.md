# OpenTrader — GPU1 Setup-Search Loop ("wayfinder")

Dedicated overnight run: GPU1 (qwythos-9b-mtp @ :5802) spends its whole
compute budget searching for the best trading setup. A model-in-the-loop
optimizer: the LLM reviews backtest feedback and proposes the next candidate
configs; a fast, cost-aware backtest scores each one.

## Why this shape
Leading quant research shows LLMs add the most value as *research/setup
scientists* that propose and critique strategies behind a statistical gate —
not as raw signal generators feeding live orders (that is what produced the
fee-bleed regression). This loop bakes that gate in: every proposal is
validated by a fee-aware backtest before it matters.

## Loop anatomy (one iteration)
1. **Scientist (GPU1)** — given the current best active setup + the last N
   results (score, ret, sharpe, maxdd, fees, trades), diagnoses what's wrong
   and returns 3 candidate configs as JSON (respecting hard bounds).
2. **Backtest (CPU)** — each candidate + 3 jitter-mutations of the best is run
   through the engine: blended technical signals → regime gate → risk sizing
   → SL/TP/trailing/max-hold exits → fixed $0.35/side fees.
3. **Objective** — `0.6*sharpe + 1.0*min(max(ret,0),0.6) - 2*maxdd
   - 3*fee_ratio - 0.3*churn`. Only ACTIVE configs (>= 8 trades) can be
   "best"; a do-nothing config (score 0.0) is recorded but never wins, so the
   search can't collapse into flat.
4. **Checkpoint** — ledger, best.json, progress.json saved atomically each
   iteration; loop is resumable.

## Files
- `setup_search/loop.py`    orchestrator (CLI + resume + plateau/wall-clock stop)
- `setup_search/scientist.py` GPU1 client (json-extraction + retries)
- `setup_search/engine.py`  cost-aware long-only backtest
- `setup_search/core.py`    config bounds + objective
- `setup_search/data.py`    yfinance 2y OHLCV fetch/cache (17 symbols)
- `data/setup_search/`      ledger.jsonl, best.json, progress.json, loop.log

## How to read results in the morning
- `data/setup_search/best.json` — best ACTIVE config, its metrics, equity curve.
- `data/setup_search/ledger.jsonl` — every evaluated config + score (search map).
- `data/setup_search/progress.json` — best score over time, plateau state.
- `tail -f data/setup_search/loop.log` — live progress.

Baseline (the config the live system was effectively running):
ret=-17.7% sharpe=-2.5 maxdd=18.7% trades=197 fees=$140 (28% bleed).
Anything the loop finds must beat that. If even the best is negative, that is
itself the finding: no simple daily-bar technical setup clears $0.35/side fees
on this universe — then the answer is "trade less / don't trade / go lower
frequency," which the loop will discover.

## Operations
- Launcher: `setup_search/run.sh` — stops `opentrader-harness.service` (frees
  GPU1; paper state persists), then `nohup`s the loop to
  `data/setup_search/loop.log`.
- Stopping: `kill $(pgrep -f setup_search.loop)`; resume by rerunning run.sh
  (checkpoint continues).
- To iterate on the code: edits auto-load on next `python3 -m setup_search.loop`
  invocation; the loop is stateless between calls except the checkpoint.
