# PROTOTYPE — Doob L^p Maximal Inequality as a drawdown bound

**Throwaway.** Question being answered: can Doob's L^p maximal inequality
give a usable worst-case bound on the running maximum (max adverse excursion)
of the equity curve, given (1) the drift/submartingale caveat and (2) the
looseness of the classical constant `(p/(p-1))^p`?

**Run:**
```
PYTHONPATH=. python3 risk/doob_tui.py
```

Keys: `[n]` new path · `[d]` drift/step · `[v]` vol/step · `[p]` sweep p=1.5,2,3,4 · `[q]` quit

**Structure:**
- `doob_prototype.py` — pure, portable logic (de-mean to martingale component,
  compute LHS/RHS, evaluate bound) — the keepable part
- `doob_tui.py` — throwaway terminal shell

**Status:** prototype in hand — pending the Doob paper's specific refinement
to swap in the tight constant. Logic verified sane (bound holds; tightness
0.24–0.74 across p, confirming the loose-constant caveat).
