# OpenTrader

Self-improving trading system: MoT expert mixture (rule-floor prior) + value-head experts trained by an adversarial self-play arena (battle → fit → war → relabel → gate).

**Read `ARCHITECTURE.md` first** — it is the single source of truth for ports, models, and the five open integration seams. Stale docs live in `docs/archive/`.

Key surfaces: `arena/` (training), `mot/` (expert mixture), `setup_search/` (value heads + walk-forward), `training/` (RL/distillation), `docs/research/` (frontier decisions).
