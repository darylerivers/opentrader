# Prop-Firm Challenge Research — Feasibility for the OpenTrader Daily Momentum System

**Date:** 2026-08-05
**Author:** research agent (OpenTrader)
**Status:** primary-source verified where marked. Everything below was fetched live from the firm's own site, TOS, help center, or an archived copy of the firm's own page (Wayback Machine) on 2026-08-05. Anything not verifiable from a primary source is explicitly flagged.

**Target system profile (given):** daily-frequency, long-only momentum; ~2–4 trades/month; 14-day average hold; 12.28% stop / 17.81% target; SPY-regime filter; ~68% win rate.

**Headline finding:** four of the five headline firms are legal for our automated system to trade (with conditions); **none of the futures firms allows 14-day holds** (Topstep and TradeDay are day-trading-only; TradeDay explicitly), so the decisive constraints are (1) hold rules and (2) per-firm automation approval mechanics. The equities-capable credible option is **Trade The Pool** (5% group / The5ers family); E8 Markets also lists US stocks but could not be fully vetted in this pass.

---

## 0. The automation policy landscape — read this first

Every firm in this report uses the same boilerplate AI/software clause, which does **not** ban AI or bots outright; it bans exploitation. Quote (Topstep ToU §27, identical wording appears in FTMO, FundedNext, The5ers, TradeDay TOS):

> "Using any software, artificial intelligence, ultra-high speed, or mass Data entry which might manipulate, abuse, or give User an unfair advantage while using the Site or Services"

The practical reading: a daily-frequency long-only system is not "manipulative," but each firm adds its own *process* requirements and each reserves **sole discretion** to classify conduct. Per-firm verdicts:

| Firm | Automation verdict | Binding mechanism |
|---|---|---|
| Topstep | **Allowed** (explicit) | No VPS/VPN allowed on accounts; day-trading only |
| FTMO | **Allowed** (explicit) | < 2,000 server requests/day (hyperactivity cap) |
| FundedNext | **Allowed with paid add-on** | EA + VPS each require purchased add-on (MT4/MT5 only) |
| Apex | **Unknown** (User Agreement behind login — not publicly fetchable; live site 403s non-browser clients) | flagged |
| The5ers | **Allowed with prior written approval** | Own-code EAs only; approval at company discretion |
| TradeDay | **Self-built OK, third-party ATS banned**; but day-trading-only | no overnight holds |
| Trade The Pool | **Allowed in beta** | SignalStack integration; ≤2 req/min; approval reserved |

---

## 1. Topstep (futures)

**Challenge structure (Trading Combine®; verified — help.topstep.com/articles/8284197, 8284204):**
- One rule, two objectives: never breach the Maximum Loss Limit (MLL); reach Profit Target; keep best single day below 50% of Profit Target (Consistency Target).
- MLL (Trailing Max Drawdown): **$2,000 on $50K, $3,000 on $100K, $4,500 on $150K** (4%/3%/3%). Trailing: rises with end-of-day balance, never falls, **locks permanently at starting balance**. Monitored intraday on unrealized P&L; breach = immediate liquidation.
- Daily Loss Limit (DLL): separate objective; breach = soft breach (auto-flattened, paused until next session), not a rule violation (ToU §Definitions "Soft Breach").
- No time limit; can pass in as few as 2 days; no minimum trading days.
- Max position size 5 contracts / 50 micros on $50K (10:1 micro:mini).
- Fees: paid per Trading Combine subscription; exact price table on site (not captured — flagged). XFA (Express Funded) activation fee; payout path 3–5 days; Instant Payouts up to $12,000; 90/10 split; Back2Funded reactivation.

**Instruments:** Futures only — CME, COMEX, NYMEX, CBOT. "Topstep traders are prohibited from trading Stocks, Options, Forex, Spot Cryptocurrency, and CFDs" (disclosures footer, verified).

**Automation policy — VERBATIM (help article "Trading Combine Parameters", updated 2026-06-24):**
> "Can I use automated trading strategies? **Yes, with conditions.** Topstep won't help set up or troubleshoot automated strategies, and no exceptions are made for errant trades or malfunctions. Test on your Practice Account first and review Prohibited Conduct and Prohibited Trading Strategies before going live. You can also use a trade copier to duplicate trades across multiple accounts."

