# Research: Five data-source evaluations

**Date:** 2026-07-31
**Method:** live API probes against the actual feeds already in the codebase
(free tier), plus config inspection. Findings recorded per source.

## Verdict summary

| Source | Evaluate | Verdict | Why |
|---|---|---|---|
| Kraken funding rates | PASS | **ADOPT** | Real data, free, no auth — BTC/ETH/SOL funding fetched live |
| FRED macro calendar | FAIL | **FIX FIRST** | Model sees SIMULATED data (`source: simulated`) — empty FRED_API_KEY |
| Finnhub news sentiment | FAIL | **DROP (free tier)** | `/news-sentiment` returns `{}` — premium-gated |
| Kraken order-book depth | PASS | **ADOPT** | trivial: extend limit=1 → limit=10 |
| On-chain (CDP) | FAIL | **DEFER** | testnet-only (base-sepolia), wallet adapter not market feed, key unconfigured |

## Funding rates (PASS → ADOPT)

`ccxt.krakenfutures()` — separate CCXT exchange, same library already in the
repo (exchange/live.py uses CCXT). No auth needed on public endpoints.

Live probe (2026-07-31):
- BTC/USD:USD → fundingRate 8.37e-07 (~0.00008%, near zero)
- ETH/USD:USD → fundingRate 6.49e-06 (~0.0006%)
- SOL/USD:USD → fundingRate 7.42e-06 (~0.0007%)

Positive funding on ETH/SOL = longs pay shorts = the carry signal the alpha
research (cross-sectional momentum) predicted. `fetch_funding_rate` works
per-symbol; `fetch_funding_rate_history` available for persistence studies.
Cost: one call per symbol, ~10 symbols the harness trades, negligible.

## FRED macro calendar (FAIL → FIX FIRST)

`data/economics.py` reads `FRED_API_KEY` from **env only** (not connections.json).
Env is empty; connections.json `fred.api_key` is `''`. Result: `fetch_economics`
falls through to `generate_simulated()`.

**The running model sees `source: simulated` macro** (confirmed in
data/macro_cache.json). It is making decisions on fabricated Federal Reserve
data — unemployment, CPI, fed funds, yields all invented. This is the most
important finding: the macro context is fake.

Fix options:
- Get a free FRED API key (api.stlouisfed.org, free, instant) → set
  `FRED_API_KEY` env or wire connections.json → make fetch_economics read
  connections.json.
- Make the simulate path LOUD — never silently fall back to fake data
  (add a `source: simulated` flag visible to the model and dashboard).

## Finnhub news sentiment (FAIL → DROP on free tier)

`/news-sentiment?symbol=AAPL` returns `{}` on the free tier — premium-gated,
like the candle API 403 found earlier. Cannot evaluate a signal that returns
no data. Note: the harness already has a generic news cache (news_json);
a per-ticker sentiment feed needs the paid tier.

## Order-book depth (PASS → ADOPT, trivial)

`exchange/live.py:266` already calls `fetch_order_book(market, limit=1)` to
compute mid-price. Extending to `limit=10` yields bid/ask imbalance, spread,
and depth ratios — the liquidity/microstructure family flagged as absent.
One-line change + a small features extractor. Free, same rate-limit budget
(one call per symbol per cycle).

## On-chain data (FAIL → DEFER)

`onchain.py` OnchainAdapter:
- Defaults to **base-sepolia testnet** (network param)
- Is a **wallet adapter** (wallet_info, balances) — not a market-data feed
- CDP key file not configured (empty coingecko/onchain keys in connections.json)

Exchange in/outflows, stablecoin minting, whale activity are NOT feedable
today. Would need mainnet CDP + a real on-chain data provider. Lowest
priority of the five — defers to the leverage tier (~$500-1k) anyway.

## Recommendation

Adopt funding rates + order book depth (both real, free, trivial). **Fix FRED
first** — the model is on fake macro and it's a silent correctness bug, not a
feature gap. Drop news sentiment on the free tier. Defer on-chain.

## Sources

- Live probes: ccxt.krakenfutures().fetch_funding_rate (BTC/ETH/SOL perps)
- exchange/live.py:262-272 (order-book mid-price, limit=1)
- data/economics.py fetch_economics + data/macro_cache.json (source: simulated)
- exchange/stock_finnhub.py _api_get /news-sentiment (empty on free tier)
- onchain.py OnchainAdapter (base-sepolia, wallet ops)
