"""The value head: fit with arena targets, vote, gate.

Builds on the closed map 'Apprentice learns to trade via RL from the rule
playbook': torch MLP V(state) -> E[forward return], early-stop on held-out
discrimination, gate = >= +1% discrimination on both regime windows. The
arena variant accepts per-row targets (war-relabeled r-tilde or the plain
forward return) and reports the discrimination gate.
"""

import json
import statistics
from pathlib import Path

import numpy as np
import torch
import torch.nn as nn

from setup_search.value_head import THETA_BAR

PROJECT = Path(__file__).resolve().parent.parent
OUT = PROJECT / "data" / "arena"
SEED = 23
TRAIN = (500, 1000)
TESTS = [(0, 500), (1000, 1250)]
VAL_FRAC = 0.15


class ArenaMLP(nn.Module):
    def __init__(self, d_in, hidden=(64, 32)):
        super().__init__()
        layers = []
        prev = d_in
        for h in hidden:
            layers += [nn.Linear(prev, h), nn.ReLU(), nn.Dropout(0.2)]
            prev = h
        layers += [nn.Linear(prev, 1)]
        self.net = nn.Sequential(*layers)

    def forward(self, x):
        return self.net(x).squeeze(-1)


def _targets_for(rows, targets):
    if not targets:
        return np.array([r["fwd"] for r in rows], dtype=np.float32)
    return np.array(
        [targets.get((r["bar"], r["sym"]), r["fwd"]) for r in rows], dtype=np.float32
    )


def _device():
    return "cuda" if torch.cuda.is_available() else "cpu"


def fit(
    rows,
    targets=None,
    epochs=200,
    lr=1e-3,
    hidden=(64, 32),
    extra_rows=None,
    extra_targets=None,
):
    torch.manual_seed(SEED)
    np.random.seed(SEED)
    device = _device()
    print(f"[arena] fit on {device}" if device == "cuda" else "", flush=True)
    train = [r for r in rows if TRAIN[0] <= r["bar"] < TRAIN[1]]
    n_val = max(1, int(len(train) * VAL_FRAC))
    trn, val = train[: len(train) - n_val], train[-n_val:]
    if extra_rows:
        trn = extra_rows + trn
    X = np.stack([r["x"] for r in trn])
    base_y = _targets_for(trn, targets)
    if extra_rows and extra_targets:
        extra_by_key = {
            (r["bar"], r["sym"]): t for r, t in zip(extra_rows, extra_targets)
        }
        for i, r in enumerate(trn):
            key = (r["bar"], r["sym"])
            if key in extra_by_key:
                base_y[i] = extra_by_key[key]
    y = base_y.astype(np.float32)
    mean, std = X.mean(0), X.std(0)
    Xz = (X - mean) / (std + 1e-8)

    model = ArenaMLP(X.shape[1], hidden=hidden).to(device)
    opt = torch.optim.AdamW(model.parameters(), lr=lr, weight_decay=1e-4)
    lossf = torch.nn.MSELoss()
    Xt = torch.tensor(Xz, device=device)
    yt = torch.tensor(y, device=device)
    Xv = torch.tensor(
        (np.stack([r["x"] for r in val]) - mean) / (std + 1e-8), device=device
    )
    yv = torch.tensor(_targets_for(val, targets), device=device)
    best_val_loss, best_state, patience = 1e9, None, 0
    for _ in range(epochs):
        model.train()
        opt.zero_grad()
        loss = lossf(model(Xt), yt)
        loss.backward()
        opt.step()
        model.eval()
        with torch.no_grad():
            vl = float(lossf(model(Xv), yv))
        if vl < best_val_loss:
            best_val_loss, best_state, patience = (
                vl,
                {k: v.clone() for k, v in model.state_dict().items()},
                0,
            )
        else:
            patience += 1
            if patience >= 15:
                break
    model.load_state_dict(best_state)
    model.eval()

    def preds(rows):
        return predict_batch(
            {"model": model, "mean": mean, "std": std}, [r["x"] for r in rows]
        )

    vp = preds(val)
    best_theta, best_d = 0.0, -1e9
    for q in np.quantile(vp, np.linspace(0.05, 0.95, 19)):
        kept = [r["fwd"] for r, p in zip(val, vp) if p >= q]
        allm = statistics.mean(r["fwd"] for r in val)
        km = statistics.mean(kept) if kept else 0.0
        d = km - allm
        if d > best_d:
            best_d, best_theta = d, float(q)

    results = []
    for lo, hi in TESTS:
        win = [r for r in rows if lo <= r["bar"] < hi]
        wp = preds(win)
        kept_f = [r["fwd"] for r, p in zip(win, wp) if p >= best_theta]
        all_m = statistics.mean(r["fwd"] for r in win)
        kept_m = statistics.mean(kept_f) if kept_f else 0.0
        results.append(
            {
                "window": f"{lo}-{hi}",
                "n": len(win),
                "kept": len(kept_f),
                "kept_mean": kept_m,
                "all_mean": all_m,
                "margin": kept_m - all_m,
            }
        )
    passed = [r for r in results if r["margin"] >= THETA_BAR]
    pass_gate = len(passed) == len(results)
    report = {
        "train_window": list(TRAIN),
        "test_windows": [list(t) for t in TESTS],
        "n_train": len(trn),
        "n_val": len(val),
        "val_mse": best_val_loss,
        "theta": best_theta,
        "results": results,
        "pass": pass_gate,
    }
    return {
        "model": model,
        "theta": best_theta,
        "mean": mean,
        "std": std,
        "report": report,
        "pass": pass_gate,
    }


def save(art, path=None):
    path = path or OUT / "arena_value_head.pt"
    OUT.mkdir(parents=True, exist_ok=True)
    torch.save(
        {
            "state": art["model"].state_dict(),
            "theta": art["theta"],
            "mean": art["mean"],
            "std": art["std"],
            "report": art["report"],
            "hidden": art.get("hidden", (64, 32)),
        },
        path,
    )
    (OUT / "arena_report.json").write_text(
        json.dumps(art["report"], indent=1, default=str)
    )
    return path


def load(path=None):
    path = path or OUT / "arena_value_head.pt"
    try:
        ck = torch.load(path, map_location="cpu", weights_only=False)
        hidden = tuple(ck.get("hidden", (32, 16)))
        model = ArenaMLP(ck["mean"].shape[0], hidden=hidden)
        model.load_state_dict(ck["state"])
    except Exception:
        return None
    model.eval()
    return {
        "model": model,
        "theta": ck["theta"],
        "mean": ck["mean"],
        "std": ck["std"],
        "report": ck.get("report", {}),
        "hidden": hidden,
    }


def load_report(path=None):
    path = path or OUT / "arena_value_head.pt"
    try:
        ck = torch.load(path, map_location="cpu", weights_only=False)
        return ck.get("report", {})
    except Exception:
        return {}


def predict_batch(art, xs):
    model, mean, std = art["model"], art["mean"], art["std"]
    device = _device()
    model = model.to(device)
    X = np.stack([np.asarray(x, dtype=np.float32) for x in xs])
    Xz = (X - mean) / (std + 1e-8)
    with torch.no_grad():
        v = model(torch.tensor(Xz, device=device)).cpu().numpy()
    return v


def make_agent(art):
    model, theta, mean, std = art["model"], art["theta"], art["mean"], art["std"]
    device = _device()
    model = model.to(device)

    def agent_fn(state):
        z = (state["x"] - mean) / (std + 1e-8)
        with torch.no_grad():
            v = float(model(torch.tensor(z, device=device).unsqueeze(0)).item())
        return (1 if v >= theta else 0), v

    return agent_fn
