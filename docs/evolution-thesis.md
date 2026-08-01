# OpenTrader Evolution Thesis

**Status:** Living document — revised per milestone, not per cycle.
**Latest revision:** R1 · 2026-08-01
**Companion map:** [Small-capital launch](https://github.com/darylerivers/opentrader/issues/8)

This is the discussion, not the number. It charts how the system should evolve —
risk, model structure, data, hardware, and instrument access — as the account
grows from a small paper/$500 base toward a real deposit. Unlocks are gated on
**capital thresholds** and hardware work is **condition-triggered**, not
calendar-committed (dates on a fast-moving GPU/market are guesswork).

---

## 1. North star

- Paper-validate the strategy at $100–300 scale with **honest fees** (done:
  $300 is the minimum-viable deposit; $50/$100 cannot clear the fee-aware
  min-notional floor).
- The validated rule-based setup (+~5%/yr OOS, 3/3 unseen years) and the
  Genesis-debate system run as a **shadow A/B**; the thesis tracks which edge
  survives as scale and costs change.
- Every capability unlock below is written as: **trigger → action → cost → decision point.**

## 2. Risk assessment

| Risk | At $100–300 | As capital grows | Mitigation |
|---|---|---|---|
| Fee drag | Dominant — fixed $0.35/side is ~2.8% of a $25 position | Shrinks in % terms | Fee-aware rejection (round-trip fee ≤ 20% of notional), min-notional floor, low-activity rule config |
| Concentrated positions | 6-9 positions, up to 15%/pos, 95% exposure | Same caps; correlation risk grows | Max position/exposure caps, Kelly fraction, correlation penalty |
| Drawdown | Circuit breaker at 15%; validated config keeps maxDD ≤ ~3% | Scale breaker to $ | Portfolio stop, vol-targeting as account justifies it |
| Model error | 19.5% signal accuracy historically | Same | Low-activity gating, HOLD-streak rescout, validation gate (recent-25% must be positive) |
| Execution realism | Paper fills ~midpoint | Real slippage/impact appear | Swap shadow → live with reduced size; compare to backtest slippage model |
| Venue/regulatory | None (spot crypto) | PDT, margin rules | See §6 gates |

**Decision point (as capital crosses ~$1–3k):** switch sizing from risk-pct to
vol-targeting; introduce a slippage/impact model into the backtest before the
first live trade.

## 3. Model structure evolution

- **Today:** two lines run in parallel —
  - **Genesis** (qwythos-9b-mtp) driving ADIR debates (bull/bear/risk);
  - **rule-based setup** (setup-search best config: regime filter + momentum/
    RSI + fee-light) as the shadow A/B.
- **Trajectory:** Genesis → **Ptolemy** (S1–S4 LoRAs, retrained monthly on
  Genesis-generated + live trade data). The thesis is the **integration
  point**: it references the separate lifecycle effort, it does not own its
  internals or timeline.
- **Promotion rule:** a model/strategy is promoted to "primary" when its
  walk-forward OOS edge beats the incumbent by a margin **and** survives a
  fresh-parameter perturbation (≥70% positive neighbors — the bar the current
  rule setup meets).
- **Hybrid hypothesis:** the durable end-state is likely **rule-based regime
  gating + LLM edge** — the LLM proposes where the rules can't see; the rules
  gate what the LLM can spend. Test this explicitly once both lines have ~1
  season of live shadow data.

## 4. Data accumulation & limitations

| Source | Status (2026-08-01) | Ceiling / constraint |
|---|---|---|
| FRED macro | ✅ real (key added) | Free tier fine for the 8 tracked series |
| Kraken spot | ✅ live | 0.16/0.26% fees; no rate wall |
| Kraken futures funding | ✅ prototype `[FUNDING]` | Free; 8h cadence |
| Order-book depth | ✅ prototype `[ORDERBOOK]` | Free; spot-only guard |
| Finnhub stock bars | ✅ live | **60 calls/min** free tier — the hard data ceiling |
| Finnhub news sentiment | ❌ dropped | Premium-gated |
| On-chain (CDP) | ⏸ deferred | Testnet-only adapter |
| Yfinance fallback | ⚠️ flaky | Delisted errors; 1mo/6mo periods |

**Limitations to plan around:**
- Finnhub 60/min caps universe size and bar-fetch frequency — a reason the
  universe is ~16 traded symbols with cached batch prices (TTL 30min).
- Trade/paper records accumulate only in the shadow + setup-search ledger;
  **start an explicit data pipeline** (trades, context, fills → parquet) at the
  first live deposit so model retrains aren't starved.
- As capital/strategy grows, the first paid-tier decision is likely **finnhub
  premium** (news sentiment + relaxed rate limits) — gate it on a demonstrated
  signal that needs it, not on growth alone.

## 5. Hardware bottlenecks (condition-triggered)

**Current baseline (2026-08-01):** GPU1 RX 7900 GRE 16GB (qwythos 9B Q4,
~8.5GB RSS under load), GPU0 RTX 3070 8GB (qwen 7B), 31GB RAM (~19GB used,
11GB available), cycle ~24–58s.

| Trigger (condition, not date) | Action | Cost |
|---|---|---|
| 2 concurrent slots/serve saturate during peak cycles (>queueing observed) | Bump server `--parallel` + semaphore | +RAM (~1–2GB) |
| RAM available < ~4GB while Firefox/etc. run | Re-evaluate ctx (currently 8K) / drop a server | Headroom, fewer KV slots |
| Next model needs >16GB VRAM at Q4 (Ptolemy-2+ scale) | Move to 24–32GB card, or split layers across GPUs | GPU purchase |
| Fine-tune (Ptolemy) and live harness contend for GPU1 | Stagger training to off-hours; cap train threads | Scheduling, no new hw |
| RAG/embedding workload grows (codesage) | Dedicated small embed server or CPU/GPU split | Marginal |

**Deadline philosophy:** each row fires on its measured trigger, then gets a
dated plan. No calendar commitments.

## 6. Instrument unlocks (capital-gated)

| Account size | Instrument | Notes | Gate to open |
|---|---|---|---|
| **$100–300** | Crypto spot (kraken) | **Current** — 0.26% taker, no PDT | none (today) |
| **~$500–1k** | Kraken futures perps | 274 swaps via `ccxt.krakenfutures()`; liquidation risk needs size discipline + tighter SL | paper-validate perp fills + liquidation model first |
| **~$1–5k** | US stocks | $0.35 fixed fee starts to amortize; finnhub bars needed | stock paper A/B at $1k+ scale |
| **~$25k+** | US options / margin | PDT rule (25k) is the hard wall | far-future; revisit at ~$10k |

**Rule:** never unlock a class on paper only — each gate above requires both a
capital threshold **and** a walk-forward-validated strategy for that instrument.

## 7. Revision log

- **R1 · 2026-08-01** — Initial thesis: $300 min deposit confirmed; rule-based
  edge validated (+5%/yr OOS); engine at 24–58s cycles; funding/depth/FRED
  context live; hardware condition-triggers defined; instrument gates set.
