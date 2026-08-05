# OpenTrader — Session Todo & State
**Last updated:** 2026-07-11 | **Session focus:** Dashboard, trading fixes, $100 capital, fee-aware architecture

---

## ✅ COMPLETED THIS SESSION

### Infrastructure
- [x] Auto-reload system — `run_harness.py` watches .py files, kills harness, wipes `__pycache__`, restarts
- [x] `harness.py` startup auto-clears `__pycache__` at `main()` entry
- [x] Dashboard GZip compression — 119KB → 24KB HTML, 90KB → 3KB API responses
- [x] Dashboard mobile optimization — summary endpoint (700 bytes) for fastRefresh instead of full state
- [x] `state/context.py` — AccountContext, FeeSchedule, FEE_TABLES for 6 exchanges
- [x] Fee-aware debate prompting — `[ACCOUNT]`/`[FEES]`/`[ADVICE]` blocks injected into LLM prompt

### Trading Fixes
- [x] Timeframe scaling: `max_position_cycles 50→500`, SL 5%→4%, TP 10%→8%, trailing stop tuned
- [x] `min_cash_reserve 5000→5` — was rejecting all trades at $100 capital
- [x] Circuit breaker fix — `peak_value=$100K` from old state causing 99.9% drawdown on $100 account
- [x] `_initial_cash` state restore no longer overwrites `--cash` CLI arg
- [x] SL/TP guard — debate-driven SELLs blocked when SL/TP/stop active; exits delegated to risk engine
- [x] 3-symbol debate producing correct signals (BTC/ETH/SOL), portfolio optimizer returning 3 allocations
- [x] Signal symbol fix — harness forces `sig.symbol = active_symbols[i]` before optimizer

### Risk & Optimization
- [x] `risk/param_optimizer.py` — per-symbol parameter optimization from trade journal (TP/SL/Kelly/hold)
- [x] `RiskManager._load_symbol_params()` — loads `optimal_params.json` per-symbol, cached by mtime
- [x] Param optimizer wired into `harness.py run_cycle()` — triggers every 50 cycles

### Dashboard UI
- [x] Trade Stats avg winner/loser → `$x.xx` (2 decimal places)
- [x] Positions table fixed — uses `/api/dashboard/positions` with SL/TP/HIGH/AGE/PNL%
- [x] Market regime sparklines — inline SVG polylines per symbol (140×32, green/red)
- [x] Period change % — portfolio card + each regime box shows since-tracking-began delta
- [x] SONY stale data filtered — only shows symbols in active stage

### Data State
- [x] 39K cycle history archived to `data/history_archive_100k/` (kept for training)
- [x] `paper_state.json` reset to clean $100 capital
- [x] Fresh `data/history/` with 184+ cycle files

---

## 🔧 CURRENT RUNNING STATE

| Service | Port | Status |
|---------|------|--------|
| llama-server | :5809 | Running |
| dashboard.py | :8098 | Running |
| harness.py | via run_harness.py | Running |
| mcp_server.py | :8092 | Unknown (may need restart) |

**Harness config:** `--live --exchange kraken --stage 2 --cash 100 --max-daily-trades 500 --parallel-debate`
**Positions:** BTC/ETH/SOL at 5-7% each (~$5 per trade)
**Fee context:** Model sees "$0.03 round-trip (0.5% of $5 position)"

---

## 📋 NEXT SESSION — Priority Tasks

### 1. 🟠 Investigate Allocation Mutation Bug
- **Symptoms:** PortfolioOptimizer logs `ALLOC-BUY` with positive qty, but `allocate_portfolio` returns HOLD allocations. Harness has `ALLOC-FIXUP` as workaround.
- **Suspect:** `@dataclass` instance sharing or callback mutation between return and harness access
- **Action:** Trace Allocation objects from creation to consumption. Check for `__del__`, `__post_init__`, or middleware that modifies `PortfolioResult.allocations`

### 2. 🟠 Trade Journal Not Being Persisted
- **Symptoms:** `_trade_journal` has 0 entries even after fills execute. Paper state shows fills but journal empty.
- **Impact:** Per-symbol param optimizer never triggers (needs 5+ closed trades). Exit reasons not being recorded.
- **Action:** Check `_trade_journal.append()` code path in harness. Verify journal is preserved in state write.