But ToU §27 Prohibited Conduct includes: "Performing… trades… by engaging in any short term or high frequency trades or simultaneously entering into opposite positions" and the AI/software clause quoted in §0. ToU §28 (Other Prohibited Uses), **verbatim**: "Using any VPN or VPS on Accounts is strictly prohibited and may result in account termination and forfeiture of profits." Also: all positions **MUST be closed prior to 3:10 PM CT** (auto-flatten ~10s before close); no overnight/weekend holds; trading only in normal electronic hours; no positions within 2% of lock limit.

**Weekend/swing holds:** **Not possible.** Day-trading only (verified ToU §27).

**Regulation & vetting:** Topstep LLC is a private Delaware LLC. The affiliate **Topstep Brokerage LLC is CFTC-registered as an IB and NFA member (NFA ID 0567079)** — verified from Topstep's own disclosures; Topstep LLC itself does not claim NFA membership in its disclosures (direct NFA BASIC lookup was blocked from this host — flagged). Published 2025 stats (their own disclosure): 16.8% of Trading Combines passed; 51.8% of participants funded at least once; **33.3% of funded-level participants received a payout**; 0.71% called up to Live. Long track record (founded 2012 as Topstep Trader); no scam allegations in primary materials (secondary review sites not exhaustively checked — flagged). **Scam-risk: Low.**

**Feasibility for our system:** **Poor.** Automation is explicitly allowed, but (a) 14-day holds are impossible (daily flatten at 3:10 PM CT), (b) VPS usage is banned, which is how most automated futures execution runs, (c) the 4% trailing MLL with a 12.28% stop forces ~1/3 sizing. Only viable if the system is rebuilt as intraday. Not recommended for this system as-is.

---

## 2. FTMO (forex/CFD)

**Challenge structure (verified — ftmo.com/en/trading-objectives, updated 2026-05-13; how-it-works page):**
- **2-Step** (recommended for us): Phase 1 Challenge — 10% profit target, 5% max daily loss, 10% max loss (**static**), min 4 trading days (counted by days with a position *opened*), **no time limit**. Phase 2 Verification — 5% target, same risk limits, same min days. Then FTMO Account (no target, continuous risk compliance), up to 90% reward split, 100% fee refunded with first reward withdrawal. Sizes $10K–$200K.
- **1-Step**: 10% target, **3% max daily loss**, **10% max loss = end-of-day trailing** on 00:00 CE(S)T closing balances, plus **Best Day Rule** (see below). No time limit.
- **Consistency rule — IMPORTANT UPDATE:** the old "30% consistency" rule has been **replaced by the "Best Day Rule"** (verified): "your **Best Day** does not represent more than **50% of your Positive Days' Profit**" (closed-trade P&L, days measured 00:00 CE(S)T). Applies to **1-Step only**; the 2-Step has no consistency rule. Exceeding it is not a breach — you just keep trading until it passes.
- No time limit on either product ("No time limit" — verified). 60-day inactivity? (not found in fetched pages — flagged; FTMO historically has no inactivity expiry).

**Instruments (flags):** FX, metals, indices, commodities, crypto CFDs per FTMO symbols page; the ticker table is JS-rendered and could not be captured; **whether US share CFDs are still offered could not be verified** in this pass (flagged).

**Automation policy — VERBATIM (ftmo.com/en/forbidden-trading-practices, updated 2026-02-02):**
> "perform simulated trades that are operated or managed by automated robots / EAs (Expert Advisors) which cause the trading account to become hyperactive in the sense of an excessive number of **more than 2,000 server requests per day** on individual simulated trades or pending orders being opened, modified, or closed, causing overload of the trading server"

Plus the standard AI clause (§0), and: gap trading banned — no *opening* trades "when major global news… are scheduled" or "two hours or less before a relevant financial market is closed for at least two hours" (this is a weekend/FX-close entry ban, not a hold ban). No copy-trading clause in the Feb-2026 list (third-party account access banned under "Personal Use").

**Weekend/swing holds:** Allowed. FAQ (verified): overnight/weekend restrictions apply only to the **Standard** account type on the FTMO Account stage; **Swing account type has no hold restrictions**, and **no hold restrictions apply during the Evaluation Process at all**.

