"""PVA (Portfolio Value Analysis) — Portfolio visualization helpers.

Extracted from tui_dashboard.py; kept separate for cleaner imports.
"""

import json
from pathlib import Path

from .harness import reader


def _list_history_files(history_dir: Path) -> list[Path]:
    return sorted(history_dir.glob("data_*.json"), key=lambda x: x.stat().st_mtime)


_pva_cache = {"points": [], "count": 0, "file_count": 0}


def get_pva_points(history_dir: Path):
    """Build portfolio value over time for visualization."""
    if not history_dir.exists():
        return {"points": [], "count": 0}

    files = _list_history_files(history_dir)
    fc = _pva_cache["count"]
    if _pva_cache["result"] is not None and fc == _pva_cache["file_count"]:
        result = dict(_pva_cache["result"])
        points = list(result.get("points", []))
        base_portfolio = points[0]["portfolio"] if points else None
        base_prices = {}
        for p in points:
            for k, v in p.items():
                if k not in ("ts", "portfolio") and v != 0 and k not in base_prices:
                    base_prices[k] = v
            try:
                s = reader.read_state()
                pv = s.get("portfolio_value", 0)
                prices = s.get("prices", {})
                # Build base_prices from BOTH history AND live state
                # so symbols not in history are added (fix: P3-4 PVA cache miss for new symbols)
                for sym, px in prices.items():
                    sym_short = sym.split("/")[0]
                    if sym_short not in base_prices and px > 0:
                        base_prices[sym_short] = px
                ts = s.get("timestamp", "")
                if base_portfolio is None and pv > 0:
                    base_portfolio = pv
                if pv > 0 and base_portfolio:
                    pt = {"ts": str(ts)[:19], "portfolio": round((pv / max(base_portfolio, 0.01) - 1) * 100, 2)}
                    result["points"] = points + [pt]
                return result
            except Exception:
                pass
        return result

    points = []
    base_portfolio = None
    base_prices = {}

    sample_n = max(1, len(files) // 800)
    for f in files[::sample_n]:
        try:
            d = json.loads(f.read_text())
        except Exception:
            continue
        pv = d.get("portfolio_value", 0)
        prices = d.get("prices", {})
        ts = d.get("timestamp", "")
        if pv <= 0: continue
        if base_portfolio is None: base_portfolio = pv
        point = {"ts": str(ts)[:19], "portfolio": round((pv / base_portfolio - 1) * 100, 2)}
        for sym, px in prices.items():
            sym_short = sym.split("/")[0]
            if sym_short not in base_prices and px > 0: base_prices[sym_short] = px
            if sym_short in base_prices and base_prices[sym_short] > 0:
                point[sym_short] = round((px / base_prices[sym_short] - 1) * 100, 2)
        points.append(point)

    # Append current live data point from paper_state.json
    try:
        s = reader.read_state()
        pv = s.get("portfolio_value", 0)
        prices = s.get("prices", {})
        if base_portfolio is None: base_portfolio = pv
        if pv > 0:
            point = {"ts": str(ts)[:19], "portfolio": round((pv / base_portfolio - 1) * 100, 2)}
            for sym, px in prices.items():
                sym_short = sym.split("/")[0]
                if sym_short not in base_prices and px > 0: base_prices[sym_short] = px
                if sym_short in base_prices and base_prices[sym_short] > 0:
                    point[sym_short] = round((px / base_prices[sym_short] - 1) * 100, 2)
            points.append(point)
    except Exception:
        pass

    _pva_cache["file_count"] = fc
    _pva_cache["result"] = {"points": points, "count": len(points)}
    return _pva_cache["result"]
