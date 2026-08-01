# Research: Leveraged and exotic instruments by account size

**Ticket:** Leveraged and exotic instruments by account size
**Date:** 2026-07-31
**Method:** Live exchange-API verification (CCXT kraken + krakenfutures already
in the codebase) + finnhub capability probe + documented regulatory minimums.

## Finding 1 — Crypto spot (current, $100–300 viable)

Kraken spot exchange exposes **1,428 spot markets** via the existing CCXT
integration (`exchange/live.py`). Already live in the system today.

- Fees: maker 0.16% / taker 0.26% (%-based — scales cleanly to $50–300)
- No leverage on spot; no minimum-balance barrier
- **Conclusion: spot crypto is the correct first-account venue at $100–300**
  (matches the map's Fee-realism decision)

## Finding 2 — Kraken Futures: perps + dated futures (next unlock)

**Kraken Futures is a separate CCXT exchange** (`ccxt.krakenfutures()`), NOT
reachable through the spot endpoint. Verified live:

- **274 perpetual swaps** (BTC/USD:USD, ETH/USD:USD, SOL/USD:USD, ...)
- **20 dated futures**
- Same CCXT library already in the codebase — integration is an exchange
  module, not a new dependency

Futures/leverage realities:
- Leverage up to 50x on some perps (venue-dependent; kraken futures offers
  up to 50x on BTC, less on alts)
- Funding-rate carry is an *additional* P&L term (positive funding when longs
  pay shorts) — this is the lead-lag/carry alpha family from the earlier
  research (alpha-cross-sectional-momentum.md)
- Fee schedule is %-based (taker ~0.02–0.05% depending on tier), still
  small-account friendly
- **Liquidation risk**: leverage on a $100–300 account means a small adverse
  move wipes the position — capital threshold to unlock should be governed by
  the risk manager's max_drawdown, not venue minimums

## Finding 3 — US equities: options + margin (needs larger capital)

Finnhub (data) routes execution through IBKR. The finnhub free tier:
- `/stock/candle` returns **403 on free tier** (premium only) — so even the
  data side of advanced stock instruments is gated today
- No options chain endpoint exercised in the current code

IBKR realities (documented, not API-verified here):
- **Fixed per-trade fees** ($0.35 stock, ~$0.65/contract options) — the
  small-account killer the map already flags
- Options/minimums: IBKR has no hard minimum for a cash account, but the
  **Pattern Day Trader (PDT) rule** applies to US margin accounts: $25,000
  minimum to make >3 day-trades/week — a hard wall below that for active
  options/margin trading
- Below $25k, a US stock account is effectively cash-limited (T+1 settlement,
  no margin) — so leveraged US equity instruments are **structurally off the
  table until ~$25k**, not just fee-inefficient

## Finding 4 — Account-size gating summary

| Instrument | Venue | Min viable | Gating factor |
|---|---|---|---|
| Crypto spot | kraken | **$50–300** ✅ | none — % fees |
| Crypto perps/futures | krakenfutures | ~$500–1k | liquidation risk, not venue min |
| US stocks (cash) | finnhub→IBKR | ~$1k+ | $0.35 fixed fee drag |
| US options/margin | IBKR | **~$25k** | PDT rule + margin regs |
| Commodities/FX | IBKR | ~$5k+ | fixed fees, futures min |

## Recommended roadmap for the evolution thesis

1. **$50–300 (now):** spot crypto only — this map's validation
2. **~$500–1k:** krakenfutures perps — adds carry/leverage alpha, but gate by
   risk-managed max_drawdown, not venue minimums
3. **~$1–5k:** add US stocks (cash) once the $0.35 fixed fee is <1% of
   position
4. **~$25k:** US options + margin unlock (PDT wall clears)

## Sources

- Verified live via `ccxt.kraken()` / `ccxt.krakenfutures()` (1,428 spot /
  274 perp + 20 future markets)
- Finnhub free-tier 403 on candle API (live probe)
- SEC FINRA Pattern Day Trader rule: $25,000 minimum equity for PDT
  designation (well-documented regulatory standard)
