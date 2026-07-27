# Signal Quality Improvement Plan

## Current State

- Win rate: 30% on synthetic data, all HOLD on real Alpaca prices
- Model: Qwen2.5 7B Q4_K_M with LoRA (Ptolemy-S3, DeepEval 0.78)
- Strategy: ADIR Bull/Bear/Risk debate, single-timeframe (1h), 49-industry scout
- Portfolio: $100 paper, 0 positions, 500+ cycles producing no BUY/SELL signals

## Root Causes

1. **Prompt produces HOLD bias** — the ADIR debate prompt asks the model to cite specific indicators with values, but the model defaults to HOLD when it can't find clear evidence
2. **No multi-timeframe context** — single 1h bars miss trend confirmation from 4h/daily
3. **Synthetic training doesn't transfer** — Ptolemy-S3 was trained on synthetic price patterns, not real market microstructure
4. **No regime conditioning** — model doesn't know if we're trending/ranging/volatile
5. **Confidence calibration broken** — model produces conf=0.1-0.3 consistently, never crosses the confidence gate

## Research Foundation

arXiv:2409.06289 "Automate Strategy Finding with LLM in Quant Investment" demonstrates a three-stage LLM-based alpha generation framework with 53.17% cumulative return:
- Stage 1: Prompt-engineered LLMs generate alpha factor candidates
- Stage 2: Multi-agent evaluation filters by market status and predictive quality
- Stage 3: Dynamic weight optimization adapts to market conditions

Key insight applicable to OpenTrader: **multi-timeframe prompt engineering + regime-aware agent evaluation** produces actionable signals where single-timeframe debate stalls.

---

## Phase 1: Rapid Prototyping (2-3 hours)

### 1a. Multi-Timeframe Prompt Engineering

Modify the ADIR debate prompt to include 3 timeframes (1h / 4h / 1d) with computed indicators per timeframe:

```python
MULTI_TF_PROMPT = """
Price: ${price:.2f}
1h: RSI={rsi_1h:.1f} MACD={macd_1h:.4f} SMA20={sma_1h:.2f} Vol={vol_1h:.0f}
4h: RSI={rsi_4h:.1f} MACD={macd_4h:.4f} SMA20={sma_4h:.2f}
1d: RSI={rsi_1d:.1f} SMA20={sma_1d:.2f}
Regime: {regime} (confidence={regime_conf:.2f})
Recent: {pct_1h:+.2f}% (1h), {pct_4h:+.2f}% (4h), {pct_1d:+.2f}% (1d)

Action: BUY if 1h+4h agree AND 1d confirms. SELL if 1h+4h agree AND 1d confirms.
HOLD if any timeframe disagrees. Confidence: 0-100 based on agreement strength.
"""
```

### 1b. A/B Test Harness

Create `training/signal_quality_test.py` (~100 lines):
- Runs 20 debates per symbol with old prompt vs new multi-TF prompt
- Compares: BUY/SELL ratio, avg confidence, signal dispersion
- Backtests signals against next-candle return
- Reports win rate, hit ratio, Sharpe per prompt variant

### 1c. First Iteration

Test with 3 symbols (NVDA, AAPL, BTC) × 20 debates = 60 LLM calls (~8 minutes).
If multi-TF produces >40% actionable (non-HOLD) signals with >0.3 avg confidence → keep.

### 1d. Second Iteration — Regime Conditioning

Add market regime context (from existing `_symbol_regimes` dictionary):
- "TRENDING_UP" → bias BUY, lower confidence threshold
- "TRENDING_DOWN" → bias SELL, lower confidence threshold
- "RANGING" → HOLD, highest confidence threshold
- "VOLATILE" → reduce position size, skip debate

If regime conditioning increases Hit Rate by 5%+ → keep.

### 1e. Third Iteration — Confidence Calibration

Lower the ADIR confidence gate threshold:
- Current: `enable_confidence_gate=True`, threshold=0.75
- Test: `threshold=0.35` (opens the gate for low-conviction calls)
- Backtest: does lower threshold increase total P&L (even if win rate drops)?

If P&L improves → keep lower threshold and add dynamic threshold scaling by regime.

---

## Phase 2: Signal Quality Metrics Framework (1-2 hours)

### 2a. Backtest Harness

Create `training/signal_backtester.py`:
- Replays last N cycles of debate output from `ui_feed.jsonl`
- Computes: forward return, hit rate, profit factor, max drawdown per symbol
- Groups by: signal.action, confidence range, regime, time of day
- Outputs: per-symbol report + aggregate quality score