**Regulation & vetting:** FTMO s.r.o. (Czech company, VAT CZ699005540, founded 2015); accounts are demo/simulated with real-money rewards; not a regulated broker (their own model disclosure). Self-reports $650M+ rewards, 4.5M+ customers, Trustpilot 4.8/5 with Trustpilot link. Regulatory-probe claims circulating in secondary media could not be confirmed from primary sources (flagged). **Scam-risk: Low.**

**Feasibility for our system:** **Best structural fit of the FX group.** On the 2-Step: no consistency rule, no time limit, holds allowed (Swing), 5% daily loss vs our 12.28% stop → size ≤ ~40% of account per trade; 10% static max loss accommodates 2 concurrent stop-outs (≈7.4% at 30% sizing). ~68% win-rate, 17.81% winners → 10% target in ~4–6 weeks of live trading, 2–4 weeks of calendar time at 2–4 trades/month... (min 4 trading days satisfied on entry days). The news/gap *entry* ban is the main operational constraint (no entries within ±5 min of high-impact events or within 2h of a ≥2h market close — i.e., late Friday). The 1-Step's Best Day Rule would bind hard (our winners cluster: a 4.3% day vs ~7% cumulative positive days could sit near 50–60%) — **prefer the 2-Step** or size winners down on the 1-Step.

---

## 3. FundedNext (forex CFDs + futures)

**Challenge structure (verified — fundednext.com/en/general-rules/cfds/trading-objectives):**
- **Stellar 1-Step:** 10% target, **3% daily loss**, **6% max loss (static)**, min 2 trading days, no time limit (60-day inactivity deactivation).
- **Stellar 2-Step:** 8% → 5% targets, 5% daily loss, 10% max loss (static), min 5 trading days, no time limit.
- Stellar Lite: 8%→4%, 4% daily, 8% static, 5 days. Stellar Instant: no target, no daily loss, 6% **trailing** max loss, no min days.
- Reward share 80% standard, up to 90% Scale-Up, 95% add-on; 15% challenge-phase reward (1-Step/2-Step only).
- **No consistency rule to pass.** (A 40% consistency rule exists only as an opt-in under the 95%-split "On-Demand Performance Reward" if gambling behavior is flagged; a 1% risk rule may be imposed.)

**Automation policy — VERBATIM (what-is-allowed page):**
> "Expert Advisors (EAs) and VPS: Both EAs and VPS are allowed across all models and account types. **EAs and VPS each require their own paid add-on to enable usage. MT4 and MT5 only. Match-Trader and cTrader do not support automated trading.** Automated activity must still follow the prohibited strategies and copy-trading rules."

Hyperactivity (help article 8020351, verified): >200 trades or >2,000 server messages/day → warning; 3 warnings = breach; 15,000 messages/day = forced disable. Forbidden (verbatim highlights): "High Frequency Trading: Use of high-frequency trading bots, mass order placement, or **AI-driven patterns designed to exploit the platform**"; "One-Sided Betting: …concentrated directional exposure… outcomes depend entirely on a single market move" (enforcement = 1% risk rule or exit); tick scalping (30s); grid; arbitrage; settlement-window (00:00–02:00 server time) exploitation; account/device sharing; third-party copy trading (copying *between your own* challenge accounts is allowed).

**Weekend/swing holds:** No restriction found in fetched rules; CFDs trade around the clock; hedging allowed within one account. (Explicit weekend-hold clause not found in the pages captured — flagged.)

**Instruments:** CFD challenges (FX/metals/indices — symbols page not fetched, flagged) and a separate **Futures** arm (FuturesFlex, Legacy, Rapid — rules page exists, not fetched in detail). Stocks: not found in captured pages (flagged).

**Regulation & vetting:** UAE-headquartered (founded 2022, founder Abdullah Jayed; Cyprus contact number); unregulated, simulated-funds model. Self-reports $316M+ rewards, 451K+ accounts, 99.99% payouts within 24h, Trustpilot 4.5/5 (73k+ reviews link), Deloitte Fast 50, Finance Magnates "Prop Firm of the Year." Known historical complaints about rule-enforcement subjectivity in secondary reviews (not verified against primary docs — flagged). **Scam-risk: Low–Medium** (large payouts history and volume, but newer than FTMO and unregulated).

