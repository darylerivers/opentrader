# ADR-0002: The deployability criterion

- **Status:** accepted
- **Date:** 2026-08-05
- **Context:** the runway (ADR-0001, CONTEXT.md) needs a pre-committed,
  falsifiable definition of when the system earns real money at risk. The paper
  phase produces ~3 real trades in 12 weeks (two of three windows ≤2), so
  return-based criteria are structurally impossible and would defer deployment
  for years. The shadow engine, not the paper account, is where edge evidence
  accrues.

- **Decision:** the system is *deployable* when all three hold:
  1. **Plumbing fidelity** — ≥3 closed paper trades spanning at least two
     distinct exit paths (stop, target, or 14-day hold), zero fatal defects
     (silent holds, state corruption, order rejections, >15bps realized
     slippage, exit-ladder deviation), reconciliation <0.1%. The rare exits
     (94% of backtest exits are the 14-day hold) are force-tested in the
     sandbox with synthetic positions — the paper phase only demonstrates the
     paths the market actually gives it.
  2. **Edge persistence** — the shadow's up-regime rule-floor edge (≥+0.9% mean
     per-trade impact) has not decayed in the latest window.
  3. **Calendar floor** — ≥10 weeks continuous paper, so the system has survived
     at least one full regime flip.
  Returns are not part of the criterion. A faithful losing system is deployable
  at 1% size; an unfaithful green system is not.

- **Consequences:** first real money is a gates event, not a date. The ladder
  (1% → 10%) proceeds only on continued fidelity + shadow persistence. This ADR
  is the pre-commitment that prevents the paper phase from being judged on P&L.
