# ADR-0004: Frequency policy — more-trades-first, intraday as a gated second project

- **Status:** accepted
- **Date:** 2026-08-05
- **Context:** the user wanted a high-frequency system. Facts: the only
  validated edge is daily momentum; frequency is not free (each step up means a
  new edge to discover, new fees, new competition); at small capital the fee
  math is fatal for intraday (50 trades/day at $100 notional ≈ $70/day in fees);
  HFT (sub-second) is out of scope entirely (capital, stack, competition). The
  system owns one validated asset; accelerating it is not an option — the
  validated edge does not transfer across timeframes.

- **Decision:** more-trades-first. Trade count scales via the three-tier
  structure (ADR-0003) toward the ~100/yr cap (the 6-position limit), using the
  edge we own. Intraday becomes a SEPARATE research track — experts trained and
  gated through the same arena gate, shadow, and deployability criterion before
  any real money touches it. HFT is declined as a goal.

- **Consequences:** the daily edge remains the money track and funds/disciplines
  the frequency ambition; the frequency track is the second project, never the
  replacement.
