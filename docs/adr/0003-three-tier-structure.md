# ADR-0003: Three-tier structure — offline rank, live trade top-N

- **Status:** accepted
- **Date:** 2026-08-05
- **Context:** the user asked how the system can (a) react to sector rotation
  (tech → oil giants) and (b) process as many tickers as possible concurrently,
  and whether pursuing full-market coverage was scope creep. Facts established:
  the validated rule's screen is ABSOLUTE per-symbol (score ≥ buy_thresh), not
  cross-sectional — rotation is caught only within the universe, and CVX-class
  names outside the validated 16 are invisible. The rank-based features that
  detect rotation (mom_rank/rsi_rank percentiles) exist only in the macro
  expert's feature set today. The 35M-row HuggingFace cross-section (11,719
  symbols) is already downloaded but unused (interrupted cache build). The
  live loop cannot economically run thousands of tickers (per-symbol bar
  fetches, 6-position cap, 14-day holds).

- **Decision:** three tiers, never one:
  1. **Live loop (Tier 1)** — the pinned liquid subset (validated 16 + crypto),
     faithful replica, deployability gates (ADR-0002). Unchanged by this ADR.
  2. **Offline cross-section (Tier 2)** — the full dataset processed offline
     (minutes of CPU), where the rotation detector lives: cross-sectional rank
     features over all symbols. The fullcross build becomes a scheduled offline
     job (also feeding multiverse-augmented training).
  3. **Portfolio ranker (Tier 3)** — an offline daily ranking over the full
     cross-section; the live loop trades the top-N. The institutional pattern
     (research ranks 10k, desk trades 50). GATED to arrive after first real
     money: it changes the strategy surface, so it must re-gate under ADR-0001.

  Also: **versioned fidelity** — the validated ladder is a snapshot, not
  scripture. Re-validation runs on the appended archive quarterly, or sooner on
  sustained shadow drift (two months of mean-impact or slippage outside band).
  A new validated config promotes through the same gates; the old one retires
  to docs/archive.

- **Consequences:** universe breadth and trade count scale toward the
  6-position-cap ceiling (~100 trades/yr) via Tier 2/3, without loading the
  live loop. The runway itself stays small and gated. Scope was not reduced —
  it was layered.
