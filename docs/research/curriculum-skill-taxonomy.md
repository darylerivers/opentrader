# Curriculum skill taxonomy — what the arena can measure, how skills compose

**Research decision for map "Curriculum forge: GPU1 trains GPU0 via skill curriculum"**
**Grounded in:** the arena package as built and verified this session (arena/candidates.py, opponents.py, battle.py, war.py, agent.py, tech.py, train.py, export.py) and its outputs in data/arena/.

## 1. Measurable objectives (the gradeable universe)

Every skill's pass/fail must be a number the arena already computes. Verified sources:

| Objective | Source | Units / pass shape |
|---|---|---|
| Held-out discrimination, window 0-500 | `gate.results[0].margin` | ≥ +0.01 (per-trade fraction) |
| Held-out discrimination, window 1000-1250 | `gate.results[1].margin` | ≥ +0.01 |
| Unseen bear half (bars 250-500) | recompute like `discrim()` | ≥ +0.01 — the honest sub-window |
| Gate pass (both windows) | `gate.pass` | bool; protocol requires 2 consecutive |
| Arena z (agent) | `battle.standings.agent.arena_score` | > field z per opponent |
| Battle takes | `battle.standings.agent.takes` | > 0 |
| Head-to-head wins/losses | `battle.h2h[opponent]` | wins > losses |
| War book net return | `war.agent.net_return` | > 0, or > opponent's book |
| War book win rate / trades | `war.agent.win_rate`, `n_trades` | floor + count |
| War regime decomposition | `war_regime[book].up/down.mean_pnl_pct` | per-regime vs field |
| Bear-war relabel yield | `n_bear_relabels` | count of down-regime states trained |
| QLoRA adapter present | `data/gpu_scheduler/adapters/momentum-agent/summary.json` | exists |
| Adapter validation | `validate_momentum_agent.py` output | discrim ≥ bar |
| Tech-tree node lit | `data/arena/tech_tree.json` discovered | node id |

## 2. Scenario matrix

A skill's scenario = window × regime × field, using components that already exist:

- **Windows** (5y master index): `0-250` early bear, `250-500` late bear, `500-1000` bull (train), `1000-1250` 2026 unseen. The war also has `2y`/`5y` archive periods.
- **Regime**: up (SPY > 96d MA), down, mixed.
- **Field subsets** (from opponents.py): full field; momentum-aligned {rule-config, ahl}; contrarian {citadel, citron}; baselines {always-take, always-skip, random}; single-persona duels {citadel} etc.

## 3. Skill definition schema

```json
{
  "id": "s12-bull-bear-balance",
  "name": "Bull+bear balance",
  "tier": 4,
  "prerequisites": ["s04-unseen-bear-half", "s05-window-2026"],
  "scenario": {"window": "mixed", "regime": "mixed", "field": "full"},
  "objective": "gate_margins",
  "pass_bar": {"windows": ["0-500", "1000-1250"], "min_margin": 0.01, "consecutive": 3},
  "metric_source": "gate.results[*].margin",
  "stick": {"retry_drop_tier": 1, "max_failures_before_remedial": 2}
}
```

Composition rules: a skill's prerequisites must be lit tech-tree nodes or mastered skills; tiers gate upward (T5 requires T4); the pass bar must reference a metric_source that exists in arena_state.json or a named recomputation.

## 4. Seed skills (~15, tiered)

**Tier 1 — fundamentals**
- s01 takes-in-ring — takes > 0
- s02 beats-field — arena z > 0
- s03 war-book-profit — agent war net_return > 0
- s04 unseen-bear-half — margin 250-500 ≥ +1%
- s05 window-2026 — margin 1000-1250 ≥ +1%

**Tier 2 — opponent duels (battle ring)**
- s06 beats-always-take — z > always-take z
- s07 beats-random — z > random z
- s08 trend-ride — war P&L > ahl in up-regime
- s09 range-defense — war P&L > citadel in down/mixed

**Tier 3 — persona gauntlet**
- s10 hype-fade-duel — h2h wins > losses vs citron AND war P&L > citron
- s11 hedge-fund-gauntlet — war P&L > citadel AND > ahl AND > citron

**Tier 4 — mastery**
- s12 bull-bear-balance — both windows ≥ +1% for 3 consecutive iterations
- s13 gate-locked — 2 consecutive gate passes
- s14 qlora-distilled — adapter exists AND validation discrim ≥ bar

**Tier 5 — graduation**
- s15 mot-weight — momentum agent earns MoT weight (validation gate pass + shadow)

## 5. How skills compose

- Prerequisite ladder = directed acyclic graph over the tech-tree nodes + mastered skills.
- Difficulty tier = max(prereq tiers) + 1, clamped.
- A skill is "attemptable" when all prerequisites are lit; the student trains on its scenario via the existing iteration loop (battle-z targets + war relabels + bear-war relabels), and mastery is checked against `pass_bar` from the latest arena_state.json.
- The stick: 2 failures → skill drops one tier ("remedial"), a retrain flag is set, and the war-vs-field requirement applies before the next tier is attempted.
