# FTMO cTrader + cTrader Open API (execution connector source)

## Consume me
- **Purpose**: execute the harness's validated decisions on an FTMO Challenge account (2-Step, Swing account type) via the cTrader Open API — no MetaTrader product anywhere in the chain (user's trust constraint).
- **Auth**: OAuth2 (cTrader ID / Spotware Connect developer app, client-credentials + access token). The user registers a developer app at connect.spotware.com; the token is issued per app. **Never a MetaTrader credential.**
- **Sample call/load**: `pip install ctrader-open-api` then a client that connects to the Open API WebSocket gateway, authenticates with the OAuth token, and places a market order via the protobuf `ProtoOACreateOrderReq`. Concrete SDK: the official `ctrader-open-api` Python package + `openapi-client-generated` protos.

## Kind: API
- **Base URL**: OAuth token endpoint `https://connect.spotware.com/oauth/token`; Open API WebSocket gateway `wss://demo.ctrader.com` / `wss://live.ctrader.com` (FTMO demo accounts connect to the cTrader demo gateway). Docs: `help.ctrader.com` (cTrader Open API), proto schemas in the `openapi-client-generated` package.
- **Auth**: OAuth2 access token (Bearer). Scope: trading + account info. Token issued per registered developer app; grant flow at connect.spotware.com.
- **Endpoints / interface**: WebSocket protobuf messages — `ProtoOAApplicationAuthReq`, `ProtoOAGetAccountsReq`, `ProtoOAExecutionEvent` (fills/positions), `ProtoOACreateOrderReq` (market/limit, SL/TP as absolute prices or offsets), `ProtoOAReconcileReq`, `ProtoOASpotEvent` (price feed). REST is used for OAuth only; all trading is the WS/protobuf surface. A single persistent WS session covers the whole connector (this is how the ≤2,000-request/day FTMO automation budget is trivially respected — one connection, not per-order polling).
- **Pagination**: n/a (event-stream model; positions/orders pushed as execution events).
- **Rate limits**: not published on the fetched pages — `unknown`. The FTMO cap (≤2,000 server requests/day) is far above the connector's needs (a daily-frequency system issues single-digit orders/day).
- **Errors**: protobuf `ProtoOAErrorRes` / `ProtoOAClientErrorRes` with error codes + descriptions over the WS; OAuth errors over REST (HTTP). Retry advice: reconnect on WS drop, resync via `ProtoOAReconcileReq`.
- **Goal depth**: connector — full: order placement (market, SL/TP), position/account queries, spot price feed for the rule's entry checks.

## Platform context (verified from ftmo.com/en/trading-platforms + FAQ, 2026-08-06)
- FTMO offers MT4, MT5, AND **cTrader**. cTrader Automate supports **C# and Python**; Open API is the integration surface.
- **Swing account type** has no overnight/weekend hold restrictions (our 14-day holds require Swing); 2-Step offers Swing (1-Step does not).
- **Evaluation phase (Challenge/Verification)**: no news-trading restriction and no hold restriction regardless of account type. The news/close restrictions apply only to Standard FTMO Accounts after funding. Our `prop_entry_gate` is therefore conservative-but-safe for evaluation and correct for the funded Standard stage.
- FTMO is demo-account/simulated-funds with real Rewards; 4.5M+ customers, $650M+ paid, 4.8/5 Trustpilot, Czech (FTMO s.r.o., VAT CZ699005540).

## Unknowns (the truth-teller)
- **US-residency restriction**: `open.ctrader.com` states Spotware services "are not available for citizens or residents of the USA." The user is US-based. Whether this blocks (a) the cTrader ID / Open API developer access used to build the connector, or (b) trading the FTMO cTrader demo account, is **unverified** — this must be tested/confirmed before building, and may force the MT5/EA path or a different firm if it blocks.
- Whether FTMO's cTrader demo servers expose the Open API gateway (standard cTrader servers do; FTMO-specific server names from the Client Area — `unknown` until the account exists).
- Exact WS gateway host for FTMO demo accounts (likely the standard cTrader demo host; confirm from the Client Area credentials).
- The cTrader symbol list for FTMO (EURUSD, USDJPY, indices, metals) — the FTMO symbols page is JS-rendered (`unknown` until fetched from an account session).
- Open API rate limits (not published on the pages fetched).
- The connector's host: the Open API is cloud-based (WS from anywhere), so this box is fine; whether the FTMO TOS requires a particular execution host is `unknown` (FTMO has no VPS/VPN ban — that's Topstep).

## Connector shape (for the downstream builder)
Harness `_rule_primary_signals` / `prop_entry_gate` → a small `ftmo_connector` service (Python, ctrader-open-api) that holds one WS session, places market orders with the validated 12.28%/17.81% SL/TP as offsets, tracks positions via execution events, and mirrors fills back into the harness journal for the defect log. The daily-frequency cadence (single-digit orders/day) sits far under the automation cap.
