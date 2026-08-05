# Expert Data Sources — Recommendation (Sentiment / Crypto / International)

**Date:** 2026-08-05
**Author:** research agent (OpenTrader)
**Status:** live-verified where possible. Every endpoint in this doc was probed from this host on 2026-08-05 unless flagged otherwise. No recommendation requires a paid plan.

## How this was verified

- Live `curl`/Python probes against every public endpoint (HTTP codes + sample payloads).
- Official docs / GitHub READMEs fetched for rate limits and coverage (cited inline).
- Cache contract mirrors `arena/candidates_macro.py` (`data/setup_search/macro_series.pkl`, 24h TTL, graceful zero/flag degradation on failure).

---

## 1. SENTIMENT expert

**Goal:** a free, reliable news/social/alt feed that can plausibly carry signal for US equities, feeding 2-5 daily-bar features.

> Context: the FinBERT-on-real-tweets evaluation produced null results. Recommendation below therefore leads with **volume / tone-of-volume / dispersion** features (counts, z-scores, volatility-of-sentiment) rather than another raw headline-score edge, and reuses Finnhub's key already in `data/connections.json`.

### Candidate-by-candidate verdict

| Source | Free? | Verdict |
|---|---|---|
| **(c) GDELT 2.0 DOC** | Yes, no key | **PRIMARY (market/index level).** Free, no key, 15-min updates, per-article tone. Rolling **3-month** search window — forward-fill only, not a 5y backfill. |
| **(e) Finnhub news** | Yes (existing key) | **PRIMARY (per-ticker).** `company-news` verified live; free tier ≈ last **~6 months** of history. `news-sentiment` / `stock/sentiment` are **paid** (403/404 verified). |
| **(a) StockTwits** | Yes, no key | **SECONDARY.** Public read endpoints verified live (no auth). Retail message volume + sparse user-tagged sentiment. Recent-only (~30d via cursor). |
| **(b) Reddit / Pushshift** | Official API free (OAuth) | **NOT recommended.** Pushshift is **defunct** — `api.pushshift.io` returns HTTP 403 `{"detail":"Not authenticated"}`, `elastic.pushshift.io` is dead, `pushshift.io` now redirects to a `/signup` wall. Official Reddit API requires OAuth2 script app, ~60-100 QPM, no structured per-ticker signal, heavy moderation noise. |
| **(d) NewsAPI.org** | Free dev tier | **REJECT.** Developer plan = 100 req/day, **only 1 month of history**, 24h article delay, dev-only (no production use). |
| **(f) Other free** | — | Alpha Vantage `NEWS_SENTIMENT` (25 req/day free, ~1y history, scored) — redundant vs Finnhub, low quota. Marketaux free (100 req/day, ~7 days history) — too shallow. Alternative.me (crypto-only, already in repo). **All rejected** for the equities expert. |

### Winner endpoints

**GDELT 2.0 DOC** — https://api.gdeltproject.org/api/v2/doc/doc
- Auth: none. Format: `json`/`csv`. Updates every 15 min.
- Rolling search window: **last 3 months** (`STARTDATETIME` must be within 3mo).
- Key params: `query`, `mode=artlist|timelinevol|timelinevolraw|timelinetone`, `format=json`, `maxrecords` (≤250), `timespan=7d`, `startdatetime`/`enddatetime`, `sort=datedesc`.
- Per-article fields (artlist): `title`, `url`, `domain`, `sourcecountry`, `language`, `publisheddate`, `seendate`, `tone` (−100..+100), `themes`, `imagecount`, `cameoeventcount`, `quotedieventcount`.
- **Rate limit:** 1 request per **5 seconds** (this host got throttled with exactly that message; official policy: “limit requests to one every 5 seconds”). Plan one request per 10-15s and retry-with-backoff on the throttle response.
- Docs: https://blog.gdeltproject.org/gdelt-doc-2-0-api/ · https://www.gdeltproject.org/api.html