**Feasibility for our system:** **Good — the 1-Step is attractive.** 6% static max loss and 3% daily loss force sizing ≤ ~24% of account per trade (12.28% stop → 2.9% loss), winners ≈ 4.3% of account; at 68% win rate, 10% target ≈ 3–4 winning trades ≈ 1–2 months, min 2 trading days trivially met. Two binding constraints: (1) **paid EA add-on is mandatory** — budget for it; (2) long-only concentration may read as "one-sided betting" over time — keep sizing diversified and risk ≤1–2% per trade (which the 3% DLL already forces). No consistency rule and no time limit make this one of the easier passes. Weekend holds unrestricted.

---

## 4. Apex Trader Funding (futures)

**Challenge structure (verified via archived copies of apex help center, 2026-03-25; live site 403s non-browser clients):**
- Current **EOD Evaluation** ("EOD Trail" products): **30-day access period (time limit)**, profit target 6% ($1,500/$3,000/$6,000/$9,000 on 25K/50K/100K/150K), **max drawdown 4% (EOD — calculated once daily at market close from EOD balance, enforced next session)**, **DLL 2%** ($500/$1,000/$1,500/$2,000; DLL = pause, not fail), max contracts 4/6/8/12, **no minimum trading days**, **consistency not applied in evaluation**. Fail = touching EOD threshold intraday (auto-liquidate).
- "Intraday Trail" variants exist (intraday trailing drawdown). Legacy model: trailing drawdown with "Safety Net" (initial + drawdown + $100) — archived page.
- **Funded stage (PA): 50% Consistency Requirement** (verified, help center): "No single trading day accounts for more than 50% of your total accumulated profit at the time of a payout request"; no fail, payout option just unlocks when satisfied; resets after each payout. Daily payouts offered.
- 7 calendar days to activate PA after passing.

**Automation policy:** Website ToU (Oct 22, 2025, archived 2026-01-05) is site-use boilerplate; the trading rules live in the **"Evaluation and Performance Account User Agreement" which is behind the member login and could not be fetched** (flagged). Apex's help center FAQ on bots/API could not be retrieved in this pass (flagged). Note: Apex evaluates on Rithmic/Tradovate/WealthCharts — Rithmic and Tradovate both have public developer APIs, and community documentation of API trading on Apex exists, but **that is not a verified primary-source statement — flagged**.

**Weekend/swing holds:** The EOD drawdown model (drawdown measured at market close) is compatible with multi-day holds; Apex advertises overnight-capable futures trading, but an explicit "hold overnight/weekend" policy clause was not captured in this pass (flagged — verify in User Agreement before paying).

**Instruments:** CME futures only (Rithmic/Tradovate/WealthCharts products). No stocks.

**Regulation & vetting:** ToU verbatim: "Apex Trader Funding is not a broker-dealer, futures commission merchant, or financial advisor." **Not CFTC/NFA-registered.** Texas corporation (Austin), operating since 2021, large volume of payout testimonials pages. Known community complaints about trailing-drawdown and consistency enforcement (secondary — flagged). **Scam-risk: Low–Medium** (paying large volumes but unregistered; automation policy opaque).

**Feasibility for our system:** **Marginal.** The **30-day time limit is the binding constraint**: our system may trade 0–1 times in the first weeks (SPY-filtered), and a 4% EOD drawdown vs a 12.28% stop forces sizing ≤ ~32% (a full stop-out = 3.9% of account — dangerously close to the 4% fail line intraday). Consistency is not in the evaluation but **binds at payout**: a 4.3% winning day vs ~8% net profit = 54% — must trade through it. Passable in a strong month, but variance exposure is high. Only pursue if automation policy is confirmed in the User Agreement first.

---

## 5. The5ers (forex CFDs + futures; stocks via sister brand Trade The Pool)

**Challenge structure (verified — the5ers.com/hyper-growth; TOS 2026-08-03):**
- **Hyper Growth (1-Step):** 10% evaluation target, **6% stop-out**, **3% daily loss**, **unlimited time**, leverage 1:30, fee from $15, no min profitable days (Pro Growth variant: min 3), **30-day inactivity expiry**, max $40K eval capital per trader. Scaling: +10% target doubles the account (up to $4M, up to 100% split; 75/25 below $350K).
- **High Stakes (2-Step) and Bootcamp (3-Step)** exist; parameters live on their own pages (not fetched in this pass — flagged).
- No consistency rule found for Hyper Growth (no best-day/profit-ratio cap in the program specs — flagged as verified-by-absence).
- **Weekend holds: allowed — VERBATIM: "Holding open trades over the weekend is allowed."** News trading allowed except bracket strategies. Assets: FX, Metals, Indices, crypto (no stocks on the CFD arm; stocks = Trade The Pool, §6).