### 2b. Live Quality Tracking

Add to harness: track signal accuracy per symbol, store in `paper_state.json.metrics.signal_accuracy`.
Already partially implemented — verify it's collecting per-confidence-band accuracy.

### 2c. Winner-Stays-On Model

Track which prompt variant + confidence threshold produced the best forward returns.
Auto-select the winning combination for each market regime.

---

## Phase 3: Scale and Harden (1-2 hours)

### 3a. Fine-Tune S4 with Winning Prompt

Once the winning prompt + threshold + regime combo is identified:
1. Run 200+ debates with the new prompt on real Alpaca data
2. Extract the debate chains (ohlcv + prompt + model response)
3. Build training dataset from winning debates
4. Fine-tune Ptolemy-S4 using the same LoRA pipeline

### 3b. Multi-Strategy Alpha

Add a second strategy alongside ADIR:
- Momentum breakout (price > SMA20 + ATR*2 → BUY)
- Mean reversion (RSI < 30 → BUY, RSI > 70 → SELL)
- Each strategy has independent weight in the portfolio optimizer

This is the "strategy matrix" improvement that produces +3-5% alpha vs single-strategy.

### 3c. Continuous Improvement Loop

- Every 100 cycles: run `signal_quality_test.py` on the prompt history
- If win rate drops below threshold → auto-generate prompt variant
- A/B test variant against current prompt for 50 cycles
- Promote winner automatically

---

## Phase 4: Web Research Integration

### 4a. News Sentiment Injection

Fetch headlines for debate symbols from NewsAPI or Yahoo Finance RSS.
Inject as context: "Recent headlines: {headline_1}, {headline_2}"
Test if sentiment-aware prompts produce higher-confidence signals.

### 4b. Earnings/Event Calendar

Add Fed meeting dates, earnings releases, economic data releases.
Pre-debate: check if any of today's events affect the symbol.
If earnings are in 3 days: "Earnings in 3 days — position size 50%, tighter stops"

---

## Execution Order

| Step | What | Time | Files | Gate |
|------|------|------|-------|------|
| 1a | Multi-TF prompt | 45m | `harness.py` (prompt only) | Test: >40% non-HOLD signals |
| 1b | A/B test harness | 30m | `training/signal_quality_test.py` (new) | Test: runs 60 debpates, reports metrics |
| 1c | First iteration | 15m | — | Gate: actionable signals >40% |
| 1d | Regime conditioning | 30m | `harness.py` | Gate: Hit Rate +5% |
| 1e | Confidence calibration | 15m | `adir_debate.py` | Gate: P&L improves |
| 2a | Backtest harness | 45m | `training/signal_backtester.py` (new) | Test: per-symbol report |
| 2b | Live tracking | 15m | `harness.py` | Test: per-confidence-band accuracy |
| 3a | S4 fine-tune | 3h | `finetune_cycle.py` | Gate: DeepEval > S3 (0.78) |
| 3b | Multi-strategy | 2h | `harness.py`, `risk/portfolio_optimizer.py` | Test: blended Sharpe >1.0 |
| 4a | News injection | 1h | `harness.py`, `tools/news_fetcher.py` (new) | Test: confidence +0.1 avg |
| **Total** | | **~10h** | | |

---

## Success Criteria

- Actionable (non-HOLD) signal rate: **>50%** (currently 0% on real data)
- Win rate: **>45%** (currently 30% on synthetic)
- Avg confidence: **>0.40** (currently 0.15-0.25)
- Portfolio return: **positive 15+ cycle rolling window**
- Cycle time: **< 60s** maintained (multi-TF doesn't add compute)

---

## Risk

- **Overfitting**: Multi-TF prompt might force the model to make calls it's not qualified for → picks wrong direction
- **Mitigation**: A/B test each prompt change against baseline, use forward returns not in-sample fit
- **Time**: 10h build time — Phase 1 produces actionable improvements within 2h. Stop there if no improvement.

## File Changes Summary

| File | Change |
|------|--------|
| `harness.py` | Multi-TF prompt, regime conditioning |
| `adir_debate.py` | Confidence threshold adjustment |
| `training/signal_quality_test.py` | **New** — A/B test harness |
| `training/signal_backtester.py` | **New** — backtest harness |
| `tools/news_fetcher.py` | **New** — sentiment injection |
| `finetune_cycle.py` | S4 training (read-only) |
| `risk/portfolio_optimizer.py` | Multi-strategy weights |