### 3. 🟡 IBKR / Stock Integration
- Finnhub free tier returns 403 on OHLCV. yfinance fallback works for data.
- Need `ib_insync` installation for real execution
- Create `exchange/ibkr.py` with IBKR paper account support
- Wire IBKR into MultiExchangeRouter for stock symbols
- Update `connections.py` to manage IBKR credentials

### 4. 🟡 Asset Class Allocator
- Build `risk/asset_allocator.py` — model-driven allocation across crypto/stocks/forex
- The LLM proposes asset class weights; allocator adjusts position sizes
- Integrate with multi-asset FeeSchedule for commission-aware allocation

### 5. 🟡 Training Pipeline (DPO Fine-tuning)
- Extract `(context, good_decision, bad_decision)` from cycle history
- Build preference pairs dataset from closed trades
- Auto-trigger LoRA fine-tune on trade-count threshold (every 5K cycles, >50 new trades)
- Use archived `history_archive_100k/` for initial training data

### 6. 🟡 Data Management
- Deploy `data_mgmt.py` prune-dead (purge HOLD-only cycles)
- Skip redundant `StateManager.write()` when nothing changed (state_key hash already implemented)
- Clean up cycle file accumulation

### 7. 🟢 Dashboard Enhancements
- Fee-adjusted PnL display (show commission breakdown per trade)
- 24h rolling change % (currently shows "since tracking began" because cycle history is new)
- Trade journal "exit reason" coloring in UI
- Connections tab: fix "unknown" status for running services

### 8. 🟢 Verify $100 Profitability
- Let harness run for 1 week with current config
- Check actual PnL vs projected expectancy
- Validate that trades are actually hitting TP/SL (not timing out)
- Tune parameters if exit reasons are all "timeout" vs "take-profit"/"stop-loss"

---

## 📊 DATA REFERENCE

| Path | Content |
|------|---------|
| `data/paper_state.json` | Current portfolio state ($100, 3 positions) |
| `data/history/` | 184+ cycle files (growing) |
| `data/history_archive_100k/` | 39K old $100K cycle files (training data) |
| `data/connections.json` | API key store (Kraken, Finnhub, etc.) |
| `data/optimal_params.json` | Per-symbol optimized params (auto-generated at cycle N*50) |

## ⚙️ Config Reference

| Parameter | Value | Source |
|-----------|-------|--------|
| Initial capital | $100 | `harness.py --cash` |
| Default SL | 4% | `risk/manager.py RiskConfig` |
| Default TP | 8% | `risk/manager.py RiskConfig` |
| Max cycles | 500 | `risk/manager.py RiskConfig` |
| Trailing stop | 2% / 1.5% activation | `risk/manager.py RiskConfig` |
| Position drawdown | 5% | `risk/manager.py RiskConfig` |
| Min cash reserve | $5 | `risk/manager.py RiskConfig` |
| Kelly fraction | 0.35 (default), per-symbol from optimizer | `risk/manager.py RiskConfig` |
| Max position | 18% | `risk/manager.py RiskConfig` |
| Max total exposure | 25% | `risk/manager.py RiskConfig` |

## 📁 Files Created/Modified This Session

| File | Status | Purpose |
|------|--------|---------|
| `state/context.py` | NEW | AccountContext, FeeSchedule, FEE_TABLES |
| `risk/param_optimizer.py` | NEW | Per-symbol parameter optimization |
| `tools/dev_reload.py` | NEW | Dev-mode file watcher |
| `run_harness.py` | REWRITTEN | Auto-restart + pycache clearing |
| `harness.py` | HEAVILY MODIFIED | Capital handling, fees, SL/TP guard, param opt, signal fix |
| `risk/manager.py` | MODIFIED | SL/TP defaults, min_cash_reserve, per-symbol overrides, fee check |
| `risk/portfolio_optimizer.py` | MODIFIED | Debug cleanup |
| `dashboard.py` | HEAVILY MODIFIED | GZip, mobile, sparklines, period change, positions fix |
| `exchange/base.py` | MODIFIED | get_fee_schedule() to ExchangeBase |