**Automation policy — VERBATIM (TOS §11 "Use of Automated Trading Software"):**
> "The User may use any custom, algorithmic, or other automated trading software (collectively, 'Automated Trading Software') owned or developed by the User… subject to: (1) User shall notify the Company in writing and obtain written approval from the Company prior to using any Automated Trading Software; (2) no Automated Trading Software may be used unless the Company has given prior written approval…; (5) the Company may require advance testing… Notwithstanding the foregoing, the Company prohibits use of any Automated Trading Software owned or developed by any third party other than the User."

Also prohibited (TOS §10 / prohibited-practices page, updated 2026-07-28): HFT (sub-second durations), bulk trading ("automatic trading tools that open multiple trades at the same time"), EA rollover scalping, third-party EAs used by multiple traders (copy), **"Using an expert advisors from a provider where the trader does not own the source code,"** one-sided bets, bracket-news, cross-operator coordinated trading, and the standard AI clause. Note the gag clause (§10.10.11): public disparagement of the company = termination + forfeiture.

**Regulation & vetting:** Five Percent Online Ltd (UK, company 12553363, London); unregulated, simulated-funds model; 10th-anniversary (2016). TOS: payouts above a threshold are paid in weekly installments ≤$10K; mandatory video interview in verification; KYC. Trustpilot link on site. **Scam-risk: Low** (long track record, established group), with the caveat of the strict TOS gag clause and discretionary risk reviews.

**Feasibility for our system:** **Strong.** No time limit, no consistency rule, weekend holds allowed, news allowed, 6% stop-out forces sizing ≤ ~48% (win ≈ 8.7% of account) — or with 3% daily-loss constraint, sizing ≤ 24% (win ≈ 4.3%; two wins ≈ target). Automation legal **only after written pre-approval** — an administrative step, but the TOS makes approval discretionary, so apply early and provide code/documentation. Long-only is fine as long as it's not a single concentrated bet.

---

## 6. Equities-capable firms (US stocks)

**Verdict up front:** no major futures brand allows stocks — Topstep: "prohibited from trading Stocks" (verified); TradeDay: CME futures only (verified TOS); Bulenox: futures-only product set (verified homepage; rules pages 404 from this host — flagged). The credible challenge-style equities options are **Trade The Pool** and **E8 Markets**; everything else seen in search results is either CFDs of indices or unvetted newcomers (flagged as not recommended without further due diligence).

### 6.1 Trade The Pool (US stocks — verified, most complete docs)
- Operator: **Trade The Pool** is a brand of **Five Percent Online Ltd** (UK) — the same company as The5ers (5% group; CEO Michael Katz). Unregulated, simulated-finds model.
- Instruments: **US stocks, warrants, ETNs, ETFs, ETPs** tradeable on Nasdaq via the TraderEvolution platform (LPs include Interactive Brokers, Saxo). Verified from program-terms page.
- Programs (verified): **Day** and **Swing** account types; **Flex** (unlimited eval time) and **MAX** (60 days day / 100 days swing). $97 entry, free 14-day trial. Swing accounts: exposure allowed across the whole day → **overnight holds permitted**; day accounts are auto-liquidated 10 min before RTH close (may re-enter with overnight exposure ~16% of BP).
- Consistency (verified): max **position** profit ratio **30%** (MAX eval) / **50%** (FLEX eval+funded, legacy 50%); minimum positions to pass (MAX Day 20, FLEX Day 10, Swing 5); FLEX requires 3×0.5% profitable days per payout cycle; min 10 ticks profit and 60s min hold per position. Payouts ≥14 days apart, min $300.
- **Automation (verbatim):** "Support for automated trading, including the specific integration with SignalStack, is currently in a **beta** state… a rate of no more than **2 requests/min** should be targeted… the Company may request or require adjustments… TTP may revoke authorization for automated trading in general." — so automation is permitted-but-revocable.
- Hold restrictions that matter (verified): **no overnight position on a reporting company (or single-stock ETF linked to it) during earnings season**; positions closed before stock splits and ex-dividend shorts; swing holds require ≥500K shares/day average volume over prior 14 days. SPY/ETF-index momentum is largely unaffected; single-stock momentum with 14-day holds would trip the earnings rule.
- Feasibility: good for SPY/ETF momentum on a Swing/FLEX account; sizing: daily-pause + stop-out model, 12.28% stop must fit inside the per-account stop-out; 3×DL buffer rule applies after funded. Long-only SPY ETF avoids earnings/volume restrictions. Consistency 50% position ratio is easy at our sizing (per-position win ≈ 4% vs total profit). **Scam-risk: Low–Medium** (same UK group as The5ers; Trustpilot-linked; but younger brand — TTP launched 2022).