**Finnhub news** — `https://finnhub.io/api/v1/company-news?symbol=AAPL&from=YYYY-MM-DD&to=YYYY-MM-DD&token=KEY`
- Auth: token (`FINNHUB_API_KEY`; key present in `data/connections.json`).
- Free tier rate limit: **60 calls/min** (Finnhub free tier). Fields: `datetime` (epoch), `headline`, `summary`, `source`, `related`, `category`.
- Historical depth on free tier: ≈ last **6 months** (verified: AAPL Dec 2025 → 240 articles; Jun 2025 → 0). Backfill what exists, then forward-fill.
- Market-wide feed also free: `https://finnhub.io/api/v1/news?category=general|crypto|business&minId=0&token=KEY` (verified live, 100 articles/call).
- **Paid-gated** (verified 403/404 on free key): `/stock/sentiment`, `/news-sentiment`, `/stock/insider-sentiment`.
- Docs: https://finnhub.io/docs/api/company-news

**StockTwits** — `https://api.stocktwits.com/api/2/streams/symbol/{SYM}.json`
- Auth: none for public reads. Returns `messages[]` with `id`, `created_at` (ISO), `body` (`$AAPL` cashtags), `symbols`, sparse `entities.sentiment` (`{"basic":"Bullish|Bearish|Neutral"}` — only present when the author tags it).
- Trending: `https://api.stocktwits.com/api/2/trending/symbols.json` (verified live).
- Rate limit: historically documented ~**200 req/hour unauthenticated**; not re-verified against a live docs page, but 8 rapid calls returned 200 with no 429. Plan hourly cadence + backoff.
- Depth: recent messages only; paginate with `cursor` (~30 days reachable).

### Feature plan (daily-bar value-head inputs)

Per-symbol (Finnhub + StockTwits), computed on the master daily calendar, forward-fill:

| # | Feature | Definition |
|---|---|---|
| 1 | `fh_count_z7` | rolling 7d Finnhub company-news count, z-scored vs trailing 90d |
| 2 | `fh_tone_z7` | rolling 7d mean headline tone (lexicon or FinBERT), z-scored vs 90d |
| 3 | `st_vol_z7` | rolling 7d StockTwits message count, z-scored vs 90d |
| 4 | `st_bear_frac7` | rolling 7d fraction of **user-tagged** bearish messages (0 if no tags) |
| 5 | `vol_of_sent` | 21d rolling std of daily mean tone (both sources) — sentiment dispersion |

Market-level (GDELT, query = regime symbol + top universe terms):
- `gd_count_z7` — 7d article-count z-score, `gd_tone_z7` — 7d mean tone z-score, `gd_vol_tone21` — 21d tone dispersion, `gd_count_ratio7` — count_t / trailing-90d mean.

### Data residency & degrade (SENTIMENT)

- **Cache to disk:** raw article/message JSONL per day → `data/expert/sentiment/raw/{date}.jsonl`; aggregated daily features → `data/setup_search/sentiment_series.pkl` (mirror `macro_series.pkl`, 24h TTL).
- **Refresh cadence:** GDELT 1×/15-30min for the live window; Finnhub + StockTwits 1×/hour, appended daily.
- **Degrade:** if all three sources fail and no cache → zero the sentiment columns **and** set a `sent_ok` coverage-flag column so the arena can mask (same contract as `candidates_macro.py` zeroing macro columns). If GDELT alone fails, keep Finnhub/StockTwits. If the raw backfill window is short, rows outside coverage are masked, not hallucinated.

---

## 2. CRYPTO expert

**Goal:** 5y daily OHLCV for BTC, ETH, SOL (USDT-quoted) with a free key or none.

### Candidate-by-candidate verdict

| Source | Free? | 5y daily depth? | Verdict |
|---|---|---|---|
| **(b) Binance public data archive** (`data.binance.vision`) | Yes, no auth, no geo-block | **Yes** — monthly zips cover 2017+ for all symbols | **WINNER.** |
| (a) **Kraken public OHLC** | Yes, no auth | **No** — hard cap of 720 candles; docs: “older data cannot be retrieved, regardless of the value of `since`” | REJECT for 5y (use only as a recent-window fallback). |
| (b2) **Binance REST `klines`** | Yes | Yes (needs ~3 calls/symbol) | REJECT — **geo-blocked from US IPs** (verified: “Service unavailable from a restricted location”). |
| (c) **CoinGecko `market_chart`** | Yes (no key) | **No** — `days=365` works (366 pts), `days=2000` and `/range` return empty; ~5 rapid calls then HTTP 429 | REJECT for 5y. |

### Winner endpoint(s) — exact URLs

