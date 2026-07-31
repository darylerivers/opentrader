"""PROTOTYPE — Doob L^p maximal inequality as a worst-case drawdown bound.

Question being prototyped:
    Can Doob's L^p maximal inequality give a usable worst-case bound on the
    running maximum (max adverse excursion) of the equity curve for this
    trading system, given two caveats?
      Caveat 1: a profitable strategy has drift -> the equity curve is a
                SUBmartingale, not a martingale. The inequality applies to
                the de-meaned (martingale) component of P&L returns.
      Caveat 2: the classical constant (p/(p-1))^p is known to be loose.
                Does the bound actually bind, or is it vacuous at the p values
                a trader would plausibly pick?

This module is PURE logic (no I/O, no terminal code) so it can be lifted
into risk/manager.py later. The TUI shell is in doob_tui.py.

Classical result (Doob): for a martingale M and p > 1,
    E[ max_{k<=n} |M_k|^p ] <= (p/(p-1))^p * E[ |M_n|^p ].
For a submartingale X with X_0 = 0, the relevant object is the martingale
component M_n = X_n - sum of predictable compensators. We approximate the
compensator by the running sample mean of per-step increments (a simple
estimator of the drift), giving an empirical martingale component.

PROTOTYPE — throwaway. Not for production use.
"""

from __future__ import annotations

import math
from dataclasses import dataclass, field
from typing import List, Optional


# ── Pure logic: Doob bound machinery ────────────────────────────────────


def doob_constant(p: float) -> float:
    """Classical Doob L^p constant (p/(p-1))^p for p > 1."""
    return (p / (p - 1.0)) ** p


def martingale_component(returns: List[float]) -> List[float]:
    """De-mean a return series to isolate its martingale component.

    Caveat-1 handling: subtract the running sample mean of prior increments
    as a simple drift/compensator estimate. The residual is the part the
    inequality can bound.
    """
    out: List[float] = []
    if not returns:
        return out
    acc = 0.0
    for i, r in enumerate(returns):
        drift = (acc / i) if i > 0 else 0.0
        out.append(r - drift)
        acc += r
    return out


def running_max_abs(values: List[float]) -> float:
    """M^*_n = max_{k<=n} |partial sum_k|."""
    s = 0.0
    m = 0.0
    for v in values:
        s += v
        m = max(m, abs(s))
    return m


def pth_moment(values: List[float], p: float) -> float:
    """E[|partial sum_n|^p] — terminal partial-sum moment."""
    if not values:
        return 0.0
    s = sum(values)
    return abs(s) ** p


def empirical_moment_running_max(returns: List[float], p: float) -> float:
    """E[ (M^*_n)^p ] estimated from a single path (no expectation, n=1)."""
    m = running_max_abs(returns)
    return m**p


@dataclass
class DoobReport:
    """The state a Doob-bound evaluation exposes to the TUI."""

    p: float
    n: int
    raw_total: float  # sum of raw returns
    mart_total: float  # sum of martingale component
    raw_running_max: float
    mart_running_max: float  # M^*_n of martingale component
    empirical_lhs: float  # (M^*_n)^p
    doob_rhs: float  # C_p * E[|M_n|^p]
    bound_holds: bool
    tightness: (
        float  # empirical_lhs / doob_rhs (<1 = bound binds at least this fraction)
    )
    margin_pct: float  # (rhs-lhs)/lhs*100 — how much slack
    history: List[dict] = field(default_factory=list)

    def as_row(self) -> dict:
        return {
            "p": self.p,
            "n": self.n,
            "mart_total": round(self.mart_total, 6),
            "raw_max": round(self.raw_running_max, 6),
            "mart_max": round(self.mart_running_max, 6),
            "lhs": round(self.empirical_lhs, 6),
            "rhs": round(self.doob_rhs, 6),
            "holds": self.bound_holds,
            "tightness": round(self.tightness, 4),
            "margin_pct": round(self.margin_pct, 1),
        }