### 6.2 E8 Markets (stocks listed — partially verified)
- US-based ("US-Based" per homepage), SimFi simulated platform; 150+ markets. **Verified instrument list includes US stocks** (AAPL, AMD, MSFT, AMZN, META, GME, etc.) alongside forex/crypto/futures/indices. Behavioral-score evaluation model ("get paid to improve discipline"), $76M+ paid out claimed, 4.79/5 PropFirmMatch.
- **Not vetted in this pass:** challenge parameters, TOS, automation/EA policy, and payout reputation were not fetched (flagged). Treat as "instrument list verified, everything else unverified" — do not pay without reading their TOS.

### 6.3 Others — flagged, not recommended
- **StockProp / similar stock-CFD challenge brands**: appeared in search, not vetted; do not use without full TOS review.
- **Maverick-type capital firms** (no-fee, discretionary): real-capital equities prop desks exist but are not challenge-style and were not researched here.
- TradeDay and Bulenox are futures-only (see below).

### 6.4 TradeDay and Bulenox (futures; brief)
- **TradeDay** (verified TOS, Feb 2025): "TRADEDAY NOT REGISTERED" — no SEC/CFTC/NFA/FINRA registration (TOS §6 verbatim). Evaluation: **day-trading only, all positions closed ≥10 min before session end** (kills 14-day holds), CME futures only, min 7-day evaluation period, EOD trailing drawdown, $99 resets. Automation: §23 Prohibited Conduct — "Using any software, artificial intelligence, ultra-high speed, or mass Data entry that might manipulate, abuse…"; **"Using a VPN or VPS to mask the location of the trading"**; **"Using trading bots or Automated Trading Systems (ATS) purchased from a third party. Or multiple users using the same trading bots and ATS's."** — self-built ATS not explicitly banned, but day-trading-only + VPN/VPS ban makes this a poor fit. **Scam-risk: Low** (established, publishes pass rates; unregistered by its own admission).
- **Bulenox**: futures-only; live rules pages returned 404 from this host and its TOS PDF is site boilerplate (no trading rules, no NFA statement found). NFA registration status and automation policy **could not be verified** in this pass (flagged). Do not act on Bulenox until rules are read from their member area.

---

## 7. Sandbox-replication feasibility (dry-run before paying any fee)

All challenge rules are computable from our 5y daily archive + shadow engine + multiverse generator, using daily close marks and position-level P&L:

| Rule type | Math needed | Firms |
|---|---|---|
| Static max loss | % × initial balance, intraday equity check | FundedNext (6/10/8%), The5ers stop-out (6%), FTMO 2-Step (10%) |
| Trailing drawdown (EOD) | peak EOD balance − drawdown; lock at start | Topstep MLL (4/3/3%, locks), FTMO 1-Step (10% EOD-trailing), Apex EOD (4% of EOD balance), The5ers 6% static, FundedNext Instant (6% trailing) |
| Daily loss | balance@midnight CET (FTMO), fixed day windows (Topstep 5PM CT, Apex 6PM ET) − X% | FTMO 3/5%, Topstep $2.5K DLL, Apex 2% DLL, FundedNext 3/5/4%, The5ers 3% |
| Consistency | FTMO Best Day ≤50% of positive-days' closed P&L (00:00 CE(S)T attribution); Topstep best day <50% of profit target; Apex best day <50% of net profit since last payout; TTP per-position ratio 30/50% + min profitable days | FTMO 1-Step, Topstep, Apex PA, TTP |
| Time limits | calendar-day clocks | Apex 30 days; TTP MAX 60/100; inactivity: The5ers 30d, FundedNext 60d |
| Min trading days | days with an *opened* position (FTMO) / non-zero P&L day (FundedNext) / min position counts (TTP) | FTMO 4, FundedNext 2–5, TTP 5–20 |

