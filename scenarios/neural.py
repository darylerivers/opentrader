"""NeuralMarketGenerator — conditional DoppelGANger-style GAN over market returns.

Follows the architecture notes in docs/research/chinese-lab-rl-foundations.md
(DoppelGANger 1909.13403):
  - GRU generator with BATCH generation (S records per hidden step) to preserve
    long-range autocorrelation over long horizons;
  - per-series auto-normalization, with the per-series scale emitted as metadata
    the generator must also produce (kills mode collapse on wide-dynamic-range
    OHLCV);
  - a second, metadata-only Wasserstein discriminator; combined loss
    L_seq + alpha * L_meta (WGAN-GP on the sequence head).

Input space: per-bar log-returns of the 17-symbol universe (SPY + 16 tradeables),
normalized to unit variance per column. The generator is CONDITIONAL on a regime
+ event one-hot, so the multiverse can be asked for a specific reality (e.g.
"bear" or "us_debt_ceiling"), and the tail library still injects grounded crises
on top.

torch is imported lazily so the rest of the scenarios package works without it.
"""
from __future__ import annotations

import numpy as np
import pandas as pd
import torch
import torch.nn as nn

from scenarios.spec import DEFAULT_UNIVERSE, ScenarioSpec, World

D = len(DEFAULT_UNIVERSE)          # 17 (SPY + 16 tradeables)
N_REGIME = 4
N_EVENT = 8
COND_DIM = N_REGIME + N_EVENT

_BASE_LEN = 256
_BATCH_S = 5


def _condition_vector(regime: str, event: str = "") -> np.ndarray:
    c = np.zeros(COND_DIM, dtype=np.float32)
    reg_idx = {"bull": 0, "bear": 1, "range": 2, "crisis": 3}.get(regime, 2)
    c[reg_idx] = 1.0
    if event:
        ev_idx = {"us_debt_ceiling": 0, "covid_crash": 1, "bear_grind_2022": 2,
                  "yen_unwind": 3, "flash_crash": 4, "liquidity_gap": 5,
                  "currency_crisis": 6, "fed_hike_surprise": 7}.get(event)
        if ev_idx is not None:
            c[N_REGIME + ev_idx] = 1.0
    return c


class _Generator(nn.Module):
    def __init__(self, latent=32, hidden=64, out=D):
        super().__init__()
        self.mlp_meta = nn.Sequential(nn.Linear(latent + COND_DIM, hidden), nn.ReLU(),
                                      nn.Linear(hidden, hidden), nn.ReLU(),
                                      nn.Linear(hidden, D))
        self.gru = nn.GRU(latent + COND_DIM, hidden, batch_first=True)
        self.head = nn.Sequential(nn.Linear(hidden, hidden), nn.ReLU(), nn.Linear(hidden, out))

    def forward(self, z, c, steps, batch_s=_BATCH_S):
        """Return (records (steps*batch_s, D), fake_meta (D,)).

        Batch generation per DoppelGANger: each GRU hidden step emits batch_s
        correlated records (shared hidden state, independent per-row noise) so
        long-range autocorrelation survives over long horizons.
        """
        zc = torch.cat([z, c], dim=-1)
        meta = self.mlp_meta(zc)
        hh = None
        x_in = zc.unsqueeze(1)
        out_rows = []
        for _ in range(steps):
            _, hh = self.gru(x_in, hh)          # hh: (1,1,H)
            h = hh[0, 0]                        # (H,)
            h_exp = h.unsqueeze(0).repeat(batch_s, 1)
            noise = torch.randn(batch_s, h_exp.size(-1), device=h.device) * 0.5
            out_rows.append(self.head(h_exp + noise))
        rows = torch.cat(out_rows, dim=0)
        return rows, meta


class _SeqCritic(nn.Module):
    def __init__(self, hidden=64):
        super().__init__()
        self.gru = nn.GRU(D, hidden, batch_first=True, bidirectional=True)
        self.head = nn.Sequential(nn.Linear(hidden * 2, hidden), nn.ReLU(), nn.Linear(hidden, 1))

    def forward(self, x):
        # x: (B, T, D) or (T, D)
        if x.dim() == 2:
            x = x.unsqueeze(0)
        _, h = self.gru(x)
        h = torch.cat([h[0], h[1]], dim=-1) if h.dim() == 3 else h
        return self.head(h).squeeze(-1)


class _MetaCritic(nn.Module):
    def __init__(self, hidden=32):
        super().__init__()
        self.net = nn.Sequential(nn.Linear(D, hidden), nn.ReLU(), nn.Linear(hidden, 1))

    def forward(self, m):
        return self.net(m).squeeze(-1)