def evaluate(returns: List[float], p: float) -> DoobReport:
    """Full Doob evaluation on a single P&L path (scaled to cash %)."""
    mart = martingale_component(returns)
    lhs = empirical_moment_running_max(mart, p)
    rhs = doob_constant(p) * pth_moment(mart, p)
    raw_max = running_max_abs(returns)
    mart_max = running_max_abs(mart)
    # Guard: rhs could be 0 on a pathological all-flat martingale
    bound_holds = lhs <= rhs + 1e-12
    tightness = (lhs / rhs) if rhs > 1e-12 else float("inf")
    margin = ((rhs - lhs) / lhs * 100.0) if lhs > 1e-12 else float("inf")
    return DoobReport(
        p=p,
        n=len(returns),
        raw_total=sum(returns),
        mart_total=sum(mart),
        raw_running_max=raw_max,
        mart_running_max=mart_max,
        empirical_lhs=lhs,
        doob_rhs=rhs,
        bound_holds=bound_holds,
        tightness=tightness,
        margin_pct=margin,
    )


def synthesize_path(
    n: int,
    drift_per_step: float,
    vol_per_step: float,
    seed: Optional[int] = None,
) -> List[float]:
    """Generate a P&L path (per-step % returns). drift>0 => submartingale."""
    import random

    if seed is not None:
        random.seed(seed)
    return [random.gauss(drift_per_step, vol_per_step) for _ in range(n)]


def try_bounds(paths: List[List[float]], p_values: List[float]) -> List[dict]:
    """Batch: for each (path, p), does the bound hold and how tight?"""
    rows = []
    for path in paths:
        for p in p_values:
            rep = evaluate(path, p)
            rows.append(rep.as_row())
    return rows


# ── Weak-type (1,1) bound (the actionable form) ────────────────────────


@dataclass
class WeakTypeReport:
    """State for the weak-type (1,1) maximal inequality test.

    Classical result (Doob paper sec.1): for a non-negative submartingale X,
        P[X*_n >= t] <= t^{-1} E[X_n].
    This is the practically usable risk bound: it bounds the probability of
    the running max (drawdown) exceeding a level t in terms of the expected
    terminal value. On a single path we check the Markov-style corollary
    X*_n <= t * E[X_n].
    """

    t: float
    running_max: float
    expected_terminal: float
    max_allowable: float  # t * E[X_n] — what the bound permits
    holds: bool  # running_max <= max_allowable
    slack_pct: float  # (allowable - running_max)/running_max*100


def evaluate_weak_type(returns: List[float], t: float) -> WeakTypeReport:
    """Weak-type check on the positive submartingale X = |partial sums|.

    X_n = (partial sum_n)^+ is a non-negative submartingale; E[X_n] is the
    average positive partial sum. The bound says P[X*_n >= t] <= E[X_n]/t;
    per-path (Markov on one sample) this implies X*_n <= t * E[X_n].
    """
    if not returns:
        return WeakTypeReport(
            t=t,
            running_max=0.0,
            expected_terminal=0.0,
            max_allowable=0.0,
            holds=True,
            slack_pct=0.0,
        )
    s = 0.0
    pos_sums = []
    run_max = 0.0
    for r in returns:
        s += r
        pos_sums.append(max(0.0, s))
        run_max = max(run_max, max(0.0, s))
    E_terminal = sum(pos_sums) / len(pos_sums) if pos_sums else 0.0
    allowable = t * E_terminal if E_terminal > 0 else float("inf")
    holds = run_max <= allowable + 1e-12
    slack = (
        ((allowable - run_max) / run_max * 100.0) if run_max > 1e-12 else float("inf")
    )
    return WeakTypeReport(
        t=t,
        running_max=round(run_max, 6),
        expected_terminal=round(E_terminal, 6),
        max_allowable=round(allowable, 6),
        holds=holds,
        slack_pct=slack,
    )
