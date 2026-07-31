# PROTOTYPE — Doob L^p Maximal Inequality as a drawdown bound

**Throwaway.** Question: can Doob's L^p maximal inequality give a usable
worst-case bound on the running maximum (max adverse excursion) of the equity
curve, given (1) the drift/submartingale caveat and (2) the looseness of the
classical constant?

**Run:**
```
PYTHONPATH=. python3 risk/doob_tui.py
```

Keys: `[n]` new path · `[d]` drift/step · `[v]` vol/step · `[p]` sweep p=1.5,2,3,4 · `[q]` quit

**Structure:**
- `doob_prototype.py` — pure, portable logic (de-mean to martingale component,
  compute LHS/RHS of the L^p bound, evaluate weak-type (1,1) bound)
- `doob_tui.py` — throwaway terminal shell

## Findings (verified against the source paper)

Source: Fitzsimmons, *Doob's Inequalities* (Math 280B, UCSD) — the classical
treatment the user pointed to. Key theorem (sec.5): for a positive
submartingale X, `||X*_n||_p <= C_p ||X_n||_p` with `C_p = p/(p-1)`.
Raising to the p-th power gives exactly the prototype's `(p/(p-1))^p` moment
form — the prototype math is faithful to the source.

1. **Caveat 1 confirmed.** As per-step drift grows, the raw running max
   explodes while the de-meaned (martingale) running max stays flat. The
   inequality must be applied to the martingale component, not the raw curve.

2. **Caveat 2 — corrected.** The constant `(p/(p-1))^p` is NOT loose in the
   worst case: the proof's Holder step is equality-attainable, so the bound is
   sharp *in expectation over the extremal distribution*. The prototype's
   tightness readings (0.24–0.74) reflect TYPICAL paths, where the bound has
   slack. So: sharp worst-case bound, loose on typical paths.

3. **Weak-type (1,1) is the actionable form.** `P[X*_n >= t] <= E[X_n]/t`
   directly bounds the PROBABILITY of a drawdown exceeding t — the natural
   circuit-breaker input. It routinely "violates" on single paths (correct:
   it's an ensemble statement), which means it must be evaluated over a Monte
   Carlo stress set of paths, not one realized curve.

## Status

Logic verified against the source paper. The weak-type form is the candidate
for `risk/manager.py` (a probability-of-excursion gate), but only with an
ensemble estimator. Riposo's paper (if distinct from the classical result) is
not yet incorporated.
