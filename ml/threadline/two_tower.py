"""Two-tower retrieval model.

Training uses PyTorch (``train_two_tower``). Serving uses ``TwoTowerNumpy``: the item vectors
are pre-computed and the small user-tower MLP is exported to NumPy, so the inference service
needs neither PyTorch nor a GPU. ``tests/test_two_tower.py`` checks both forward passes agree.

Architecture
    item tower : [id emb | product type | department | colour | index group | content emb] -> MLP -> L2 norm
    user tower : [masked mean of history item vectors | age-band emb | online ratio | log #history] -> MLP -> L2 norm
    loss       : in-batch sampled softmax with logQ popularity correction and accidental-hit masking
"""

from __future__ import annotations

import logging
from dataclasses import dataclass
from pathlib import Path

import numpy as np
import pandas as pd

log = logging.getLogger(__name__)

N_AGE_BANDS = 5
TT_ATTRS = ["product_type_name", "department_name", "colour_group_name", "index_group_name"]


def _l2(x: np.ndarray) -> np.ndarray:
    return x / (np.linalg.norm(x, axis=-1, keepdims=True) + 1e-8)


@dataclass
class TwoTowerNumpy:
    """NumPy-only serving half of the two-tower model."""

    item_vecs: np.ndarray  # (n_items, d), L2-normalised, row i = articles row i
    age_emb: np.ndarray  # (N_AGE_BANDS, a)
    w1: np.ndarray
    b1: np.ndarray
    w2: np.ndarray
    b2: np.ndarray

    def encode_users(self, hist_rows: list[list[int]], age_bands: np.ndarray, online: np.ndarray) -> np.ndarray:
        """``hist_rows``: per user, catalogue row indices of recent purchases (any order)."""
        d = self.item_vecs.shape[1]
        pooled = np.zeros((len(hist_rows), d), dtype=np.float32)
        n = np.zeros(len(hist_rows), dtype=np.float32)
        for i, rows in enumerate(hist_rows):
            if rows:
                pooled[i] = self.item_vecs[rows].mean(axis=0)
                n[i] = len(rows)
        x = np.concatenate(
            [pooled, self.age_emb[np.asarray(age_bands, dtype=int)],
             np.asarray(online, dtype=np.float32)[:, None], np.log1p(n)[:, None]], axis=1)
        h = np.maximum(x @ self.w1.T + self.b1, 0)
        return _l2(h @ self.w2.T + self.b2).astype(np.float32)

    def save(self, path: Path) -> None:
        np.savez_compressed(path, item_vecs=self.item_vecs, age_emb=self.age_emb,
                            w1=self.w1, b1=self.b1, w2=self.w2, b2=self.b2)

    @classmethod
    def load(cls, path: Path) -> TwoTowerNumpy:
        z = np.load(path)
        return cls(**{k: z[k] for k in ("item_vecs", "age_emb", "w1", "b1", "w2", "b2")})


# --------------------------------------------------------------------------------------
# Training (PyTorch)
# --------------------------------------------------------------------------------------

def _encode_attrs(articles: pd.DataFrame) -> tuple[np.ndarray, list[int]]:
    codes, cards = [], []
    for c in TT_ATTRS:
        cat = pd.Categorical(articles[c].astype(str))
        codes.append(cat.codes.astype(np.int64) + 1)
        cards.append(len(cat.categories) + 1)
    return np.stack(codes, axis=1), cards


def build_training_samples(
    tx: pd.DataFrame, row_of: pd.Series, customers: pd.DataFrame, hist_len: int, max_samples: int, seed: int
) -> dict[str, np.ndarray]:
    """One sample per purchase: (history before that week, purchased item)."""
    from threadline.features import age_band

    tx = tx.sort_values(["customer_idx", "t_dat"])
    cust = tx["customer_idx"].to_numpy()
    week = tx["week"].to_numpy()
    item = row_of.reindex(tx["article_id"].to_numpy()).to_numpy().astype(np.int64) + 1  # 0 = padding
    online_ratio = (tx["sales_channel_id"] == 2).groupby(tx["customer_idx"]).mean()
    ages = customers.set_index("customer_idx")["age"]

    bounds = np.flatnonzero(np.diff(cust)) + 1
    starts = np.r_[0, bounds]
    ends = np.r_[bounds, len(cust)]
    hist, pos, users = [], [], []
    for s, e in zip(starts, ends):
        w, it = week[s:e], item[s:e]
        for wk in np.unique(w):
            before = it[w < wk][-hist_len:]
            padded = np.zeros(hist_len, dtype=np.int64)
            if len(before):
                padded[-len(before):] = before
            for p in np.unique(it[w == wk]):
                hist.append(padded)
                pos.append(p)
                users.append(cust[s])
    users = np.asarray(users)
    out = {
        "hist": np.stack(hist),
        "pos": np.asarray(pos, dtype=np.int64),
        "age_band": age_band(ages.reindex(users).fillna(ages.median()).to_numpy()).astype(np.int64),
        "online": online_ratio.reindex(users).fillna(0.5).to_numpy().astype(np.float32),
    }
    if len(pos) > max_samples:
        idx = np.random.default_rng(seed).choice(len(pos), size=max_samples, replace=False)
        out = {k: v[idx] for k, v in out.items()}
    return out


