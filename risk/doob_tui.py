#!/usr/bin/env python3
"""PROTOTYPE TUI — Doob L^p maximal inequality worst-case drawdown bound.

Drive it by hand: add synthetic P&L paths with different drift/vol, sweep p,
and watch whether Doob's bound actually holds and how tight it is (the two
caveats). The logic lives in risk/doob_prototype.py (pure, portable).

PROTOTYPE — throwaway shell. The logic module is the keepable bit.

Run: python3 risk/doob_tui.py
"""

import sys

from risk.doob_prototype import (
    doob_constant,
    evaluate,
    synthesize_path,
)

BOLD = "\x1b[1m"
DIM = "\x1b[2m"
RESET = "\x1b[0m"


class State:
    def __init__(self):
        self.path = [0.0, 0.0, 0.0]  # per-step % returns
        self.p = 2.0
        self.drift = 0.001  # per-step drift (submartingale when >0)
        self.vol = 0.01
        self.rows = []  # sweep history: list of row dicts


def render(state: State) -> str:
    rep = evaluate(state.path, state.p)
    lines = []
    lines.append(
        f"{BOLD}Doob L^p Maximal Inequality — worst-case drawdown bound{RESET}"
    )
    lines.append("")
    lines.append(
        f"  {DIM}classical constant C_p=(p/(p-1))^p = {doob_constant(state.p):.4f}{RESET}"
    )
    lines.append("")
    lines.append(f"  {BOLD}p{RESET}            {state.p:.2f}")
    lines.append(f"  {BOLD}n (steps){RESET}    {len(state.path)}")
    lines.append(
        f"  {BOLD}drift/step{RESET}   {state.drift:+.4f}   {DIM}(>0 → submartingale, caveat 1){RESET}"
    )
    lines.append(f"  {BOLD}vol/step{RESET}     {state.vol:.4f}")
    lines.append("")
    lines.append(f"  {BOLD}raw total{RESET}        {rep.raw_total:+.6f}")
    lines.append(
        f"  {BOLD}mart. total{RESET}      {rep.mart_total:+.6f}   {DIM}(de-meaned, caveat 1){RESET}"
    )
    lines.append(f"  {BOLD}raw running max{RESET}  {rep.raw_running_max:.6f}")
    lines.append(f"  {BOLD}mart running max{RESET} {rep.mart_running_max:.6f}")
    lines.append("")
    lines.append(f"  {BOLD}LHS (M*_n)^p{RESET}  {rep.empirical_lhs:.6e}")
    lines.append(f"  {BOLD}RHS C_p·E|M_n|^p{RESET} {rep.doob_rhs:.6e}")
    verdict = f"{BOLD}{'BOUND HOLDS' if rep.bound_holds else 'BOUND VIOLATED'}{RESET}"
    lines.append(f"  {BOLD}verdict{RESET}        {verdict}")
    tight = (
        f"{rep.tightness:.2f}× of the bound used"
        if rep.tightness != float("inf")
        else "∞ (rhs≈0)"
    )
    lines.append(
        f"  {BOLD}tightness{RESET}      {tight}   {DIM}(1.0 = bound is exactly binding; <<1 = loose, caveat 2){RESET}"
    )
    lines.append(
        f"  {BOLD}slack margin{RESET}   {rep.margin_pct:+.1f}%   {DIM}(>0 = headroom; <0 = violation){RESET}"
    )
    lines.append("")
    lines.append(
        f"  {DIM}last 5 steps: {[round(v, 4) for v in state.path[-5:]]}{RESET}"
    )
    if state.rows:
        lines.append("")
        lines.append(f"  {BOLD}sweep history{RESET}")
        for r in state.rows[-6:]:
            lines.append(
                f"    p={r['p']:.1f} n={r['n']} drift={r.get('drift', 0):+.3f} "
                f"→ {'HOLDS' if r['holds'] else 'VIOL'} "
                f"tight={r['tightness']:.2f} margin={r['margin_pct']:+.0f}%"
            )
    lines.append("")
    lines.append(
        f"  {BOLD}[n]{RESET}{DIM} new path{RESET}  "
        f"{BOLD}[d]{RESET}{DIM} drift{RESET}  "
        f"{BOLD}[v]{RESET}{DIM} vol{RESET}  "
        f"{BOLD}[p]{RESET}{DIM} sweep p=1.5,2,3,4{RESET}  "
        f"{BOLD}[q]{RESET}{DIM} quit{RESET}"
    )
    return "\n".join(lines)


def read_float(prompt: str, default: float) -> float:
    try:
        return float(input(prompt).strip() or default)
    except ValueError:
        return default


def main() -> None:
    state = State()
    print("\033[2J\033[H", end="")
    print(render(state), end="")
    while True:
        try:
            k = input("\n> ").strip()
        except (EOFError, KeyboardInterrupt):
            break
        if k in ("q", "quit"):
            break
        elif k in ("n", ""):
            state.path = synthesize_path(
                60, drift_per_step=state.drift, vol_per_step=state.vol, seed=None
            )
            state.rows = []
        elif k == "d":
            state.drift = read_float(f"  drift/step [{state.drift:+g}]: ", state.drift)
        elif k == "v":
            state.vol = read_float(f"  vol/step [{state.vol:g}]: ", state.vol)
        elif k == "p":
            for p in (1.5, 2.0, 3.0, 4.0):
                rep = evaluate(state.path, p)
                row = rep.as_row()
                row["drift"] = state.drift
                state.rows.append(row)
        print("\033[2J\033[H", end="")
        print(render(state), end="")


if __name__ == "__main__":
    main()
