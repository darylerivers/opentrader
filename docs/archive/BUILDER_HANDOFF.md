# OpenTrader Builder Handoff — Jul 17

## Operational Status

| Component | State | Details |
|-----------|-------|---------|
| Harness | **Running** | PID 3131215, Alpaca paper exchange, direct 5806 |
| Model server | **Running** | llama-server P2tolemy-S3 LoRA, port 5806 |
| Database | **Stable** | paper_state.json: cycle 671, $100 PV, 0 positions, 500 signals |
| Registry | **Clean** | S3 active (0.7822), Alpha-1 removed, S0 fixed |
| Cron | **Active** | train 02:00, eval /30min, scheduler /12h, watchdog /5min |

## What Works

1. **Three-tier debate roster** — Tier 1 radar scans 511 tickers (batch API), Tier 2 Bull/bear agents rate top 20, Tier 3 ADIR Toulmin debate on top 6
2. **Smart debate** — Skips stale HOLD symbols without positions, achieving 0s deferred cycles
3. **Parallel debates** — ThreadPoolExecutor with `_cycle_debates` stored at call site (correct symbol attribution)
4. **Equity market context** — S&P 500, NASDAQ, VIX injected into debate context via yfinance
5. **ATR-14 dynamic stops** — 3x ATR stop-loss, 6x take-profit
6. **Single-stage scout** — 511 batch prices → industry radar → LLM picks top candidates
7. **Watchdog** — health.json every 5min, auto-restarts dead harness
8. **Advisor** — Uses eval_score from registry (not just win rate)

## Critical Bugs

### 1. ALL signals are HOLD with confidence < 0.35
**Root cause:** The Qwen2.5 7B model produces low-confidence HOLD on real Alpaca prices. Despite:
- Balanced BULL prompt (symmetrical BUY/HOLD, not BUY-only, temp 0.5)
- Lowered confidence gate (0.75 → 0.35)
- Multi-timeframe context (1h / 4h / 1d RSI + SMA)
- Equity market context (S&P, NASDAQ, VIX)
- Tier 2 agent rating (Bull + bear rate all 20 candidates)

**Why this happens:** The base Qwen model was not fine-tuned on trading decisions with real market data. It defaults to caution (HOLD) when it can't find clear evidence. Prompt engineering can tilt the needle but can't override the base weights.

**Fix required:** Fine-tune on real debate data with forward-return labels (S4 training).

**Data available:**
- `data/training/training_data_merged.jsonl` (2,787 examples)
- `data/training/synthetic_scenarios.jsonl` (2,000 examples)
- `data/harness.log` — 500+ debate chains from today with ADIR signals, prices, and agent votes

**Training path:**
```bash
cd /home/mrc/opentrader
/home/mrc/rocm_venv/bin/python3 -m training.finetune_cycle \
  --data data/training/training_data_merged_v2.jsonl \
  --epochs 1 --batch-size 1 --grad-accum 4 --log-level INFO
```

### 2. Tier 1 radar returns too few candidates (top20=6, not 20)
**Fix:** `_llm_json_array` min_score lowered from 5 to 1 (line 1683). Restart harness to apply. Already on disk.

### 3. BUY/SELL imbalance persists (18% BUY / 49% SELL)
**Root cause:** BEAR prompt NOT updated in parallel with BULL prompt. Only the BULL got balanced (BUY/HOLD). The BEAR still says "RISK AUDITOR — find reasons NOT to trade" (line 167).

**Fix:** Update `BEAR_SYSTEM_ADIR` in `mot/agents/adir_debate.py` to match the BULL's symmetrical format:
```
"You are a RISK ANALYST — your role is to find SELL signals
or confirm HOLD with equal weight. You are NOT required to output SELL."
```

### 4. TUI dashboard — HOLD-only display
**Not a rendering bug.** The dashboard correctly displays what the model produces: all HOLD with 0.01 confidence. The dashboard works — the model doesn't.

## Key Files

| File | Status | Last Change |
|------|--------|-------------|
| `harness.py` | Three-tier scout, smart debate, multi-TF, dynamic focus | Today |
| `mot/agents/adir_debate.py` | BULL prompt balanced (symmetrical), confidence gate 0.35 | Today |
| `mot/agents/debate.py` | Equity market context in build_context | Today |
| `data/news.py` | Added `fetch_equity_markets()` (yfinance S&P/NASDAQ/VIX) | Today |
| `exchange/alpaca_paper.py` | Batch price fetch, SimpleBar conversion, push_bar | Today |
| `training/signal_quality_test.py` | Signal quality metrics from log | Today |
| `training/signal_backtester.py` | Confidence-band breakdown | Today |
| `tui_dashboard.py` | 12 panels, 5 tabs, Console() auto-detect | Today |
| `mot/industry_map.py` | 49 industries, 511 tickers | Stable |
| `mot/tradable_universe.py` | 65 symbols (52 + 13 ag/mining/energy) | Stable |
| `training/ops_watchdog.py` | 6 checks, health.json | Stable |
| `training/eval_gate.sh` | SIGCONT trap, deploy chain | Stable |
| `docs/SIGNAL_QUALITY_PLAN.md` | 4-phase plan | Reference |
| `docs/AGENTIC_SDLC.md` | Architecture doc | Reference |

## Next Steps (priority order)

1. **Fix BEAR prompt** — balance it to match the symmetrical BULL (lines 167-209 in adir_debate.py)
2. **Restart harness** — to pick up min_score=1 fix for Tier 1 radar
3. **Trigger S4 training** — on real debate data with forward-return labels
4. **Re-evaluate S4** — via eval_gate.sh after training completes
5. **Deploy S4** — if DeepEval > 0.78 (S3 baseline)

## Do NOT Touch
- `mot/coordinator.py` — eval_score gate is in place
- `training/eval_gate.sh` — SIGCONT trap is stable
- `training/ops_watchdog.py` — works correctly
- `mot/coordinator.py`, `mot/adapter_registry.py` — registry persistence is fixed

## Harness Restart Command
```bash
kill $(pgrep -f "harness.py" | head -1) 2>/dev/null; sleep 1
rm -rf /home/mrc/opentrader/__pycache__
setsid python3 harness.py \
  --exchange alpaca-paper --stage 3 --cash 100 \
  --llama-host http://127.0.0.1:5806 \
  --max-cycles 0 --debate-mode adir --parallel-debate \
  --interval 10 \
  >> /home/mrc/opentrader/data/harness.log 2>&1 &
disown
```