def train_two_tower(
    tx: pd.DataFrame,
    articles: pd.DataFrame,
    customers: pd.DataFrame,
    content_emb: np.ndarray,
    dim: int = 64,
    epochs: int = 4,
    batch_size: int = 1024,
    lr: float = 2e-3,
    hist_len: int = 20,
    temperature: float = 0.05,
    max_samples: int = 3_000_000,
    seed: int = 42,
    log_fn=None,
    return_torch: bool = False,
):
    import torch
    import torch.nn as nn
    import torch.nn.functional as F

    torch.manual_seed(seed)
    n_items = len(articles)
    row_of = pd.Series(np.arange(n_items), index=articles["article_id"].to_numpy())
    attr_codes, cards = _encode_attrs(articles)
    samples = build_training_samples(tx, row_of, customers, hist_len, max_samples, seed)
    n = len(samples["pos"])
    log.info("Two-tower: %d training samples, %d items", n, n_items)

    # Pad row 0 for the padding index.
    attr_t = torch.tensor(np.vstack([np.zeros((1, attr_codes.shape[1]), np.int64), attr_codes]))
    content_t = torch.tensor(np.vstack([np.zeros((1, content_emb.shape[1]), np.float32), content_emb]))
    freq = np.bincount(samples["pos"], minlength=n_items + 1).astype(np.float64) + 1.0
    log_q = torch.tensor(np.log(freq / freq.sum()), dtype=torch.float32)

    class ItemTower(nn.Module):
        def __init__(self) -> None:
            super().__init__()
            self.id_emb = nn.Embedding(n_items + 1, dim, padding_idx=0)
            self.attr_embs = nn.ModuleList([nn.Embedding(c, 16) for c in cards])
            self.content = nn.Linear(content_emb.shape[1], 32)
            self.mlp = nn.Sequential(nn.Linear(dim + 16 * len(cards) + 32, 2 * dim), nn.ReLU(), nn.Linear(2 * dim, dim))

        def forward(self, idx: torch.Tensor) -> torch.Tensor:
            a = attr_t[idx]
            parts = [self.id_emb(idx)] + [e(a[..., i]) for i, e in enumerate(self.attr_embs)]
            parts.append(self.content(content_t[idx]))
            return F.normalize(self.mlp(torch.cat(parts, dim=-1)), dim=-1)

    class UserTower(nn.Module):
        def __init__(self) -> None:
            super().__init__()
            self.age = nn.Embedding(N_AGE_BANDS, 8)
            self.fc1 = nn.Linear(dim + 8 + 2, 2 * dim)
            self.fc2 = nn.Linear(2 * dim, dim)

        def forward(self, hist_vecs, mask, age, online):
            cnt = mask.sum(1, keepdim=True)
            pooled = (hist_vecs * mask.unsqueeze(-1)).sum(1) / cnt.clamp(min=1)
            x = torch.cat([pooled, self.age(age), online.unsqueeze(1), torch.log1p(cnt)], dim=1)
            return F.normalize(self.fc2(F.relu(self.fc1(x))), dim=-1)

    item_tower, user_tower = ItemTower(), UserTower()
    params = list(item_tower.parameters()) + list(user_tower.parameters())
    opt = torch.optim.Adam(params, lr=lr)
    t = {k: torch.tensor(v) for k, v in samples.items()}

    for epoch in range(epochs):
        perm = torch.randperm(n)
        total, steps = 0.0, 0
        for s in range(0, n, batch_size):
            b = perm[s : s + batch_size]
            hist, pos = t["hist"][b], t["pos"][b]
            mask = (hist > 0).float()
            hv = item_tower(hist)
            u = user_tower(hv, mask, t["age_band"][b], t["online"][b])
            v = item_tower(pos)
            logits = u @ v.T / temperature - log_q[pos][None, :]
            same = pos[:, None] == pos[None, :]
            logits = logits.masked_fill(same & ~torch.eye(len(b), dtype=torch.bool), -1e9)
            loss = F.cross_entropy(logits, torch.arange(len(b)))
            opt.zero_grad()
            loss.backward()
            opt.step()
            total += loss.item()
            steps += 1
        log.info("two-tower epoch %d loss %.4f", epoch + 1, total / steps)
        if log_fn:
            log_fn("tt_train_loss", total / steps, epoch)

    with torch.no_grad():
        all_idx = torch.arange(1, n_items + 1)
        item_vecs = torch.cat([item_tower(all_idx[i : i + 8192]) for i in range(0, n_items, 8192)]).numpy()
    exported = TwoTowerNumpy(
        item_vecs=item_vecs.astype(np.float32),
        age_emb=user_tower.age.weight.detach().numpy().astype(np.float32),
        w1=user_tower.fc1.weight.detach().numpy(), b1=user_tower.fc1.bias.detach().numpy(),
        w2=user_tower.fc2.weight.detach().numpy(), b2=user_tower.fc2.bias.detach().numpy(),
    )
    return (exported, item_tower, user_tower) if return_torch else exported
