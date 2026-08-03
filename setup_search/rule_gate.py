#!/usr/bin/env python3
"""The rule playbook as a gate: the validated rule-based config's screen.

Weaponizing the playbook = wrapping the LLM debate in this discipline:
- regime gate (SPY > SMA) must allow longs,
- the symbol's composite technical score (momentum/RSI/breakout blend) must
  clear `buy_thresh`,
- fee-aware sizing/min-notional stay as-is (in the risk manager).

The LLM may only act on names that pass; it can down-weight/veto within bounds
but never enter a name the rules reject. Reuses the setup_search engine's
feature math so the gate is byte-identical to the validated config.
"""

import json
from pathlib import Path

from setup_search.core import clamp_config
from setup_search.data import REGIME_SYM
from setup_search.engine import _features, _score_at

PROJECT = Path(__file__).resolve().parent.parent


def load_rule_config() -> dict:
    """The validated best config (the playbook)."""
    cfg = json.loads((PROJECT / "data/setup_search/best.json").read_text())
    return clamp_config(cfg.get("config", {}))


def screen(closes: dict, highs: dict, lows: dict, vols: dict, sym: str, date, cfg: dict = None, regime_sym: str = None) -> tuple:
    """Return (pass_bool, score) for the rule-playbook entry gate.

    pass iff regime allows longs AND composite score >= buy_thresh.
    regime_sym overrides the default regime market (SPY); crypto uses BTC.
    """
    cfg = cfg or load_rule_config()
    regime_sym = regime_sym or REGIME_SYM
    feat = _features(closes, highs, lows, vols, cfg)
    if sym not in feat or date not in feat[sym].index:
        return False, 0.0
    spy = closes.get(regime_sym)
    regime_ok = True
    if cfg["regime_filter"] and spy is not None:
        ma = spy.rolling(int(cfg["regime_window"]), min_periods=10).mean()
        v = ma.get(date)
        regime_ok = bool(v is not None and float(spy[date]) > float(v))
    score = float(_score_at(
        {s: feat[s].loc[date] for s in feat}, cfg, {s: 0.0 for s in feat}
    )[sym])
    return (regime_ok and score >= cfg["buy_thresh"]), round(score, 4)


def screen_signal(cfg, closes, highs, lows, vols, sym, date) -> tuple:
    """Same as screen() but with an explicit cfg — convenient for the harness."""
    return screen(closes, highs, lows, vols, sym, date, cfg)
