# Research: Hedge-fund persona playbooks for the arena (Citadel, Citron, trend house)

**Date:** 2026-08-04
**Question:** What does each hedge-fund persona DO in the arena? For a starter
set — Citadel-style quant/market-making, Citron-style short/activist, one
macro/trend house — define the trading style, the behaviorally-relevant decision
rule an in-process bot can execute in the candidate-battle ring, and the edge
each persona has against the rule playbook.
**Method:** primary sources where possible (Citron Research site, Man AHL site),
reputable secondary otherwise (Wikipedia citing SEC/P&I/Institutional
Investor/Bloomberg; SEC 2024 complaint), then mapped onto the arena's executable
feature set (`setup_search/engine.py:36` `_features`: `mom`, `rev`, `rsi`,
`brk`, `z`, `ma_dist`, `vol_spike`, `vol_level`, `momfilt`, cross-sectional
`rank`; regime = SPY vs 200d MA, `validate_momentum_agent.py:58`).

## 0. The arena's executable surface

Rule opponents must live in-process and consume what the candidate pipeline
already computes (pure OHLCV — the map's Notes rule out LLM-served persona
opponents at VRAM ceiling unless research says otherwise):

- **`mom`** — own-return momentum over `mom_lb`
- **`rev`** — mean-reversion pressure (negative return over `rev_lb`)
- **`rsi`** — oscillator
- **`brk`** — distance from rolling-high breakout
- **`z`** — z-score of price vs rolling mean/std
- **`ma_dist`**, **`vol_spike`**, **`vol_level`**, **`momfilt`** — research
  gates (MA distance, volume spike, realized vol)
- **`rank`** — cross-sectional rank across the 17-symbol universe
- **regime** — SPY above/below its 200d MA

Every persona below is specified as a rule over these columns, so it is a
drop-in in-process bot. **Verdict up front:** none of the three needs LLM-driven
behavior to open the arena (see §5).

## 1. Citadel-style — quant multi-strategy / market-making

### Trading style
Multi-strategy, not a single directional bet. Fund silos: Wellington (flagship
multi-strategy, 1990), Global Equities (market-neutral, 2001), Tactical Trading
(statistical-arb + market-neutral equity, 2007/2009), Fixed Income & Macro
(1999), plus commodities and credit. Semi-autonomous "pod" teams each run their
own sector book under centralized risk (risk-capital allocation, stress
exposure, liquidity management; ~500 stress tests/day). The market-making arm
(Citadel Securities, a separate legal entity) earns the spread by inventory
management and price reconciliation across venues — Griffin framed it publicly
as "keep[ing] the New York markets in line with the markets in Chicago."
Edge = relative-value/spread capture and tight, centralized risk, not a
directional view.

### Behaviorally-relevant decision rule (in-process bot)
A stat-arb/market-making tilt on the candidate set — it only TAKEs "cheap
within an uptrend" and fades extensions:

- **Entry (TAKE):** `mom > 0` (trend context intact) **AND** `z < +z_max` (not
  extended — price near/under the rolling mean) **AND** `rev > 0` (recent dip =
  the relative-value mispricing to buy). This is *contrarian within an uptrend*:
  it buys weakness against strength, the closest OHLCV analogue to a
  relative-value fill.
- **Exit:** scale out when the mispricing closes — `z` reverts toward 0 or `rsi`
  re-enters the neutral band — a spread-capture exit, not a directional one.
- **Sizing:** inverse-vol position sizing (`1 / vol_level`, shrink further on
  `vol_spike`); small per-candidate size, high turnover, many small bets. Hard
  per-trade and per-basket risk caps.
- **Risk appetite:** LOW directional exposure; loses gracefully in big trends
  (it's short the trend's tail), wins in range/mean-reverting regimes.
- **Contrarian vs momentum:** contrarian-lite / relative-value; momentum-aligned
  only as the trend "context" filter, never as the entry reason.