**Backfill (one-time, ~60 small files/symbol):**
```
https://data.binance.vision/data/spot/monthly/klines/BTCUSDT/1d/BTCUSDT-1d-2021-08.zip   (also ETHUSDT, SOLUSDT)
```
**Incremental (daily):**
```
https://data.binance.vision/data/spot/daily/klines/BTCUSDT/1d/BTCUSDT-1d-2026-08-04.zip
```
- Checksums: same path + `.CHECKSUM` (sha256sum).
- Symbols: `BTCUSDT`, `ETHUSDT`, `SOLUSDT` — the USDT quote **is** the stablecoin leg; if you also want Tether’s own peg series, that is not a Binance spot pair (use CoinGecko `tether` or Kraken `USDTUSD`).
- CSV columns (headerless, 12 cols): `open_time, open, high, low, close, volume, close_time, quote_asset_volume, n_trades, taker_buy_base_vol, taker_buy_quote_vol, ignore`.
- **Gotcha — timestamp precision:** Binance spot archive timestamps switch from **milliseconds (13-digit) to microseconds (16-digit) for data from 2025-01-01 onward**. Parse by digit-length or by calendar, else the 2025+ tail misaligns to 1970-01-01.
- Publication: monthly zips available first Monday of the month; daily zips the next day (today’s daily zip 404s until then — verified).
- Docs: https://github.com/binance/binance-public-data (README, klines schema, checksums, updates log).

**Fallback (partial, last ~2y only):** `https://api.kraken.com/0/public/OHLC?pair=XBTUSD|ETHUSD|SOLUSD&interval=1440` (no auth; verified live; `since` ignored for backfill — official: max 720 most-recent entries). Pairs `XBTUSD`, `ETHUSD`, `SOLUSD`. Docs: https://docs.kraken.com/api/docs/rest-api/get-ohlc-data

### Data residency & degrade (CRYPTO)

- **Cache to disk:** rebuilt OHLCV → `data/setup_search/crypto_ohlcv.pkl` (same contract `setup_search/crypto_leg.py` already loads; keep `BTC-USD`-style aliases so `REGIME_SYM="BTC-USD"` and the engine are untouched).
- **Refresh cadence:** rebuild full 5y from monthly zips on a 7-day TTL; append yesterday’s daily zip each day.
- **Degrade:** archive unreachable → serve last full snapshot (no partial), optionally patch the trailing ~2y from Kraken; never fail the arena iteration (mirror the `candidates_macro.py` warning+zero path).

---

## 3. INTERNATIONAL expert

**Goal:** international equity indices + FX + commodities so the model sees non-US regimes. **All 12 candidate yfinance tickers verified live on 2026-08-05 with full 5y daily data.**

### Verified yfinance (Yahoo chart) coverage — 5y daily, 2021-08-05 → 2026-08-05

| Ticker | n (days) | non-null close | Notes |
|---|---|---|---|
| `^N225` | 1223 | 1223 | Nikkei 225 |
| `^FTSE` | 1262 | 1262 | FTSE 100 |
| `^GDAXI` | 1275 | 1275 | DAX |
| `^HSI` | 1227 | 1227 | Hang Seng |
| `^GSPC` | 1255 | 1255 | S&P 500 (regime anchor) |
| `^VIX` | 1305 | 1256 | **has nulls** (holiday/subscription) — dropna/ffill |
| `EEM` | 1255 | 1255 | MSCI EM ETF (dividend-adjusted) |
| `EFA` | 1255 | 1255 | MSCI EAFE ETF (dividend-adjusted) |
| `EURUSD=X` | 1306 | 1300 | ~6h UTC offset — normalize to UTC date |
| `USDJPY=X` | 1306 | 1300 | same |
| `GC=F` | 1260 | 1257 | gold futures |
| `CL=F` | 1260 | 1257 | WTI futures |

**Gotchas (verified):**
- Yahoo chart API **rate-limits aggressively** (bare URL hit returned HTTP 429). Use a browser-ish `User-Agent` header and **1-2s spacing between tickers** (all 12 succeeded with this).
- The repo pattern in `arena/candidates_macro.py:74` (direct `query1.finance.yahoo.com/v8/finance/chart/…?range=5y&interval=1d`) is exactly the right endpoint; yfinance wraps the same API.
- Indices are price-return only (no adjustment needed); `EEM`/`EFA` are ETF-adjusted. FX/futures rows carry a few hours’ UTC offset — normalize, then `reindex(ffill)` onto the US master calendar (the arena already aligns non-US sessions this way).

