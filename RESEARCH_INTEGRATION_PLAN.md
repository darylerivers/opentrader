# OpenTrader — Research Integration Plan

**Last Updated:** 2026-07-23
**Phase:** Research Integration (Phases 1-7)

---

## Table of Contents

1. [Phase 1: Fix Critical Bugs](#phase-1-fix-critical-bugs)
2. [Phase 2: Signal Quality — Multi-Timeframe Indicators](#phase-2-signal-quality--multi-timeframe-indicators)
3. [Phase 3: Market Context Injection](#phase-3-market-context-injection)
4. [Phase 4: News & Events Integration](#phase-4-news--events-integration)
5. [Phase 5: A/B Testing Framework](#phase-5-ab-testing-framework)
6. [Phase 6: Research Pipeline](#phase-6-research-pipeline)
7. [Phase 7: TUI Dashboard Upgrades](#phase-7-tui-dashboard-upgrades)

---

## Phase 1: Fix Critical Bugs

**Goal:** Eliminate runtime crashes and ensure stable operation.

### P1-1: Fix `report_risk.py` positions dict/list mismatch
**Status:** ✅ FIXED (already on disk)
- Line 17-20 now handles both dict and list formats
- `pos = {p["symbol"]: p for p in s.get("positions", []) if isinstance(p, dict)}`

### P1-2: Fix `report_risk.py` stage always "?"
**Status:** ✅ FIXED (already on disk)
- Line 40 now reads `s.get("models", {}).get("stage", s.get("metrics", {}).get("stage", "?"))`

### P1-3: Fix training scheduler shares arxiv variable
**Status:** ✅ FIXED (line 320: `_last_training_eval` now separate from `_last_arxiv_extract`)

### P1-4: Fix FlashTrainer non-existent model names
**Status:** ✅ FIXED (lines 377-378 now use `ls:qwythos-9b-mtp`)

### P1-5: Fix `--llama-host` default port
**Status:** ✅ FIXED
- `run_harness.py` line 59: `--llama-host http://127.0.0.1:5809`
- `harness.py` line 135: `llama_host or cfg.get("llama_host", "http://127.0.0.1:5809")`
- `agent/trading_agent.py` line 372: default is now `:5809`
- `mot/agents/adir_debate.py` line 312: default is now `:5809`
- `mot/agents/debate.py` line 162: default is now `:5809`

### P1-6: Fix harness file syntax corruption
**Status:** ✅ FIXED (removed duplicate top-level code block, fixed indentation)

**Verification Command:**
```bash
cd /home/mrc/opentrader
python3 -c "import ast; ast.parse(open('harness.py').read()); print('✓ Syntax OK')"
```

---

## Phase 2: Signal Quality — Multi-Timeframe Indicators

**Goal:** Add multi-timeframe technical indicators (1h/4h/1d) to the ADIR debate context, enabling the agent to see trend alignment across timeframes.

### Files Created/Modified
| File | Change |
|------|--------|
| `data/multi_tf.py` | New helper: `_compute_tf_indicators()`, `_compute_tf_indicators()` |
| `mot/agents/debate.py` | Added `_compute_tf_indicators()` helper + integrated into `build_context()` |

### How It Works
```python
# data/multi_tf.py
def compute_multi_tf_indicators(bars: List[dict], symbol: str) -> dict:
    """Compute RSI, MACD, SMA20, Vol, Trend for 1h, 4h, 1d timeframes."""
    # Downsample 1h bars into 4h and 1d bars
    # Compute indicators per timeframe
    return {"1h": {...}, "4h": {...}, "1d": {...}}

def format_multi_tf_prompt(indicators: dict, symbol: str) -> str:
    """Format as prompt block:
       1h  RSI=68 (OVERBOUGHT)  Vol=2.5%  Price=$45,200
       4h  RSI=62 (BULLISH)  Vol=1.8%  Price=$45,150
       1d  RSI=58 (BULLISH)  Vol=1.2%  Price=$45,100
    """
```

### Integration Point
`mot/agents/debate.py` → `build_context()` → `_compute_tf_indicators(bars)`
- Returns formatted multi-TF string appended to context
- Uses same bars data already available to the debate engine
- No new API calls — purely computed from existing data

### Success Criteria
- Multi-TF indicators appear in `data/harness.log` under "Market Context"
- Agent debates include 1h/4h/1d RSI, MACD, SMA20 values
- Win rate improves by ≥5% over 20-cycle test

---

## Phase 3: Market Context Injection

**Goal:** Enrich debate context with equity markets (S&P 500, NASDAQ, VIX), crypto sentiment (Fear & Greed), and trending assets.

### Files Modified
| File | Change |
|------|--------|
| `mot/agents/debate.py` | Already has EQUITY MARKETS + CRYPTO SENTIMENT sections (lines 279-278) |
| `data/economics.py` | Add `fetch_equity_markets()` → S&P 500, NASDAQ, VIX via yfinance |
| `data/news.py` | Add `fetch_equity_markets()` integration into existing fetch functions |

### Equity Market Context Example
```
EQUITY MARKETS:
  S&P 500: 4,523.47 (+0.24%)
  NASDAQ: 18,432.91 (+0.41%)
  VIX: 14.32
```

### Success Criteria
- Equity market data appears in harness logs
- Dashboard shows equity context in cycle summaries

---

## Phase 4: News & Events Integration

**Goal:** Add earnings calendars, Fed meeting dates, and economic data releases to debate context.

### Files to Create
| File | Purpose |
|------|---------|
| `data/earnings.py` | Fetch earnings dates/prices from Yahoo Finance |
| `data/events.py` | Fetch Fed meeting dates, CPI/NFP dates |
| `data/sentiment_enrichment.py` | Integrate with existing `news.py` for sentiment scoring |

### Earnings Calendar Context Example
```
EVENTS:
  Earnings: NVDA earnings in 3 days (consensus $90.00, EPS growth +22%)
  Fed Meeting: 2026-07-30, rate decision expected 5.25%
  CPI Release: 2026-07-29, expected +0.4%
  Guidance: Higher-than-expected → position size 50%, tighter stops
```

### Success Criteria
- Events appear in harness logs
- Agent reduces position size when earnings are within 3 days
- Earnings dates tracked in dashboard

---

## Phase 5: A/B Testing Framework

**Goal:** Systematically test prompt variants and track signal quality metrics.

### Files Created
| File | Purpose |
|------|---------|
| `training/signal_quality_test.py` | A/B test harness — runs N cycles, compares prompt variants |
| `data/ab_test_results.json` | Stores test results, metrics, comparisons |

### Usage
```bash
# Run baseline (current ADIR prompt) vs multi-TF prompt
python3 training/signal_quality_test.py \
  --symbol BTC/USDT --cycles 20 --interval 10 --stage 1

# View results
cat data/ab_test_results.json
```

### Metrics Tracked
| Metric | Definition | Target |
|--------|-----------|--------|
| Action Rate | % non-HOLD signals | >45% |
| Avg Confidence | Mean confidence of all signals | >0.35 |
| Max Confidence | Highest confidence in sample | >0.50 |
| BUY Rate | % BUY signals | ~50% |
| SELL Rate | % SELL signals | ~50% |

### Success Criteria
- A/B test produces comparable results for both prompts (baseline is stable)
- Multi-TF prompt shows ≥5% improvement in action rate
- Results logged to `data/ab_test_results.json`

---

## Phase 6: Research Pipeline

**Goal:** Continuous discovery of new trading techniques from arXiv, HF Hub, and academic literature.

### Files Modified
| File | Change |
|------|--------|
| `data/research/` | New eval_transforms/ files for capability distillation |
| `training/research_runner.py` | Schedule periodic arXiv scans |
| `training/eval_gate.sh` | Add new research evaluation criteria |

### Research Sources
| Source | Type | Frequency |
|--------|------|-----------|
| arXiv:q-fin | Papers | Daily (via API) |
| HuggingFace Hub | Models/Projects | Weekly scan |
| SSRN | Preprints | Weekly |
| arxiv-scan API | New papers | Hourly |

### Research Integration Workflow
```
arXiv Scan (daily) → Filter q-fin, q-fin.MG, q-fin.CM
    ↓
Extract: Method, Dataset, Performance Metric, Code
    ↓
Evaluate: Can it be applied to OpenTrader?
    ↓
If Yes → Create eval_transform (data/research/eval_transforms/)
    ↓
Test: Run on historical data, compare to baseline
    ↓
If Improve → Add to eval_gate criteria, deploy to training
    ↓
Monitor: Track real-time performance vs baseline
```

### Success Criteria
- `data/research/capability_manifest_*.json` updated weekly
- At least 1 new eval transform created per month
- Research findings documented in `data/research/README.md`

---

## Phase 7: TUI Dashboard Upgrades

**Goal:** Surface the agentic engineering layer (ADIR debate, universe scouting, eval scores, research heartbeat) in the TUI dashboard.

### Files Modified
| File | Change |
|------|--------|
| `tui_dashboard.py` | Add 2 new tabs: "Debate" and "Pipeline" |
| `harness.py` | Append `ui_feed.jsonl` per cycle (universe picks + debate votes) |

### New Tabs
**Tab 4: Debate**
- Per-symbol ADIR votes: Bull/Bear/Risk actions + confidences
- Color-coded agreement (green=agree, red=disagree)
- Multi-TF indicator values per symbol

**Tab 5: Pipeline**
- Eval scores per model (Ptolemy-S0 to S3)
- Pending candidates awaiting eval
- Deploy gate thresholds (current vs active)
- Research heartbeat (last scout, distill, ATDL trigger)
- Staleness flags (red if >6h)

### Success Criteria
- `python3 tui_dashboard.py` → Tab 4 "Debate" shows live debate votes
- `python3 tui_dashboard.py` → Tab 5 "Pipeline" shows eval scores, pending candidates, research heartbeat
- No harness changes required for dashboard (reads `data/ui_feed.jsonl` and state files)

---

## Implementation Timeline

| Phase | Files | Effort | Dependencies |
|-------|-------|--------|--------------|
| 1: Fix Critical Bugs | harness.py, agent/trading_agent.py, mot/agents/*.py | ~30 min | None |
| 2: Multi-Timeframe Indicators | data/multi_tf.py, mot/agents/debate.py | ~45 min | Phase 1 |
| 3: Market Context | data/economics.py, data/news.py | ~45 min | Phase 2 |
| 4: News & Events | data/earnings.py, data/events.py, data/sentiment_enrichment.py | ~60 min | Phase 3 |
| 5: A/B Testing | training/signal_quality_test.py | ~30 min | Phase 2 |
| 6: Research Pipeline | data/research/, training/research_runner.py | ~60 min | Phase 5 |
| 7: TUI Dashboard | tui_dashboard.py, harness.py | ~60 min | Phase 5 |
| **Total** | | **~4.5 hours** | |

---

## Verification Checklist

After each phase, verify:
- [ ] Code syntax valid: `python3 -c "import ast; ast.parse(open('file.py').read())"`
- [ ] Harness runs without crash: `python3 harness.py --exchange paper --stage 1 --cycles 5`
- [ ] Dashboard renders: `python3 tui_dashboard.py`
- [ ] Logs show expected output: `tail -50 data/harness.log`
- [ ] State persists: `cat data/paper_state.json | head -20`

---

## Token Budget Management

| Phase | Est. Tokens | Description |
|-------|-------------|-------------|
| 1 | 200 | Read file, apply edits, verify syntax |
| 2 | 300 | Read context, add helper, modify build_context |
| 3 | 250 | Read files, add functions, verify |
| 4 | 350 | Create 3 files, verify API calls |
| 5 | 200 | Run test, verify results |
| 6 | 300 | Create files, verify pipeline |
| 7 | 250 | Modify dashboard, verify tabs |
| **Total** | **1850** | |

---

## Files Modified (Summary)

| File | Phase | Lines Added |
|------|-------|-------------|
| `harness.py` | 1, 3 | ~20 (syntax fix) |
| `agent/trading_agent.py` | 1 | 2 (port fix) |
| `mot/agents/adir_debate.py` | 1 | 2 (port fix) |
| `mot/agents/debate.py` | 2 | ~50 (multi-TF + build_context) |
| `data/multi_tf.py` | 2 | 150 (new file) |
| `data/economics.py` | 3 | ~30 (new function) |
| `data/news.py` | 3 | ~10 (integration) |
| `data/earnings.py` | 4 | ~40 (new file) |
| `data/events.py` | 4 | ~30 (new file) |
| `data/sentiment_enrichment.py` | 4 | ~20 (new file) |
| `training/signal_quality_test.py` | 5 | ~200 (new file) |
| `training/research_runner.py` | 6 | ~50 (extension) |
| `tui_dashboard.py` | 7 | ~150 (new tabs) |
| `harness.py` (ui_feed) | 7 | ~20 (append JSONL) |
| **Total** | | **~800** |

---

## Next Steps

1. **Immediate:** Run Phase 1 verification — all critical bugs fixed
2. **Today:** Phase 2 (multi-TF indicators) + Phase 5 (A/B testing)
3. **Tomorrow:** Phase 3-4 (market context + news/events)
4. **Following Week:** Phase 6-7 (research pipeline + dashboard)
5. **Continuous:** Monitor research, add new eval transforms as papers arrive
