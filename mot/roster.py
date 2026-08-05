"""The expert roster — the "many MB models" vision, realized as specializations.

Each specialization describes one value-head expert: which candidate universe,
which feature extractor, which data source, which checkpoint. The RegimeRouter
routes among *validated* experts; the rule floor holds until an expert earns
per-regime weight. This is the registry Phase 4 of the roadmap: generalize the
arena loop so a new expert is a config entry, not a fork of the code.

Status semantics:
  - ready    -> data + feature pipeline exist; train_expert() can run today
  - prototype-> feature pipeline exists (e.g. value_head_1m macro path); needs
               the per-expert candidate collector wired into the arena
  - planned  -> data source not yet in-process (crypto archive missing,
               sentiment null-result per five-data-sources evaluation)
"""
from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Optional

from mot.experts import ValueHeadExpert

PROJECT = Path(__file__).resolve().parent.parent
ARENA_OUT = PROJECT / "data" / "arena"


@dataclass
class ExpertSpec:
    id: str
    name: str
    description: str
    status: str                 # ready / prototype / planned
    checkpoint: Optional[Path] = None
    universe: str = "US 17-sym (SPY + 16 tradeables)"
    feature_plan: str = ""
    data_plan: str = ""


SPECIALIZATIONS: dict = {
    "momentum": ExpertSpec(
        id="momentum",
        name="Momentum value head",
        description="US cross-sectional momentum: V(state)->E[10-bar fwd], the arena's incumbent.",
        status="ready",
        checkpoint=ARENA_OUT / "arena_value_head.pt",
        feature_plan="9 engineered OHLCV features + composite score + SPY ratio "
                     "(arena/candidates.py FEAT_COLS)",
        data_plan="5y daily archive, 17-symbol US universe (data/setup_search/ohlcv_5y.pkl)",
    ),
    "macro": ExpertSpec(
        id="macro",
        name="Macro / rate-sensitivity value head",
        description="FRED + VIX + breadth features (the value_head_1m reuse path).",
        status="prototype",
        checkpoint=None,
        feature_plan="value_head_1m features: cross-sectional ranks + DFF/DGS10/CPIAUCSL + VIX + breadth",
        data_plan="data/macro_cache.json + FRED (api in data/connections.json)",
    ),
    "sentiment": ExpertSpec(
        id="sentiment",
        name="Sentiment value head",
        description="News/social sentiment (FinBERT on tweets evaluated null; reddit/news not yet integrated).",
        status="planned",
        feature_plan="news/social sentiment scores from data/news_cache.json, social_cache.json",
        data_plan="caches exist; the five-data-sources evaluation found no added value yet",
    ),
    "crypto": ExpertSpec(
        id="crypto",
        name="Crypto value head",
        description="BTC/ETH/SOL leg (kraken).",
        status="planned",
        feature_plan="crypto OHLCV + regime leader (setup_search/crypto_leg.py)",
        data_plan="crypto_ohlcv.pkl archive NOT present (war-referee note) — needs kraken fetch",
    ),
    "international": ExpertSpec(
        id="international",
        name="International value head",
        description="International indices/currencies (the user's 'brewing problems abroad' surface).",
        status="planned",
        feature_plan="non-US index + FX + commodity OHLCV",
        data_plan="no archive yet — needs data source (e.g. yfinance international tickers)",
    ),
}


def list_roster() -> list:
    return [
        {"id": s.id, "name": s.name, "status": s.status}
        for s in SPECIALIZATIONS.values()
    ]


def build_expert(expert_id: str) -> Optional[ValueHeadExpert]:
    """Return a ValueHeadExpert wrapping the specialization's trained checkpoint,
    or None if not ready / no checkpoint yet."""
    spec = SPECIALIZATIONS.get(expert_id)
    if spec is None or spec.checkpoint is None:
        return None
    exp = ValueHeadExpert.from_checkpoint(spec.checkpoint, name=expert_id)
    return exp if exp.art is not None else None


def train_expert(expert_id: str, **kw) -> dict:
    """Train/iterate one specialization through the arena loop.

    Currently only 'momentum' has a full data+feature pipeline wired into the
    arena. Other specializations raise a clear NotBuildableError until their
    candidate collector exists — the roster mechanism, not the data, is the
    deliverable here.
    """
    spec = SPECIALIZATIONS.get(expert_id)
    if spec is None:
        raise KeyError(f"unknown expert '{expert_id}'")
    if spec.status != "ready":
        raise NotBuildableError(
            f"expert '{expert_id}' status={spec.status}: needs its candidate "
            f"collector wired into the arena (see ExpertSpec.data_plan)"
        )
    from arena.train import run_iteration
    rep = run_iteration(**kw)
    exp = build_expert(expert_id)
    return {"report": rep, "expert": exp}


class NotBuildableError(Exception):
    pass
