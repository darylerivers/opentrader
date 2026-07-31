# Research: Alpha sources absent from the current system

**Date:** 2026-07-31
**Question:** Which alpha source, absent from the current system, is the
highest-probability addition for a real-price paper trading system with 66
symbols across US stocks + crypto (kraken + finnhub feeds)?
**Method:** gap analysis against the codebase, then primary-source literature
(OpenAlex-indexed papers).

## 1. What the system already trades on

Confirmed by code inspection (`mot/`, `risk/`, `data/`, `training/`):

- **Time-series technical / regime:** ADX, Bollinger width, MA slope, volume
  ratio, HH/HL structure (`data/regime_classifier.py`) — regime is
  trending/ranging/volatile/bearish
- **Scenario teaching:** breakout, false-breakout, trend, mean-reversion,
  flash-crash, range-accumulation (`training/programmatic_teacher.py`)
- **Sentiment:** fear&greed, social cache, news cache
- **LLM debate:** ADIR bull/bear/risk on real prices
- **Risk:** Kelly, ATR stops, allocator, circuit breaker

Gap scan (`grep` for order-flow, lead-lag, carry, term-structure,
cross-sectional, cointegration across mot/risk/data/training/exchange):
**zero hits.** The following families are entirely absent.

## 2. Feasibility constraints from the exchange feeds

- `exchange/live.py` (kraken via CCXT): `fetch_ohlcv`, `fetch_ticker`,
  `fetch_tickers`, `fetch_order_book(limit=1)`. **No** funding rates, **no**
  full order-book depth wired.
- `exchange/stock_finnhub.py`: OHLCV + generic `_api_get` (can reach quotes /
  news / sentiment). No order flow.
- Consequence: **order-flow/liquidity-microstructure and carry/term-structure
  are NOT currently feedable.** The feasible families are **OHLCV-derived**:
  cross-sectional momentum, time-series momentum, lead-lag, and
  volatility-managed versions of each.

## 3. Primary-source evidence

### Cross-sectional momentum (CSMOM) — the canonical, most-cited alpha
- Jegadeesh & Titman (1993), *Returns to Buying Winners and Selling Losers*,
  JF — **11,542 citations** (OpenAlex). Buy past 3–12m winners, sell past
  3–12m losers; robust across markets/eras.
- Fama-French / Daniel-Moskowitz (2016), *Momentum Crashes*, JFE — documents
  momentum crash risk after market rebounds; argues for dynamic/vol-scaling.
- Compatible with existing regime classifier; directly rankable across the
  66-symbol universe with OHLCV the feeds already provide.

### Time-series momentum (TSMOM) — orthogonal to CSMOM
- Moskowitz, Ooi & Pedersen (2012), *Time series momentum*, JFE — **1,416
  citations**. Sign of own past return predicts continuation across 58
  instruments (equities, FX, commodities, bonds). Fits the per-symbol debate
  path the harness already runs.

### Crypto-specific support
- Liu & Tsyvinski (2021), *Risks and Returns of Cryptocurrency*, RFS — crypto
  returns have time-series momentum and a momentum factor structure, not
  equity-style factor exposure.
- Spillover literature (e.g. "Small things matter most", JIMF 2020): **BTC
  leads altcoin returns** — a lead-lag signal usable entirely on kraken OHLCV
  (BTC rank/return as a predictor for ETH/SOL/XRP/etc.).

## 4. Verdict / recommendation

Highest-probability addition: **cross-sectional momentum across the 66-symbol
universe, volatility-managed** (Jegadeesh-Titman ranking + TSMOM sign per
symbol + vol scaling to mitigate momentum crashes). Rationale:

1. **Feasible today** — pure OHLCV, already provided by kraken + finnhub.
   No new data contracts.
2. **Best evidence** — the single most-cited alpha in the literature
   (11.5k+ citations), robust across 30 years.
3. **Orthogonal to current stack** — the system has no cross-sectional
   ranking at all; it ranks nothing across symbols, only trades each symbol
   on its own signal. CSMOM is additive, not overlapping.
4. **Fit** — feeds the existing portfolio allocator (weights across symbols)
   and the ADIR debate (as a "cross-sectional" context feature).

Secondary candidate: **BTC→altcoin lead-lag** (Liu-Tsyvinski momentum +
spillover evidence) — also OHLCV-only, cheap to add, and the universe already
holds BTC + 7 altcoins.

Deferred (need new data): order-flow/microstructure, carry/funding.

## Sources

- Jegadeesh, N. & Titman, S. (1993). Returns to Buying Winners and Selling
  Losers. *Journal of Finance.* DOI 10.1111/j.1540-6261.1993.tb04702.x
- Moskowitz, T., Ooi, Y. & Pedersen, L.H. (2012). Time series momentum.
  *Journal of Financial Economics.* DOI 10.1016/j.jfineco.2011.11.003
- Liu, Y. & Tsyvinski, A. (2021). Risks and Returns of Cryptocurrency.
  *Review of Financial Studies.*
- Daniel, K. & Moskowitz, T. (2016). Momentum crashes. *Journal of Financial
  Economics.*
