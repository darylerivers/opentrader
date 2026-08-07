# OpenTrader

A self-improving algorithmic trading system: a walk-forward-validated rule floor (the incumbent edge) paired with value-head neural experts selected by a Mixture-of-Traders (MoT) router. Experts must earn their way in through an adversarial training arena — they are only deployed when they beat the incumbent's held-out gate.

## The core idea

Most trading systems are a single model with a backtest. OpenTrader treats edge as something that must be *earned and re-proven*:

1. **Rule floor** — a long-only daily momentum strategy, validated with walk-forward analysis on real data (12.28% stop / 17.81% target, 14-day max hold, SPY-vs-96d regime gate). This is the incumbent; it holds all weight until an expert beats it.
2. **Value-head experts** — small MLP experts (momentum, macro, international) trained on the same feature space, selected per-regime by the router.
3. **Arena** — an adversarial loop (`battle → fit → war → relabel → gate`) where candidate experts train against the incumbent. A candidate only ships if it clears a **+1% edge on both regime windows** against held-out data.
4. **Multiverse stress-testing** — neural + parametric market samplers plus a curated crisis tail-library (COVID crash, 2022 bear, yen unwind) to overfit-proof the edge before deployment.
5. **Live harness** — real price feeds (equities + crypto), regime-gated risk, paper settlement, and continuous evidence accrual.

**Validation discipline is the product.** Nothing deploys on vibes; everything earns its place against the incumbent on data it has never seen.

## Repository layout

| Path | Purpose |
|---|---|
| `arena/` | Adversarial training loop (battle/fit/war/relabel/gate) |
| `mot/` | Mixture-of-Traders router + expert definitions |
| `setup_search/` | Value-head training, walk-forward validation, FTMO universe |
| `training/` | RL / distillation refinement (GRPO) |
| `exchange/` | Data sources, live/paper execution, multi-router |
| `risk/` | Regime-gated risk rules |
| `harness.py` | Live paper-trading harness |
| `docs/` | Architecture, ADRs, research decisions |

## Validated configuration

The current validated playbook lives in `data/setup_search/best.json` — the walk-forward-optimized parameters for the rule floor. Runtime state (agent/adapter state, training checkpoints, caches) is intentionally **not** committed; the repo tracks code, architecture, and validated artifacts only.

## Getting started

```
pip install -r requirements.txt
python run_harness.py --help
```

See `ARCHITECTURE.md` for the full design, ports, and integration seams.