Implementation notes: (1) FTMO's Best Day Rule needs closed-trade profit attributed to close-day CE(S)T; (2) Apex EOD drawdown needs an EOD-balance series re-computed each close; (3) Topstep MLL needs intraday low-ticks — on daily bars use day lows and assume stop-filled-at-stop; (4) multi-account/correlation and one-sided-betting flags are *qualitative* — encode our typical sizing as a constant so the reviewer sees uniform risk per trade; (5) run the multiverse generator against each firm's rule set as a post-filter; Apex's 30-day clock and FTMO 1-Step's Best Day Rule will be the highest-failure-rate filters in backtest, exactly as expected live.

---

## 8. Affiliate programs

| Firm | Program | Verified details |
|---|---|---|
| FTMO | Yes — affiliate portal (affiliate.ftmo.com, SSO login page verified) | Rate not public on the login page (flagged; historically revenue-share based) |
| FundedNext | Yes (Affiliate T&C PDF verified) | **Star tier 8%**; **Galactic tier 12%** after $1,000 commission threshold |
| The5ers | Yes — /refer-a-trader/ (page verified) | Exact % is in a promo image (not machine-extractable — flagged) |
| Apex | Yes — /affiliates page exists (footer link, archived copy) | Rate not captured (flagged) |
| Trade The Pool | Yes — /affiliate-page/ (verified link) | Rate not captured (flagged) |
| Topstep | **Not found** — no affiliate program link on site/footer (flagged) | — |
| TradeDay | **Not found** on site (flagged) | — |

None of the verified programs exposes API-based or agent-friendly tracking publicly; all are cookie/link-based (flagged: standard affiliate SaaS not disclosed).

---

## 9. Verdicts

| Firm | Instruments | AI/bot policy | Scam-risk | Pass-feasibility for our system |
|---|---|---|---|---|
| **Topstep** | CME futures only | Allowed (VPS/VPN banned, day-trading only) | Low | **Poor** — no overnight holds |
| **FTMO** | FX/CFD (2-Step model) | Allowed (<2,000 req/day) | Low | **High** (use 2-Step, Swing type) |
| **FundedNext** | FX/CFD + futures | Allowed w/ paid EA+VPS add-ons | Low–Med | **High** (Stellar 1-Step; 6% static) |
| **Apex** | CME futures only | Unknown (User Agreement behind login) | Low–Med | **Marginal** — 30-day limit; verify TOS first |
| **The5ers** | FX/CFD; stocks via TTP | Allowed w/ written pre-approval, own code | Low | **High** (Hyper Growth; weekend holds OK) |
| **TradeDay** | CME futures only | Third-party bots banned; self-built unclear | Low | **None** — day-trading only |
| **Bulenox** | Futures only | Unverified | Unverified | Unverified — flagged |
| **Trade The Pool** | US stocks/ETFs (Nasdaq) | Beta-allowed (SignalStack, 2 req/min) | Low–Med | **Medium–High** (Swing/FLEX, SPY ETFs) |
| **E8 Markets** | US stocks + 150+ markets | Unverified | Unverified | Unverified — flagged |

**Top 3 firms worth pursuing (for a daily, automated, long-only, 14-day-hold momentum system):**
1. **FTMO (2-Step, Swing account type)** — no consistency rule, no time limit, holds allowed, EAs explicitly allowed under a generous request cap, best payout track record ($650M+, 4.8/5 Trustpilot, 10-year run). Only the news/gap *entry* window needs handling in the rule engine.
2. **The5ers (Hyper Growth 1-Step)** — weekend holds allowed, no time limit, no consistency rule, news allowed; automation legal after written approval of our own code. Fee from $15. Watch the discretionary risk review + gag clause.
3. **Trade The Pool (Flex Swing, SPY/ETF)** — the credible US-equities route (same UK group as The5ers): long-only ETF momentum fits its 50% position-consistency and no-earnings restrictions; automation is beta (2 req/min) with revocable approval, so run semi-automated.

**Do not pursue:** Topstep/TradeDay (no overnight holds — architectural mismatch), Apex until its User Agreement's automation clause is read in the member area, Bulenox/E8 until rules verified.

---

## Sources (primary; all fetched 2026-08-05)