### Free fallbacks / cross-checks

- **(a) FRED FX** (key already used by the repo): `DEXJPUS` (USD/JPY), `DEXUSEU` (EUR/USD → invert), `DEXCHUS` (CNY/USD), `DEXBZUS` (BRL/USD). Daily, full decades of history.
  `https://api.stlouisfed.org/fred/series/observations?series_id=DEXJPUS&api_key=KEY&file_type=json&frequency=d`
  (Series pages: https://fred.stlouisfed.org/series/DEXJPUS etc. Not API-probed here — no FRED key in this shell’s env; series are standard.)
- **(b) ECB SDMX** (verified live, no key): `https://data-api.ecb.europa.eu/service/data/EXR/D.USD.EUR.SP00.A?format=csvdata&startPeriod=2026-07-01&endPeriod=2026-08-05`
  ECB reference rates, daily, full history since 1999, CSV/JSON. USD/JPY via `EXR.D.JPY.USD.SP00.A`. Docs: https://data.ecb.europa.eu/help/api/statistical-data
  Caveat: ECB FX is a once-a-day ~16:00 CET reference rate (T+1 publication) — fine for daily bars, not for intraday.

### Recommended universe (12 tickers)

```
^N225  ^FTSE  ^GDAXI  ^HSI  ^GSPC  ^VIX  EEM  EFA  EURUSD=X  USDJPY=X  GC=F  CL=F
```
Optional adds with same 5y profile: `^KS11` (KOSPI), `^BSESN` (Sensex), `^AXJO` (ASX 200). All fetched with the `query1.finance.yahoo.com` chart URL + UA header + 1-2s spacing.

### Data residency & degrade (INTERNATIONAL)

- **Cache to disk:** `data/setup_search/international_series.pkl` (mirror `macro_series.pkl`, 24h TTL).
- **Refresh cadence:** 24h, aligned with the arena’s daily cache.
- **Degrade:** Yahoo down → FX subset from ECB SDMX (`EURUSD=X`, `USDJPY=X` via ECB/FRED), keep last index/commodity snapshot, mask missing columns; never fail the iteration.

---

## Endpoints I could NOT fully verify (web access issues)

- **GDELT live JSON payload** — throttled at the 1-req/5s rule from this shared egress IP on every probe (the throttle message itself confirms endpoint + policy). Params/fields taken from the official docs; endpoint format matches documented examples.
- **CoinGecko free-tier exact req/min** — docs URL 404’d; empirically ~5 rapid calls then HTTP 429 (so ≤5/min effective).
- **Kraken public rate-limit page** — docs URL 404’d (moved); OHLC behavior verified against the official OHLC page + live probe. No throttle observed on rapid OHLC calls.
- **StockTwits documented req/hr** — developers-docs URLs 404’d; endpoint verified live, no 429 on 8 rapid calls (figure ~200/hr unauth per historical docs).
- **Reddit current QPM** — official docs not fetchable; archived wiki says 60 QPM per OAuth client (current dev docs report 100). Flagged as “roughly 60-100.”
- **Finnhub `stock/sentiment` + `news-sentiment`** — verified **unavailable on the free key** (404/403). Do not build on these.
- **FRED `DEX*` FX series** — could not query without a key in this shell; series are standard/active on the cited FRED pages.
- **NewsAPI live call** — no key present; free-tier limits confirmed from the official pricing page (100 req/day, 1-month history, 24h delay).

## Bottom line

- **SENTIMENT:** GDELT DOC 2.0 (market volume/tone, free, no key, 1-req/5s) + Finnhub `company-news` (per-ticker, existing key, ~6mo backfill) + StockTwits (retail volume, no key). Features = z-scored counts, tone, and 21d tone dispersion; mask un-backfilled rows.
- **CRYPTO:** Binance public data archive monthly klines zips (`BTCUSDT`/`ETHUSDT`/`SOLUSDT`) for the clean 5y backfill — free, no auth, no geo-block; parse the 2025+ microsecond timestamps; Kraken as ~2y fallback.
- **INTERNATIONAL:** all 12 yfinance tickers verified 5y; Yahoo chart via `query1` + UA header + 1-2s spacing; ECB SDMX and FRED `DEX*` as free FX fallbacks.
