# CONTEXT — OpenTrader's shared language

Terms as this project actually uses them. When agents or issues name a concept,
use the term below; don't drift to synonyms the glossary avoids.

## The trader

- **Rule floor** — the walkforward-validated long-only rule (data/setup_search/best.json).
  The incumbent. Holds all weight until an expert earns it.
- **Validated config** — same thing; the "playbook". Its risk contract: 15% per
  position, 6 concurrent positions, 95% exposure, 12.28% stop, 17.81% target,
  14-day max hold, SPY-vs-96d regime gate.
- **Regime** — the market state the rule trades on: SPY above or below its 96-day
  average. "Up" or "down". One regime clock for equities; crypto gates on BTC's
  own trend, not SPY.
- **MoT router** — the Mixture-of-Traders selector. Picks the expert per regime;
  the floor holds until an expert's recorded per-trade impact beats the floor's.
- **Expert** — a deployable edge: a tiny value-head MLP (momentum, macro,
  international). LLMs are the explainable layer, never the edge.

## How edge is built and measured

- **Arena** — the adversarial training loop: battle → fit → war → relabel → gate.
- **Gate** — the held-out discrimination test: an expert's kept-trades mean minus
  the candidate mean must clear +1% on both regime windows. Real data only.
- **Multiverse** — generated market worlds (neural + parametric samplers) used to
  stress-test the agent and to augment training. Synthetic rows never enter the
  gate, the war, or the evidence.
- **Tail library** — curated crisis worlds (US debt ceiling, COVID crash, 2022
  bear, yen unwind, flash crash). GANs under-sample tails; this is the
  countermeasure.
- **Fidelity war** — replay of the real 5-year archive. The headline gate.
- **Multiverse war** — survival test across generated worlds; a world is "ruined"
  below −25% net or −30% drawdown.
- **Shadow** — the daily-archive evidence engine (setup_search/shadow_mot.py).
  Where edge evidence actually accrues; thousands of candidates per run.
- **Paper shadow** — the live harness on real prices, paper settlement.
  Infrastructure validation, not edge validation.
- **GRPO** — group-relative policy optimization; the arena's refinement step.

## The deployment program

- **Runway** — the phased plan: paper shadow → first real money at 1% → ladder to
  15%, gated on shadow evidence and infra cleanliness. Capital ceiling $10k,
  funded by work income + prop-challenge rewards (ADR-0005). Sizing ramps
  1% → 15% gated on fidelity; the absolute-$ stop is 10% of account → halt +
  review.
- **Prop account** — the FTMO 2-Step challenge (ADR-0005), the project's
  revenue vehicle: firm capital traded on a slow compounding clock
  (~939 days to target at current cadence), 90% split at funding, sizing ≤20%
  during the challenge, and a news/gap entry ban the rule engine must encode.
- **Inactivity clock** — a firm's deactivation timer (The5ers 30d, FundedNext
  60d): the system's 102-day no-trade gap disqualifies any firm with one; only
  FTMO has none.
- **Deployable** — the pre-committed gate for first real money: ≥3 closed paper
  trades spanning at least two exit paths, zero fatal defects, ≤15bps realized
  slippage; the shadow's up-regime rule-floor edge un-decayed; ≥10 weeks
  continuous paper. Rare exits are force-tested in the sandbox, not awaited
  live. Returns are deliberately not part of the criterion (see ADR-0002).
- **Fatal defect** — a plumbing failure that disqualifies the paper phase on any
  single occurrence: silent hold, state corruption, order rejection, >15bps
  slippage, exit-ladder deviation.
- **Three-tier structure** — how the system handles scale (ADR-0003): the live
  loop trades a pinned liquid subset; the offline cross-section (the 35M-row
  dataset) ranks all symbols; the portfolio ranker (later, gated) trades the
  top-N. Offline rank, live trade top-N.
- **Portfolio ranker** — Tier 3: an offline daily cross-sectional ranking over
  the full universe; the live loop trades the top-N. Arrives after first real
  money, re-gated under the faithful-replica principle.
- **Versioned fidelity** — the validated ladder is a snapshot, not scripture:
  re-validation on the appended archive quarterly (or on sustained shadow
  drift), promoted through the same gates; the old config retires.
- **Rotation detector** — the rank-based layer (cross-sectional mom/RSI
  percentiles) that reacts to sector rotation; lives in Tier 2 (the macro
  expert's feature set today, the offline cross-section tomorrow). The
  validated 16-name rule's screen is absolute, not rank-based — it catches
  rotation only within its universe.
- **Sandbox** — opentrader-sandbox, an isolated copy of the repo. All changes are
  proven here before touching the live tree or the GPU.
- **Faithful replica** — the principle that live must reproduce the validated
  strategy exactly (same exits, sizing, risk contract) or live-vs-backtest
  comparisons are meaningless.

## Avoid

- "The AI trading model" — say which expert.
- "More data" — say which model consumes which feature space.
- "Validated" — only for things that passed the gate or walkforward.