**Topstep**
- https://www.topstep.com/terms-of-use (ToU §27 Prohibited Conduct, §28 VPS/VPN ban; May 11, 2026)
- https://help.topstep.com/en/articles/8284197-trading-combine-parameters ("Yes, with conditions" automation FAQ; June 24, 2026)
- https://help.topstep.com/en/articles/8284204-what-is-the-maximum-loss-limit (MLL $2,000/$3,000/$4,500; trailing; locks)
- https://help.topstep.com/en/articles/10305426-prohibited-trading-strategies-at-topstep (June 10, 2026)
- https://www.topstep.com/disclosures-notices and https://www.topstep.com/about-us (futures-only; Topstep Brokerage NFA ID 0567079; 2025 stats)
- https://www.topstep.com/rules (redirects; rules on site) — combine parameter table (profit-target values) not captured in this pass (flagged)

**FTMO**
- https://ftmo.com/en/terms-and-conditions/ (PDF: cdn.ftmo.com/docs/terms-and-conditions/…) — Clause 7 (Risk Management, Forbidden Trading Practices)
- https://ftmo.com/en/forbidden-trading-practices/ (updated 2026-02-02; EA 2,000-request cap verbatim)
- https://ftmo.com/en/trading-objectives/ (updated 2026-05-13; 1-Step/2-Step params, Best Day Rule 50%, min 4 days, no time limit)
- https://ftmo.com/en/how-it-works/ (Swing vs Standard hold rules; 90% split; fee refund)
- https://ftmo.com/en/symbols/ (JS-rendered table — flagged)
- https://ftmo.com/en/affiliate/ (portal login; rate not public — flagged)

**FundedNext**
- https://fundednext.com/en/general-rules/cfds/trading-objectives (Stellar params)
- https://fundednext.com/en/general-rules/cfds/what-is-forbidden and /what-is-allowed (EA+VPS add-ons verbatim; news split; hedging)
- https://help.fundednext.com/en/articles/8020351-what-are-the-restricted-prohibited-trading-strategies (hyperactivity 200/2,000/15,000; quick strike 30s; one-sided betting)
- https://fundednext-production-bucket.s3.amazonaws.com/…/FundedNext_Affiliate_Terms_&_Conditions.pdf (Star 8% / Galactic 12%)

**Apex**
- https://apextraderfunding.com/terms-of-use (archived 2026-01-05; "not a broker-dealer, futures commission merchant")
- https://apextraderfunding.com/help-center/eod-trailing-drawdown-accounts/eod-evaluations/ (archived 2026-03-25; 30-day access, 6% target, 4% EOD drawdown, 2% DLL)
- https://apextraderfunding.com/help-center/additional-helpful-items/50-consistency-requirement/ (archived 2026-05-06)
- https://apextraderfunding.com/help-center/legacy-products/legacy-trailing-drawdown-rule/ (archived 2026-05-24; Safety Net math)
- User Agreement (rules + automation): behind login — **not verified** (flagged)

**The5ers**
- https://the5ers.com/terms-and-conditions/ (Aug 3, 2026; §10 prohibited practices, §11 Automated Trading Software, §7.5 payout installments, gag clause)
- https://the5ers.com/faqs/prohibited-trading-practices/ (July 28, 2026)
- https://the5ers.com/hyper-growth/ (1-Step params; weekend holds verbatim)
- https://the5ers.com/refer-a-trader/ (program exists; % in image — flagged)

**Equities**
- https://tradethepool.com/program-terms/ (instruments, Day/Swing, MAX/FLEX, 30%/50% position consistency, automation beta, earnings/overnight rules, payouts)
- https://tradethepool.com/ (programs, $97 fee, Trustpilot link, Five Percent Online Ltd disclosure)
- https://www.e8markets.com/ (US stock instrument list verified; rules/TOS not fetched — flagged)
- https://www.tradeday.com/terms-and-conditions/ (Feb 18, 2025; day-trading-only, CME-only, NOT registered §6, ATS/VPN clauses §23)
- https://bulenox.com/ + Terms_of_Use.pdf (site boilerplate only; trading rules 404 from this host — flagged)

**Cross-cutting notes / unverified items:** NFA BASIC direct lookups blocked from this host (reliance on firms' own disclosures for registration status); FTMO/Bulenox exact fee schedules (JS-rendered); FTMO stock-CFD offering; Apex overnight/weekend clause and automation policy; The5ers affiliate %; E8 and StockProp full TOS; any regulatory-probe news claims (secondary media, not primary — excluded by methodology).
