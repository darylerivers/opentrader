# ADR-0005: Prop revenue vehicle — FTMO 2-Step

- **Status:** accepted
- **Date:** 2026-08-05
- **Context:** capital-limited; the prop route was researched across nine firms
  (docs/research/prop-firm-challenge-research.md) and dry-run in the sandbox
  (setup_search/prop_challenge_sim.py, replaying the system's actual 77-trade
  5y sequence through each firm's verified rules). Sandbox verdicts: FTMO
  2-Step and 1-Step PASS; The5ers and FundedNext FAIL on inactivity clocks
  (the system's 102-day no-trade gap vs their 30/60-day deactivation); Apex
  FAIL on its 30-day clock. Research's "4-6 weeks to target" was a cadence
  misread — the sim shows ~939 days / 44 trades at current cadence.

- **Decision:** FTMO 2-Step (Swing account type) is the prop revenue vehicle.
  Operational constraints adopted from the verified ruleset:
  - Sizing ≤ ~20% of account per trade during the challenge (5% daily loss,
    sized to survive two same-day stops, compounding-aware);
  - no entries within ±5 minutes of high-impact news, or within 2 hours of a
    ≥2-hour market close (the news/gap entry ban — the rule engine must encode
    it before the prop leg starts);
  - automation is allowed (<2,000 server requests/day); challenge fee
    ~$100-500; funded stage up to 90% split; no time limit, no inactivity
    clock, no consistency rule on the 2-Step.

- **Consequences:** the prop account is a slow compounding revenue stream
  (multi-year at current cadence), not a quick capital injection. The cadence
  is the binding constraint everywhere; the levers are Tier 2/3 (ADR-0003) and
  the shadow-validated experts, all gated.
