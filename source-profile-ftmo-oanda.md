# FTMO US (x OANDA) — execution connector source

## Consume me
- **Purpose**: execute the harness's validated decisions on the FTMO US challenge (2-Step, Swing account type) via the **OANDA v20 REST API** — the sanctioned US-resident path, US-regulated, no MetaTrader, no Spotware, no geolocation workaround.
- **Auth**: OANDA personal access token (generated in the fxTrade Account Management Portal → "Manage API Access" → personal token). Sent as `Authorization: Bearer <token>`. **Never a username/password, never a MetaTrader credential.**
- **Sample call/load**: `curl -H "Authorization: Bearer $TOKEN" https://api-fxpractice.oanda.com/v3/accounts` (practice/demo) or `https://api-fxtrade.oanda.com/v3/accounts` (live). Python SDKs exist (e.g. `oanda-candles`, community `oandapyV20`).

## Kind: API
- **Base URL**: `https://api-fxpractice.oanda.com` (demo) / `https://api-fxtrade.oanda.com` (live), path prefix `/v3`.
- **Auth**: Bearer token (header). Personal access token from the AMP; token is a secret — store in the harness config like the other keys, never commit.
- **Endpoints** (developer.oanda.com/rest-live-v20):
  - `GET /v3/accounts` — list accounts (the FTMO US challenge account ID).
  - `GET /v3/accounts/{id}/summary` — balance, NAV, positions count.
  - `GET /v3/accounts/{id}/pricing?instruments=` — real-time bid/ask (quote stream via `stream` param or the pricing stream).
  - `POST /v3/accounts/{id}/orders` — create market/limit orders; **stop-loss + take-profit attached as order fields** (absolute prices or distances — the validated 12.28%/17.81% map to these).
  - `GET /v3/accounts/{id}/trades`, `PUT /v3/accounts/{id}/trades/{id}/close` — position management + exit (the 14-day-hold exits).
  - `GET /v3/instruments` — the FTMO US symbol list (EUR_USD, USD_JPY, US30 index, metals).
- **Pagination**: `page`/count params on list endpoints; the pricing stream is push.
- **Rate limits**: OANDA's v20 API is effectively unlimited for retail-frequency use; no published per-second cap that a daily-frequency system could hit (single-digit orders/day). FTMO's automation cap applies on the FTMO side, not OANDA's.
- **Errors**: HTTP status + a JSON `errorMessage` body; 401 = bad token, 404 = wrong account/endpoint, 400 = malformed order. Retry on 5xx with backoff; re-auth only on 401.
- **Goal depth**: connector — full: order placement (market, SL/TP), account/position queries, pricing for entry checks.

## Platform context (verified from ftmo.oanda.com + developer.oanda.com, 2026-08-06)
- **FTMO US** is the sanctioned entity for US residents (FTMO's own "Who can join FTMO?" directs US clients to ftmo.oanda.com). Legal name in the page schema: "FTMO US".
- OANDA Corporation is a **CFTC-registered FCM + RFED and NFA member (No. 0325821)** — the strongest trust signal in this research, and directly answers the user's platform-trust concern.
- Platforms for FTMO US: **MetaTrader 5 and TradingView** (via the OANDA Broker Profile). The OANDA v20 REST API is the automation surface — no MetaTrader product in the harness.
- **Swing account type** (2-Step) has no overnight/weekend hold restrictions; the evaluation phase is unrestricted regardless of type — our 14-day holds are clean. The news/close restrictions apply only to the funded Standard account (our `prop_entry_gate` is conservative-but-safe).
- FTMO US offers 2-Step and a Free Trial. Real US traders earn payouts through this entity (testimonials: Paul, USA — $500,180).

## Unknowns (the truth-teller)
- Whether the FTMO US challenge accounts expose OANDA v20 API access directly, or require the TradingView/MT5 path with the API token issued against an OANDA demo account the FTMO US account maps to — **the account-provisioning detail, to be resolved by opening the Free Trial and checking the Client Area/AMP**.
- The exact FTMO US instrument list (the site's Simulated Assets page exists; the symbol set was not fetched in this pass).
- Whether the OANDA token works for the FTMO US simulated (demo) accounts or only a personal OANDA demo — resolved by the Free Trial.
- FTMO US pricing (fees) for the challenge — the pricing page exists on the site; not fetched here.

## Connector shape (for the downstream builder)
Harness `_rule_primary_signals` / `prop_entry_gate` → a small `ftmo_us_connector` (Python, OANDA v20 REST) that holds the account token in the harness config, places market orders with the validated 12.28%/17.81% SL/TP as order fields, tracks trades via the trades endpoint, and mirrors fills back into the journal for the defect log. Daily-frequency cadence (single-digit orders/day) is trivial for the API and the FTMO automation budget.