class NeuralMarketGenerator:
    """Conditional WGAN-GP over market log-returns with emitted metadata."""

    def __init__(self, latent=32, hidden=64, device: str = "auto"):
        self.device = _pick_device(device)
        self.gen = _Generator(latent, hidden, D).to(self.device)
        self.seq_c = _SeqCritic(hidden).to(self.device)
        self.meta_c = _MetaCritic().to(self.device)
        self.alpha = 0.5
        self.norm_std = np.ones(D, dtype=np.float32)
        self._trained = False

    # -- training -------------------------------------------------------------
    def train(self, logret: np.ndarray, regimes: np.ndarray, epochs=50,
              lr=1e-3, grad_penalty=10.0, window=_BASE_LEN, seed=0):
        """logret: (T, D) normalized-log-return matrix; regimes: (T,) label str
        per bar. Slices windows, conditions each on its regime one-hot, and runs
        the DoppelGANger-style WGAN-GP update."""
        self.norm_std = (np.std(logret, axis=0) + 1e-8).astype(np.float32)
        x = (logret / self.norm_std).astype(np.float32)
        conds = np.stack([_condition_vector(r) for r in regimes])
        windows = _make_windows(x, window)
        cond_w = _make_windows(conds, window)
        opt_g = torch.optim.Adam(self.gen.parameters(), lr=lr, betas=(0.5, 0.999))
        opt_d = torch.optim.Adam(list(self.seq_c.parameters()) + list(self.meta_c.parameters()),
                                 lr=lr, betas=(0.5, 0.999))
        steps = (window + _BATCH_S - 1) // _BATCH_S
        rng = np.random.RandomState(seed)
        for ep in range(epochs):
            g_loss_t, d_loss_t = 0.0, 0.0
            idx = rng.permutation(len(windows))
            for i in idx:
                xw = torch.tensor(windows[i].astype(np.float32),
                                  device=self.device).unsqueeze(0)  # (1,T,D)
                cw = torch.tensor(cond_w[i][0], device=self.device)             # (Dc,)
                for _ in range(2):  # critic updates per gen step
                    z = torch.randn(1, 32, device=self.device)
                    fake, fake_meta = self.gen(z, cw.unsqueeze(0), steps)
                    # truncate the batch-generated fake to the real window length
                    fake = fake[:xw.size(1)]
                    fake_seq = fake.unsqueeze(0)
                    d_real = self.seq_c(xw)
                    d_fake = self.seq_c(fake_seq.detach())
                    gp = _grad_penalty(self.seq_c, xw, fake_seq.detach(), self.device)
                    m_real = self.meta_c(torch.tensor(self.norm_std, device=self.device).unsqueeze(0))
                    m_fake = self.meta_c(fake_meta.detach())
                    d_loss = (d_fake.mean() - d_real.mean() + grad_penalty * gp
                              + self.alpha * (m_fake.mean() - m_real.mean()))
                    opt_d.zero_grad()
                    d_loss.backward()
                    opt_d.step()
                z = torch.randn(1, 32, device=self.device)
                fake, fake_meta = self.gen(z, cw.unsqueeze(0), steps)
                g_loss = (-self.seq_c(fake).mean() - self.alpha * self.meta_c(fake_meta).mean())
                opt_g.zero_grad()
                g_loss.backward()
                opt_g.step()
                g_loss_t += g_loss.item()
                d_loss_t += d_loss.item()
            print(f"[neural] epoch {ep}: g={g_loss_t / len(windows):.3f} d={d_loss_t / len(windows):.3f}")
        self._trained = True
        return self

    # -- generation -----------------------------------------------------------
    def generate_world(self, spec: ScenarioSpec, n_bars=None) -> dict:
        n = n_bars or spec.n_bars
        steps = (n + _BATCH_S - 1) // _BATCH_S
        self.gen.eval()
        with torch.no_grad():
            z = torch.randn(1, 32, device=self.device)
            c = torch.tensor(_condition_vector(spec.regime, spec.event or ""),
                             device=self.device).unsqueeze(0)
            rows, _ = self.gen(z, c, steps)
            ret = rows.cpu().numpy().astype(np.float64)
        ret = ret[:n] * self.norm_std
        close = 100.0 * np.exp(np.cumsum(ret, axis=0))
        index = pd.bdate_range(end=pd.Timestamp.today().normalize(), periods=n)
        data = {}
        for j, s in enumerate(DEFAULT_UNIVERSE):
            df = pd.DataFrame(
                {"open": close[:, j], "high": close[:, j] * 1.005,
                 "low": close[:, j] * 0.995, "close": close[:, j],
                 "volume": np.full(n, 1e6)},
                index=index,
            )
            data[s] = df
        return data

    def save(self, path):
        torch.save({"gen": self.gen.state_dict(), "norm_std": self.norm_std}, path)

    def load(self, path):
        ck = torch.load(path, map_location=self.device, weights_only=False)
        self.gen.load_state_dict(ck["gen"])
        self.norm_std = ck["norm_std"]
        self._trained = True


def _pick_device(device: str):
    if device != "auto":
        return device
    return "cuda" if torch.cuda.is_available() else "cpu"


def _make_windows(x: np.ndarray, window: int, stride=None) -> np.ndarray:
    stride = stride or window // 2
    n = len(x)
    return np.stack([x[i:i + window] for i in range(0, max(1, n - window + 1), stride)])


def _grad_penalty(critic, real, fake, device):
    b = real.size(0)
    eps = torch.rand(b, 1, 1, device=device)
    interp = (eps * real + (1 - eps) * fake).requires_grad_(True)
    d = critic(interp)
    grads = torch.autograd.grad(d, interp, grad_outputs=torch.ones_like(d),
                                create_graph=True)[0]
    gp = ((grads.norm(2, dim=-1) - 1) ** 2).mean()
    return gp