### Edge against the rule playbook
The rule playbook (the Momentum agent's naive TAKE-all-momentum baseline that
iteration #1 degenerated to) buys after moves are already extended. Citadel
persona's edge is in **choppy/mean-reverting regimes**: it skips the extended
entries the playbook chases, sizes down as vol spikes, and monetizes the
reversion the playbook bleeds on. Low correlation to the momentum bot — exactly
the opponent that exposes "momentum in a range market" as a losing rule.

## 2. Citron-style — short / activist research

### Trading style
Activist short-selling driven by published negative research ("representing the
other side of Wall Street," publishing since 2001). Concentrated, high-conviction,
narrative-driven bearish bets against the consensus; famous targets ran from
Valeant (2015) to GameStop (2021, where shorts including Citron capitulated into
a 700% rally). Critically, the house is **evidence-driven, not position-sticky**:
its own site describes covering a long-held short thesis and flipping to a bull
case when "the facts changed." The real edge is reading company documents,
regulatory filings, and announcements — fundamental, not technical. The SEC's
July 2024 civil complaint against Andrew Left and Citron Capital alleges the
research was weaponized: recommendations made contrary to private positions for
~$20M (2018–2023) and advance-sharing of planned announcements with two hedge
funds. Take the *strategy* (fade hype, act on thesis change), not the *alleged
abuse*, for the persona.

### Behaviorally-relevant decision rule (in-process bot)
A deliberately **adversarial** opponent — the anti-momentum vote. Its TAKE is
rare and contrarian; its default is SKIP-with-a-thesis:

- **Entry (TAKE, rare):** TAKE only when the candidate *looks like a hype
  trap to fade* — `mom > 0` **AND** extreme extension (`z > +z_hi` or
  `ma_dist > +d_hi` or `rsi > rsi_hi`) **AND** `vol_spike` elevated (event
  volume = the "story"). I.e. it acts only where it can short the overextension.
  In a long-only TAKE/SKIP ring this is the "fade" vote.
- **Exit / thesis-falsification:** the CACC lesson encoded as a rule — if the
  extension *keeps* extending (`mom` accelerates over the next `k` bars, `brk`
  re-breaks to new highs), the thesis is falsified; flip to SKIP/no-position.
  Never average into a losing thesis.
- **Sizing:** concentrated when it strikes (high conviction), but the flip rule
  bounds the tail; the persona is built to lose big in sustained rallies (the
  GameStop failure mode) — that's part of the design.
- **Risk appetite:** HIGH per-position, LOW frequency; variance is the point.
- **Contrarian vs momentum:** strongly contrarian — it is the momentum
  bot's mirror-image failure detector.

### Edge against the rule playbook
The playbook's worst regime is the **momentum crash** — after market rebounds,
momentum strategies bleed (Daniel & Moskowitz 2016). The Citron persona is built
to sit exactly there: it fades the extended, event-driven moves that naive
momentum rules TAKE at the top. Its edge is adversarial and regime-dependent: it
dominates in hype/frothy conditions and gets crushed in clean trends — which
makes it a great *discriminating* opponent, not a balanced one.

## 3. Man AHL-style — systematic trend / CTA (macro/trend house)

### Trading style
One of the longest-running systematic managers (founded 1987 as a CTA), built on
trend-following: "markets exhibit persistent anomalies, such as price trends,
mean reversion, carry... inefficiencies result from behavioural biases, for
example risk aversion, anchoring and herding." Core principles: diversification,
efficiency, risk control. Flagship momentum programmes span 800+ markets; vol
targeting is explicit (the AHL "TargetRisk" lineage). Pure time-series momentum
with long lookbacks and risk-controlled exposure — the academic anchor is
Moskowitz-Ooi-Pedersen (2012) time series momentum, already on file in this
repo's research notes.

### Behaviorally-relevant decision rule (in-process bot)
The **momentum-aligned mirror** of the Momentum agent — the honest baseline:

- **Entry (TAKE):** long-lookback trend confirmed — `mom` over a LONG window
  (`mom_lb_long`, e.g. 3–4x the bot's `mom_lb`) `> 0` **AND** `ma_dist` over a
  long MA `> 0` **AND** regime aligned (`SPY > 200d MA`). No mean-reversion
  entries, no fading — it only rides.
- **Exit:** slow, trend-respecting — exit when the long-lookback `mom` turns
  negative or price crosses back below the long MA; **no tight stops**. Rides
  through short-term noise and drawdowns by design.
- **Sizing:** vol-targeted (`target_vol / vol_level`), so exposure is scaled to
  realized vol; the rule's edge is discipline (position on, stay on) not timing.
- **Risk appetite:** moderate per-position, LOW turnover, broad diversification;
  accepts long drawdowns for the trend's payoff.
- **Contrarian vs momentum:** pure momentum — the persona the Momentum agent is
  nominally trying to beat.

### Edge against the rule playbook
The rule playbook's discrimination failure (iteration #1: SKIP-everything,
+0.00% vs all +2.50%) is exactly what a disciplined trend rule fixes: it
TAKEs persistent trends with vol-scaled size and holds them, so it collects the
+2.50% the baseline threw away. Against a *better* momentum agent, AHL-persona is
the discriminating holdout: if the RL candidate can't beat a long-lookback,
risk-controlled trend rule on the same candidates, it isn't adding edge. This is
the opponent that makes the arena meaningful.

## 4. Per-persona summary table

| Persona | Style | TAKE rule (entry) | Exit | Sizing / risk | Alignment | Edge vs playbook | Regime where it wins |
|---|---|---|---|---|---|---|---|
| Citadel (quant/market-making) | Multi-strategy stat-arb, market-neutral, spread capture | `mom>0 & z<z_max & rev>0` (cheap-within-trend) | `z`→0 / RSI neutral (spread capture) | Inverse-vol, small, capped, high turnover | Contrarian-lite / relative-value | Skips extended chases; monetizes reversion | Range / choppy, mean-reverting |
| Citron (short/activist) | Activist short research, concentrated, thesis-driven | `mom>0 & (z>z_hi or ma_dist>d_hi or rsi>rsi_hi) & vol_spike` (fade hype) | Thesis falsification: re-break to new highs → flip to SKIP | High conviction, low frequency, bounded tail | Strongly contrarian | Fades momentum-crash tops; adversarial | Froth / hype, post-rebound |
| AHL (systematic trend/CTA) | Time-series trend following, vol-targeted | long-lb `mom>0 & ma_dist>0 & regime up` | Long-lb `mom` <0 or long-MA cross | Vol-targeted, low turnover, wide stops | Pure momentum | Collects trends; fixes SKIP-everything | Sustained trends |

## 5. Verdict: does any persona need LLM-driven behavior?

**No — open the arena with all three as in-process rule bots.**

- **Citadel and AHL:** their edges are rule-expressible on the arena's existing
  OHLCV features (relative value + vol scaling; long-lookback trend + vol
  targeting). An LLM adds nothing but VRAM cost, and the map's Notes put the
  fleet at ceiling — this confirms the in-process-bot default for these two.
- **Citron:** its *real* edge — reading filings, announcements, and narrative
  intent — is not OHLCV-expressible; a rule bot can only caricature it as an
  over-extension fade + thesis-falsification exit. That caricature is a *good
  enough* adversarial opponent to start, because the arena needs a discriminating
  anti-momentum vote, not a faithful Andrew Left. **If** a later refinement
  needs the narrative edge, that persona is the single candidate for an
  LLM-served "thesis reader" on GPU1 — a follow-on decision, not a blocker.

## Sources

- Citron Research, official site (executive editor Andrew Left, "Representing the
  other side of Wall Street," publishing since 2001; CACC bull-case note on
  covering a long-held short thesis as "the facts changed"):
  https://www.citronresearch.com
- SEC press release + civil complaint (2024-07-26), *SEC charges Andrew Left with
  fraud* — public recommendations contrary to private positions (~$20M,
  2018–2023), advance-sharing with two hedge funds: cited via
  https://en.wikipedia.org/wiki/Andrew_Left
- Citron / short-seller history (Valeant, GameStop 2021 short squeeze and
  capitulation): cited via https://en.wikipedia.org/wiki/Citron_Research
- Man AHL, official site — founded 1987 as CTA; trend-following origins;
  "persistent anomalies... behavioural biases (risk aversion, anchoring,
  herding)"; diversification/efficiency/risk control; 800+ market momentum
  programmes; vol-targeting lineage: https://www.man.com/ahl
- Citadel LLC structure and strategies — Wellington (1990), Global Equities
  market-neutral (2001), Tactical Trading stat-arb (2007/2009), Fixed Income &
  Macro (1999); semi-autonomous teams; ~500 stress tests/day, risk-capital
  allocation, liquidity management; $90.4B net gains since 1990 (LCH); Griffin
  congressional testimony on market-making price reconciliation (NY/Chicago):
  cited via https://en.wikipedia.org/wiki/Citadel_LLC
- Moskowitz, T., Ooi, Y. & Pedersen, L.H. (2012). Time series momentum. *Journal
  of Financial Economics.* DOI 10.1016/j.jfineco.2011.11.003
- Daniel, K. & Moskowitz, T. (2016). Momentum crashes. *Journal of Financial
  Economics.*
- Arena feature surface: `setup_search/engine.py:36` (`_features`), regime in
  `setup_search/validate_momentum_agent.py:58`
