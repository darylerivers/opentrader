# Portfolio war referee: what to reuse + speed budget

**Status:** Research decision — supplies the war-sim recipe the reward protocol and the iteration protocol consume.
**Date:** 2026-08-04
**Companion map:** [Momentum agent arena: RL candidate-battle + portfolio-war referee](https://github.com/darylerivers/opentrader/issues/61)
**Builds on:** [Arena reward + war-relabeling protocol on the value-head loop](https://github.com/darylerivers/opentrader/issues/66) — this ticket is the one that ticket is blocked by; it supplies the "war-sim recipe and its relabelable outcome signals" that protocol's Step 2 depends on.

## Summary — yes, the portfolio war can be a CPU-fast referee

Measured on this repo's own sim stack (python 3.13, pandas 2.3, one core): a full war run —
20 candidate agents, each trading a symbol sub-book over a 2-year daily replay (500 bars,
17-symbol universe) — costs **~0.76 s total, ~38 ms per candidate book**. Even the
full-width variant (each candidate over all 16 tradeables) is **~5.8 s for 20 candidates**.
The referee runs a **handful of times per iteration**, so its whole budget is **~5–120 s
per iteration — 1–5% of a ~10 min QLoRA train** (the heavy side is the candidate battle's
thousands of rounds, not the war).

Every signal the reward protocol needs — portfolio P&L, per-candidate drawdown
contribution, per-regime decomposition, and per-state reward relabeling — is already
emitted by the reused sim's output (`net_return`, `equity`, `trades[]` with `sym`, `pnl`,
`pnl_pct`, `entry_date`, `exit_date`, `bars`, `reason`), or is a sub-2 ms pass over the
trade log. No LLM is in the loop; the war is numeric, seeded/criticized by the value head.

## What exists to reuse

| Component | Source | Measured cost (CPU, 1 core) | War role |
|---|---|---|---|
| Portfolio backtest sim | `setup_search/engine.py` `run_backtest` | 0.12 s / 250 bars (1y), 0.27 s / 500 (2y), 0.71 s / 1250 (5y) at 16 syms; ~0.05 s per symbol per 1250 bars | Core book sim: entries, SL/TP/trailing/max-hold/signal exits, per-position risk sizing, max-pos/max-exposure caps, fee-aware min-notional |
| OHLCV archive | `setup_search/data.py` `load_ohlcv`/`align` → `data/setup_search/ohlcv_{1y,2y,5y}.pkl` (16 tradeables + SPY) | 0.02 s load+align | Replay-window source; SPY = regime marker |
| Feature/score/rank engine | `setup_search/engine.py` `_features`, `_score_at`, `_cross_sectional_rank` | sub-ms | Candidate scoring shared with the value head |
| Labeled (state, reward) emitter | `setup_search/value_head.py` `collect()` | ms | 10-bar forward-return labels — the relabel target's base |
| Single-symbol sim + difficulty transforms | `training/traderbench.py` `Simulator` (4 bps fees, 5 bps slippage, half-Kelly), `baseline`/`noisy`/`meta`/`adversarial` transforms, external-transform loader | 0.1–0.33 ms per sim run (250 bars); 0.7 ms for a full 4-transform pass | Regime/perturbation variety and the difficulty ladder for stress folds |
| Ledger search history | `data/setup_search/ledger.jsonl` (875 configs), `best.json` | — | Candidate/field provenance; the validated config war sims can be seeded from |
| Live cycle snapshots | `data/history/cycle_*.json` (110) | — | Historical war ground truth (portfolio value, cash, positions, fills) |
| Crypto leg (kraken) | `setup_search/crypto_leg.py` (`BTC-USD` regime leader, 0.16%/side taker fee) | n/a — archive (`crypto_ohlcv.pkl`) not currently present | Optional second asset class for the war; same pipeline, same `run_backtest` |

**Not reusable for a CPU-fast war:**

- `harness.py`'s backtest path (`_push_new_bar` harness.py:1306, `_debate_one_symbol` harness.py:1801, `_debate_wrapper` harness.py:2688) — replays the **full live stack** with an LLM debate HTTP call per symbol per bar. It is the expensive path and the war must not go through it; the war's simulation is `engine.run_backtest` + `traderbench.Simulator`, not the harness.
- `training/rl_trainer.py` `BehavioralRLTrainer` — already ruled not reusable by the closed map's [Audit the reward-labeled environment + RL infrastructure](https://github.com/darylerivers/opentrader/issues/36) (field mismatch + reward ignored). No reason the war changes that.
- The finnhub/CCXT fetch paths (`exchange/stock_finnhub.py`, `exchange/live.py` `fetch_historical_bars`) are **live-fetch with in-memory TTL caches, no durable archive** — irrelevant to a replay war except as an on-demand bar source; the pkl archives are the durable replay data.

## Fidelity / speed trade-off

The war's two dials are **window length** and **book width**, both roughly linear in cost:

| Configuration | Cost per war run (measured) |
|---|---|
| 1 candidate book, 1y (250 bars), 16 syms | 0.12 s |
| 1 candidate book, 2y (500 bars), 16 syms | 0.27 s |
| 1 candidate book, 5y (1250 bars), 16 syms | 0.71 s |
| 1 candidate book, 2y, 2-sym sub-book | ~0.04 s |
| Full war: 20 candidates × 2y sub-book | ~0.76 s |
| Full war: 20 candidates × 2y full 16-sym book | ~5.8 s |

The exit/sizing ladder in `run_backtest` already carries the fidelity the $500 fee-dominated
account needs (per-side $0.35 floor, min-notional, max-exposure caps). The order-level
ledger in `exchange/paper.py` (partial fills, per-order slippage) is strictly more realistic
but adds per-order Python overhead for no war-level benefit — **skip it**. Difficulty/regime
variety costs ~0.7 ms per full transform pass, so stress folds are effectively free.

## Sample budget — war runs a handful, the battle runs thousands

- **Candidate battle** (the RL training loop): thousands of rounds × field, each round a
  `traderbench.Simulator` run at ~0.3 ms → the heavy side, thousands of policy evaluations per iteration.
- **Portfolio war** (referee between iterations): a **handful** of portfolio runs per
  iteration — one per regime window (bear/bull) per candidate book, plus seeds. At ~1–6 s
  per full war (20 candidates), even 20 war runs ≈ 10–120 s/iteration vs ~600 s QLoRA train:
  **1–5% of the iteration wall-clock**. The map's "war runs a handful of times per iteration
  vs thousands of candidate battles" is confirmed as the right split — the war's per-run
  cost is comparable to *one* battle round's population cost, so its whole budget is a rounding error on the training loop.
- **Data yield per war run** is not the constraint: each war run relabels all its decisions
  at once — every executed trade is a labeled (state, TAKE) with a realized `pnl_pct`, so a
  war run yields tens-to-hundreds of per-state reward corrections per run (the same density
  as the closed map's 134-candidate environment, but freshly relabeled under the current field).

## Relabelable episodic outcome signals (all cheap)

All four are computed from the reused sim's output; none needs the harness or an LLM.

1. **Portfolio P&L** — `net_return` + the `equity` curve from `run_backtest`, merged across
   candidate books (sum of sub-book equity). This is the war's headline score and the
   P&L-vs-persona episode metric the reward protocol's head-to-head term consumes.
2. **Drawdown contribution per candidate** — each candidate's sub-book `equity` curve gives
   its own max drawdown and its marginal contribution to the merged book's running-peak
   drawdown (each candidate is a labeled portfolio slice). Free once the sub-books are run.
3. **Per-regime decomposition** — tag each trade by regime at entry (SPY vs 200-day MA):
   measured **1.6 ms for 53 trades**. Each trade's `pnl`, `pnl_pct`, `entry_date`,
   `exit_date`, `bars`, `reason` are in the log, so up/down (or any regime fold) P&L splits
   are a dict-grouping away. This is the protocol's per-regime pooling input.
4. **Per-state reward relabeling** — each trade's `pnl_pct` **is** the realized forward
   return of that (state → TAKE) decision, in the same return units as the value head's
   10-bar `fwd` target. So the relabel is a copy of the war's realized trade returns back
   onto the decisions that produced them, and because the field's outcome on the *same
   candidate* is in the log, the reward protocol's `δ_t = (r_t − V(s_t)) + (r_t − r_field_t)`
   correction is directly computable. Nothing episodic needs discount-rollout — the closed
   map's contextual-bandit framing holds (a candidate is an independent trade).

## The war-sim recipe

1. **Data:** `load_ohlcv("5y")` + `align()` (0.02 s) → slice a replay window
   (`setup_search.data.slice_aligned` or an `iloc[:n]` slice). Durable, deterministic, CPU-local.
2. **Field:** N candidate TAKE/SKIP policies (value-head-seeded agent + persona bots). Each
   owns a symbol sub-book (per-candidate attribution) or the whole book (pooled). Replace
   `run_backtest`'s `score ≥ buy_thresh` entry gate with the candidate's TAKE/SKIP on that
   candidate's symbols; the exit ladder, sizing, caps and fees stay untouched.
3. **Regime folds:** split the window by SPY > 200-day MA into bear/bull sub-windows; optionally
   run `traderbench` transforms (noisy/meta/adversarial, 0.7 ms/pass) for stress folds.
4. **Book sim:** one `run_backtest` per candidate book (~0.04 s at 2y/2-sym, 0.27 s at 2y/full).
5. **Merge + score:** portfolio equity = sum of sub-book curves; portfolio P&L, max DD,
   Sharpe, win rate. P&L-vs-each-persona = the war score.
6. **Relabel:** per-trade `pnl_pct` + regime tag + field outcome → per-state rewards and
   `δ_t` corrections for the next value-head fit; per-candidate DD contributions; portfolio
   P&L for the gate. **The war gates before it relabels** (per the reward protocol), and the
   gate always reads raw, un-relabeled candidates.

**Expected wall-clock per war run: ~0.8–6 s (20 candidates, 2y replay).** Budget: a handful
per iteration; total war cost ≈ 1–5% of the iteration's ~10 min training budget.

## Sources

Tickets (cited by title, per wayfinder convention):

- [Momentum agent arena: RL candidate-battle + portfolio-war referee](https://github.com/darylerivers/opentrader/issues/61) — architecture (battle = training loop, war = referee between iterations, few runs), baseline failure −2.50%, "what to reuse + speed budget" question.
- [Arena reward + war-relabeling protocol on the value-head loop](https://github.com/darylerivers/opentrader/issues/66) — consumes this recipe's signals; δ correction, gate-before-relabel, per-regime pooling.
- [Apprentice learns to trade via RL from the rule playbook](https://github.com/darylerivers/opentrader/issues/35) — closed map; contextual-bandit framing (candidate = independent trade).
- [Audit the reward-labeled environment + RL infrastructure](https://github.com/darylerivers/opentrader/issues/36) — 134 (state, reward) candidates over 5y; `BehavioralRLTrainer` not reusable.
- [Design the policy architecture + anti-overfitting training loop](https://github.com/darylerivers/opentrader/issues/37) — MLP value head `V(state)→E[fwd]`, 10-bar forward return target.

Code and data (all measured on this branch, python 3.13 / pandas 2.3, 1 core):

- `setup_search/engine.py` — `run_backtest` (0.12–0.71 s full-book over 1y–5y; ~0.05 s per symbol per 1250 bars), `_features`, `_score_at`, `_cross_sectional_rank`; trade log fields `sym/pnl/pnl_pct/entry_date/exit_date/bars/reason`.
- `setup_search/data.py` — `load_ohlcv`/`align` (0.02 s); `data/setup_search/ohlcv_{1y,2y,5y}.pkl` archives.
- `setup_search/value_head.py` — `collect()` (10-bar fwd labels), `ValueMLP` (Linear `d_in→32→16→1`, ReLU, Dropout 0.2).
- `training/traderbench.py` — `Simulator` (4 bps fee, 5 bps slippage, half-Kelly; 0.1–0.33 ms per 250-bar run), `baseline`/`noisy`/`meta`/`adversarial` transforms (0.7 ms per full pass), external-transform loader.
- `setup_search/crypto_leg.py` — kraken crypto leg (BTC regime leader, 0.16%/side); archive not currently present.
- `harness.py` (`_push_new_bar`:1306, `_debate_one_symbol`:1801, `_debate_wrapper`:2688) — the slow live-stack backtest path, ruled out for the war.
- `data/setup_search/ledger.jsonl` (875 configs), `data/history/cycle_*.json` (110 cycle snapshots), `exchange/paper.py` (order-level ledger, not needed at war fidelity).
