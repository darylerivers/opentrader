# Arena reward + war-relabeling protocol on the value-head loop

**Status:** Research decision — ready for the iteration-protocol grilling to consume.
**Date:** 2026-08-04
**Companion map:** [Momentum agent arena: RL candidate-battle + portfolio-war referee](https://github.com/darylerivers/opentrader/issues/61)
**Builds on:** [Apprentice learns to trade via RL from the rule playbook](https://github.com/darylerivers/opentrader/issues/35) (closed)

## Summary

The closed RL map left us a torch MLP value head `V(state) -> E[forward return]` with a
`+1%` held-out discrimination bar and a rule-gate veto, but **no arena-relative reward**
and **no way for the portfolio war's episodic outcomes to reach the value head**. This
document closes both gaps, plus the arena-specific overfitting risk (memorizing the
opponent field instead of the market).

Three decisions:

1. **Battle reward:** keep the closed map's realized 10-bar forward return as the base
   signal, made arena-relative as a **cross-sectionally standardized margin over the
   round's field** (a z-score of the candidate's forward return against the round's
   candidate field). Head-to-head margin is the **episode-level war score** (agent
   portfolio P&L vs each persona); ordinal rank is the **standings/ladder metric** for
   the round-robin and the animation, not the value-head target.
2. **War-relabeling:** the war (referee, *between* iterations) runs the value-head-seeded
   agent against the field, then decomposes each episode back into per-state reward
   corrections — **advantage-style** — as `δ_t = (r_t − V(s_t)) + (r_t − r_field_t)`
   (critic advantage over the value baseline, plus the head-to-head margin over the
   field), computed **per regime window**, then added to the base target as an
   augmentation `r̃_t = r_t + η·δ_t` for the next iteration's value-head fit. The war
   **gates before it relabels** — relabeled targets never constitute a pass.
3. **Anti-overfitting:** held-out discrimination stays the gate (iteration #1 failed at
   `−2.50%`), and it now also splits **opponents**, not just time: the value head trains
   on a slice of the field and is gated on a fresh slice over the unseen regime windows,
   with persona stochasticity (the existing TraderBench difficulty transforms) and
   early-stop on held-out discrimination only — never in-ring win rate, which is the
   opponent-memorization signal.

---

## 1. Context — what the closed map already decided

The closed map [Apprentice learns to trade via RL from the rule playbook](https://github.com/darylerivers/opentrader/issues/35)
settled the base loop. Its three tickets, by title, are the contract this arena must not
rewrite:

- **[Audit the reward-labeled environment + RL infrastructure](https://github.com/darylerivers/opentrader/issues/36)**
  — the environment is **134 (state, reward) candidates over 5y**, regime-diverse
  (2022 bear → 2026), and the reward is the **10-bar forward return** (densest signal;
  trade P&L is selection-biased at 28 samples). `BehavioralRLTrainer` is **not reusable**
  — new trainer path.
- **[Design the policy architecture + anti-overfitting training loop](https://github.com/darylerivers/opentrader/issues/37)**
  — first build is a **torch MLP value head `V(state)->E[fwd]`** over the engineered
  features + composite score + regime; leakage rule = features at bar `t`, label at
  `t+FORWARD`; train `(500,1000)`, test `(0,500)` (incl. 2022 bear) `+ (1000,1250)`;
  **early-stop on held-out discrimination**, not train loss; L2/dropout; the value gate
  vetoes *within* the rule-passing set (rules stay primary).
- **[Set the reward, autonomy bar, and deployment](https://github.com/darylerivers/opentrader/issues/38)**
  — reward = 10-bar forward return (fee-penalized ok); synthetic traps in **eval only**;
  autonomy bar = held-out discrimination `(kept-mean − all-mean) ≥ +1%/trade` on **both**
  regime windows for **2 consecutive eval windows**; value-gate deployment, paper shadow
  first; failure rule = underperform floor → pure-rule + iterate.

Code evidence of the loop as built:

- `setup_search/value_head.py` — `ValueMLP` (11→32→16→1, ReLU + dropout 0.2), early-stop
  patience 15 on val MSE, θ tuned on the validation slice, gate = `margin ≥ +0.01` on both
  test windows. **Current state: FAILS the gate** — window `0-500` margin `+0.17%`,
  window `1000-1250` margin `−0.22%` (`data/research_gate/value_head_report.json`). This is
  the number the arena's first iteration must beat.
- `setup_search/value_head_1m.py` — the US-1m reuse of the same loop (240-bar forward,
  FRED/VIX/breadth/cross-sectional-rank features): proof the loop transfers across markets,
  which is what the "reusable for Risk/Bear and Macro/Sentiment" goal in the arena map's
  Destination requires. Also currently fails its gate.
- `setup_search/validate_momentum_agent.py` — iteration #1's QLoRA eval: `TAKE-mean −
  all-mean` over a held-out 2026 sample is the discrimination metric.
- `setup_search/trap_test.py` + `setup_search/trap_holdout.py` — the trap protocol:
  every screen-passer with realized forward returns, synthetic traps in eval only, and a
  **regime-split holdout** (train `500-1000`, judge `0-500` + `1000-1250`). The
  memorization failure it caught (held-out kept `0/115`; see `data/research_gate/trap_holdout.json`)
  is the reason the architecture moved off few-shot prompting to the value head.

---

## 2. Decision 1 — the battle reward

### The candidates, judged against the closed map's contract

| Candidate | What it rewards | Strengths | Why it does not stand alone here |
|---|---|---|---|
| **Rank-based** (ordinal within round) | position in the round's outcome ordering | scale-free; immune to bull/bear mean drift across the map's own test windows | discards magnitude — the closed map's bar and the value head's regression target are **in return units** (`+1%` discrimination, `E[fwd]`); a rank target breaks both |
| **Head-to-head margin** (agent's chosen-candidate returns vs a paired opponent) | beating the specific opponent | truest "battle" signal; directly encodes earning MoT weight | depends on pairing and opponent quality; sparse (only realized on the agent's TAKEs); a weak field inflates it |
| **Risk-adjusted forward return** (vol-scaled) | return per unit risk | the Risk/Bear persona's native language | needs a per-bar vol estimate — noise at the per-decision density the bandit needs; the closed map deliberately chose the densest raw signal |

### The decision

**Battle reward = the candidate's realized 10-bar forward return, standardized against
the round's field** — `r_arena(s,a) = (fwd(s) − μ_round) / (σ_round + ε)`, clipped, where
`μ_round`/`σ_round` are the mean/std of forward returns over the round's candidate field
(all agents' + the personas' candidates in that round).

This is deliberately a **hybrid** of the three options, and it is what "arena-relative"
means mechanically:

- **Head-to-head margin aggregated over the whole field** (not one paired opponent): the
  agent's candidates are judged against the entire round's outcome distribution, so
  opponent *quality* averages out instead of being an arbitrary pairing artifact.
- **Risk-adjusted without a vol model**: normalizing by the field's dispersion does the
  vol adjustment cross-sectionally — bear windows, with wider outcome dispersion, get a
  comparable "edge per unit of field volatility" signal to bull windows, keeping the
  closed map's two-regime bar meaningful.
- **Magnitude-preserving like a margin, not an ordinal**: the value head still regresses
  an `E[fwd]`-shaped target and the gate still reports raw `%` margins.

Layering, so each form is used where it earns its keep:

- **In-ring training reward:** the field-relative standardized forward return above.
- **Episode/war score (head-to-head margin at portfolio level):** the agent portfolio's
  realized P&L **vs each persona's portfolio P&L** on the same replay window — the
  portfolio-war research ticket's cheaply-computable signals (portfolio P&L, per-candidate
  drawdown contribution, per-regime decomposition).
- **Rank:** ordinal within round — the round-robin ladder, the animation's standings, and
  the war's persona ranking. Not the value-head target.

Continuity check: fee-penalization stays allowed and synthetic traps stay eval-only, per
the closed map's [Set the reward, autonomy bar, and deployment](https://github.com/darylerivers/opentrader/issues/38).

---

## 3. Decision 2 — the war-relabeling protocol (advantage-style)

The arena map's Notes fix the architecture: *candidate battle = the RL training loop
(thousands of rounds); portfolio war = referee between iterations (few runs, relabels
per-state rewards, gates); the bandit value head seeds + criticizes the war agent.* This
decision defines that "relabels per-state rewards."

### The protocol, in four steps

**Step 1 — Seed.** The value head `V(s) → E[fwd]` seeds the war agent's policy: take
candidate iff `V(s) ≥ θ`, with `θ` from the last iteration's validation-slice tuning
(exactly what `value_head.py` already does). The value head is also the **critic** for
Step 3.

**Step 2 — Run.** The agent and the opponent field trade the same replay window (the war
sim budget is the portfolio-war research ticket's deliverable). Record per decision:
state `s_t`, action `a_t`, candidate, realized forward return `r_t`, **regime window**
(2022 bear vs 2026), and each opponent's decision + outcome on the **same candidate**.

**Step 3 — Decompose episode → per-state corrections.** Because each candidate is an
independent trade (a contextual bandit, not a Markov chain — the closed map's framing),
the episodic return-to-go of a decision *is* its realized forward return, so no
discount-rollout is needed. The portfolio-level P&L and per-candidate drawdown
contribution (the war referee's signals) aggregate those per-decision returns into the
episode outcome, and the field baseline `r_field_t` (mean field outcome on that candidate)
into the head-to-head term.

Per-state advantage-style correction:

```
δ_t = ( r_t − V(s_t) )   +   ( r_t − r_field_t )
       ── critic advantage over the value baseline ──   ── head-to-head margin vs the field ──
```

- The first term is REINFORCE-with-critic credit assignment: the decision's realized
  outcome minus what the value head expected — the "value head criticizes the war agent"
  half of the map's Notes. Positive δ = the decision beat the learned expectation.
- The second term is the arena-relative half: the decision's outcome minus the field's
  outcome on the same candidate — *beating the field is what earns MoT weight*.
- **Per regime window**: δ is computed and pooled *within* each regime window (the bear
  and the bull separately), so the correction cannot be swamped by one regime — matching
  the closed map's both-windows bar.

**Step 4 — Relabel for the next iteration, then gate.**

- New per-state target for the next value-head fit: **`r̃_t = r_t + η·δ_t`**, `η ∈ (0,1)`
  a trust factor. The base target stays the realized forward return (continuity with the
  closed map); the advantage correction **reweights which states carry positive signal** —
  states where the agent beat the field get boosted, states where the field beat the agent
  get suppressed — without ever replacing the base reward.
- The war **gates before it relabels**: the iteration passes on **raw** held-out
  discrimination (next section) plus P&L-vs-field (the iteration-protocol ticket's
  secondary signal). Relabeled targets feed the *next* iteration's training only; a
  war-inflated reward can never constitute a pass.

This is exactly "how episodic outcomes decompose back into per-state reward
corrections — advantage-style": two baselines (value head + field) subtract out, the
residual advantage flows back to the states that caused it, regime-segmented.

---

## 4. Decision 3 — the anti-overfitting loop

The arena adds a **second** overfitting axis the closed map never had: with a fixed field
of deterministic persona bots over thousands of rounds, a value head can learn to exploit
**opponent quirks** rather than market edge. The closed map's time-regime overfit was
already caught (trap holdout kept `0/115`). The arena protocol must prevent and detect
both.

### The protocol

1. **Held-out discrimination stays the only gate.** Unchanged from the closed map and the
   arena map's Destination: `kept-mean − all-mean ≥ +1%/trade` on **both** regime windows
   (2022 bear + 2026), 2 consecutive eval windows. Iteration #1 missed at **−2.50%**
   (TAKE-mean `+0.00%` vs all `+2.50%`; `data/research_gate/momentum_agent_validation.json`).
   The gate always measures **raw** realized forward returns on un-relabeled candidates —
   synthetic traps stay eval-only (closed map), and the war's relabel never touches the
   gate's data.
2. **Opponent split mirrors the regime split.** The value head trains on battles against a
   **training slice** of the opponent field; the held-out gate also runs against a
   **fresh slice of personas the agent never battled**, over the unseen regime windows.
   Beating familiar opponents is not progress; beating unseen opponents on unseen regimes
   is.
3. **Persona stochasticity + rotation.** Persona bots carry behavioral variance, and
   rounds draw random opponent subsets — no fixed `(state, opponent) → outcome`
   correlation can be learned. The difficulty ladder already exists to keep opponents
   honest: `training/traderbench.py` ships `baseline` / `noisy` / `meta` / `adversarial`
   transforms and a fee/slippage-aware `Simulator`.
4. **Early-stop on held-out discrimination, never in-ring win rate.** In-ring win rate is
   the **memorization signal** — it climbs exactly as the agent exploits opponent quirks —
   so it must not drive training. The closed map's early-stop discipline (patience on the
   held-out slice, not train loss) extends to a **held-out opponent slice**.
5. **Catch both degenerate modes.** Iteration #1 failed *down* (SKIP-everything, TAKE-mean
   `+0.00%`); a rubber-stamp can fail *up* (takes everything, traps and all — the trap
   protocol's exact bar). The `+1%` two-window discrimination bar catches both: the
   current value-head v1 already fails it (`+0.17%` / `−0.22%`), so the arena's first win
   is simply clearing the bar the closed map already set.

---

## 5. Dependencies and handoff

- **Consumes:** the portfolio-war research ticket's war-sim recipe and its relabelable
  outcome signals (portfolio P&L, per-candidate drawdown contribution, per-regime
  decomposition) — this ticket is blocked by it; the protocol above is written against
  those signals.
- **Consumed by:** the iteration-protocol ticket (cadence, war schedule, what passes), which
  this ticket blocks — it supplies the reward definition, the relabel mechanic, and the
  gate, so that ticket can decide cadence and acceptance without re-deciding rewards.
- **Fits the field:** the persona playbooks research ticket supplies the opponent field
  the battle and the war run against; opponent-vs-held-out slicing (Decision 3.2) assumes
  that field is generated from playbooks, not a fixed list.

## Sources

Tickets (cited by title, per wayfinder convention):

- [Momentum agent arena: RL candidate-battle + portfolio-war referee](https://github.com/darylerivers/opentrader/issues/61) — Destination, Notes (battle=training loop, war=referee between iterations, bandit value head seeds + criticizes), baseline failure −2.50%.
- [Apprentice learns to trade via RL from the rule playbook](https://github.com/darylerivers/opentrader/issues/35) — closed map, framing as contextual bandit.
- [Audit the reward-labeled environment + RL infrastructure](https://github.com/darylerivers/opentrader/issues/36) — 134 candidates over 5y, 10-bar fwd reward, trainer not reusable.
- [Design the policy architecture + anti-overfitting training loop](https://github.com/darylerivers/opentrader/issues/37) — MLP value head, train/test windows, early-stop on held-out discrimination, value gate.
- [Set the reward, autonomy bar, and deployment](https://github.com/darylerivers/opentrader/issues/38) — +1% both-windows bar, 2 consecutive windows, traps eval-only, fee-penalized ok.
- [Portfolio war referee: what to reuse + speed budget](https://github.com/darylerivers/opentrader/issues/63) — relabelable outcome signals (P&L, per-candidate drawdown contribution, per-regime decomposition).
- [Iteration protocol + acceptance gate: cadence, war schedule, what passes](https://github.com/darylerivers/opentrader/issues/67) — P&L-vs-field as secondary signal; consumes this protocol.
- [Hedge-fund persona playbooks for the arena (Citadel, Citron, ...)](https://github.com/darylerivers/opentrader/issues/62) — the opponent field.

Code and data:

- `setup_search/value_head.py` — ValueMLP, early-stop, θ tuning, gate; current FAIL (`data/research_gate/value_head_report.json`: `+0.17%` / `−0.22%`).
- `setup_search/value_head_1m.py` — reuse pattern across markets (the other-role-agents goal).
- `setup_search/validate_momentum_agent.py` — iteration #1 eval; `data/research_gate/momentum_agent_validation.json` (`taken=0`, margin `−2.50%`).
- `setup_search/trap_test.py`, `setup_search/trap_holdout.py` — trap protocol; `data/research_gate/trap_holdout.json` (held-out kept `0/115`).
- `training/traderbench.py` — Simulator (fee 4bps, slippage 5bps, half-Kelly), transforms baseline/noisy/meta/adversarial.
