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
  10%, gated on shadow evidence and infra cleanliness.
- **Sandbox** — opentrader-sandbox, an isolated copy of the repo. All changes are
  proven here before touching the live tree or the GPU.
- **Faithful replica** — the principle that live must reproduce the validated
  strategy exactly (same exits, sizing, risk contract) or live-vs-backtest
  comparisons are meaningless.

## Avoid

- "The AI trading model" — say which expert.
- "More data" — say which model consumes which feature space.
- "Validated" — only for things that passed the gate or walkforward.
