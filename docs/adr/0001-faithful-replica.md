# ADR-0001: The faithful replica principle

- **Status:** accepted
- **Date:** 2026-08-05
- **Context:** the runway (see CONTEXT.md) deploys the validated rule to a live
  paper harness. When the live harness ran ATR-based exits (3xATR on 1h bars),
  a 2% trailing overlay, and a crypto-derived risk config, identical signals
  produced −6.8% live vs +22.2% backtest. Live was a different strategy, so
  live-vs-backtest comparison was meaningless — self-inflicted diagnostic noise.

- **Decision:** live must reproduce the validated strategy exactly:
  - exits = validated ladder (12.28% stop / 17.81% target / 14 trading-day max
    hold, trailing off), evaluated on daily bars;
  - risk contract = validated (15% per position, 6 positions, 95% exposure,
    Kelly inputs from validated stats so the cap never clips);
  - the held-out gate, war relabels, and all evidence stay real-data-only;
    synthetic multiverse rows may augment training but never measurement.

- **Consequences:** any deviation from the validated contract must be an explicit,
  logged ADR of its own — never a silent drift. The runway's pass criteria are
  infrastructure and exit-ladder fidelity, not returns.
