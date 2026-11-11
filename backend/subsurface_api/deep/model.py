"""Unsupervised per-pixel anomaly model (numpy-only, deterministic).

Two interchangeable backends:

* ``pca`` (default) — robust-standardised features, SVD/PCA, per-pixel
  reconstruction error. Linear, fast, fully inspectable.
* ``autoencoder`` — a tiny tanh MLP (D → 8 → 3 → 8 → D) trained in-place with
  plain numpy SGD on a subsample; reconstruction error again becomes the score.
  Same contract, slightly more expressive, still dependency-free.

The output is always a percentile-ranked anomaly map in [0, 1]: 1.0 means
"the most reconstruction-surprising pixel of this region". Invalid pixels are
excluded from the fit and scored 0.

This is a *surface spectral-behaviour* anomaly detector — not a target detector
(docs/SCIENCE-SCOPE.md).
"""

from __future__ import annotations

from typing import Dict, Tuple

import numpy as np

FEATURE_KEYS = (
    "ndvi", "ndwi", "mndwi", "ndmi", "nbr", "bsi", "albedo",
    "z_ndmi", "z_ndvi", "z_bsi",
    "persistence", "trend_ndmi", "trend_ndvi",
)


def build_feature_cube(evidence: Dict[str, np.ndarray]) -> Tuple[np.ndarray, np.ndarray]:
    """Stack features → ``(H*W, D)`` matrix + validity boolean vector."""
    keys = [k for k in FEATURE_KEYS if k in evidence]
    if not keys:
        raise ValueError("no evidence layers to build features from")
    cube = np.stack([evidence[k] for k in keys], axis=-1).astype(np.float32)
    h, w, d = cube.shape
    flat = cube.reshape(h * w, d)
    valid = np.isfinite(flat).all(axis=1) & ~np.all(flat == 0.0, axis=1)
    return flat, valid


def _robust_scale(x: np.ndarray) -> Tuple[np.ndarray, np.ndarray, np.ndarray]:
    med = np.median(x, axis=0)
    iqr = np.percentile(x, 75, axis=0) - np.percentile(x, 25, axis=0)
    scale = np.where(iqr > 1e-6, iqr, 1.0).astype(np.float32)
    return (x - med) / scale, med.astype(np.float32), scale.astype(np.float32)


def percentile_rank_1d(x: np.ndarray) -> np.ndarray:
    """Rank values to [0, 1] (0 = lowest, 1 = highest). Deterministic."""
    n = x.size
    if n == 0:
        return np.zeros(0, dtype=np.float32)
    order = np.argsort(x, kind="stable")
    ranks = np.empty(n, dtype=np.float64)
    ranks[order] = np.arange(n, dtype=np.float64)
    if n > 1:
        ranks /= (n - 1)
    return ranks.astype(np.float32)


def pca_anomaly(features: np.ndarray, valid: np.ndarray, var_keep: float = 0.90) -> np.ndarray:
    """Reconstruction-error anomaly percentile over valid pixels → full map."""
    h_w, _ = features.shape
    out = np.zeros(h_w, dtype=np.float32)
    if valid.sum() < max(32, features.shape[1] * 2):
        return out
    x = features[valid]
    zs, _, _ = _robust_scale(x)
    mean = zs.mean(axis=0)
    xc = (zs - mean).astype(np.float64)
    try:
        u, s, vt = np.linalg.svd(xc, full_matrices=False)
    except np.linalg.LinAlgError:
        return out
    energy = (s ** 2).sum()
    if energy <= 0:
        return out
    kept = int(np.searchsorted(np.cumsum(s ** 2) / energy, var_keep) + 1)
    kept = max(1, min(kept, s.size))
    proj = xc @ vt[:kept].T
    recon = proj @ vt[:kept]
    err = ((xc - recon) ** 2).sum(axis=1)
    out[valid] = percentile_rank_1d(err.astype(np.float32))
    return out


def _tanh(x: np.ndarray) -> np.ndarray:
    return np.tanh(x)


def autoencoder_anomaly(
    features: np.ndarray,
    valid: np.ndarray,
    hidden: int = 8,
    bottleneck: int = 3,
    epochs: int = 300,
    lr: float = 0.02,
    max_train: int = 40000,
    seed: int = 42,
) -> np.ndarray:
    """Tiny numpy autoencoder; reconstruction error → percentile map."""
    rng = np.random.default_rng(seed)
    h_w, d = features.shape
    out = np.zeros(h_w, dtype=np.float32)
    n_valid = int(valid.sum())
    if n_valid < max(64, d * 4):
        return out

    x = features[valid]
    zs, _, _ = _robust_scale(x)
    if n_valid > max_train:
        idx = rng.choice(n_valid, size=max_train, replace=False)
        train = zs[idx]
    else:
        train = zs
    train64 = train.astype(np.float64)

    w1 = rng.normal(0, 1 / np.sqrt(d), size=(d, hidden))
    b1 = np.zeros(hidden)
    w2 = rng.normal(0, 1 / np.sqrt(hidden), size=(hidden, bottleneck))
    b2 = np.zeros(bottleneck)
    w3 = rng.normal(0, 1 / np.sqrt(bottleneck), size=(bottleneck, hidden))
    b3 = np.zeros(hidden)
    w4 = rng.normal(0, 1 / np.sqrt(hidden), size=(hidden, d))
    b4 = np.zeros(d)

    n = train64.shape[0]
    batch = min(1024, n)
    prev = np.inf
    for _epoch in range(max(10, epochs)):
        perm = rng.permutation(n)
        last = 0.0
        for start in range(0, n, batch):
            b = train64[perm[start:start + batch]]
            h1 = _tanh(b @ w1 + b1)
            h2 = _tanh(h1 @ w2 + b2)
            h3 = _tanh(h2 @ w3 + b3)
            rec = h3 @ w4 + b4
            err = rec - b
            loss = float((err ** 2).mean())
            last = loss
            g = 2.0 * err / b.shape[0]
            gw4, gb4 = h3.T @ g, g.sum(axis=0)
            gh3 = g @ w4.T * (1.0 - h3 ** 2)
            gw3, gb3 = h2.T @ gh3, gh3.sum(axis=0)
            gh2 = gh3 @ w3.T * (1.0 - h2 ** 2)
            gw2, gb2 = h1.T @ gh2, gh2.sum(axis=0)
            gh1 = gh2 @ w2.T * (1.0 - h1 ** 2)
            gw1, gb1 = b.T @ gh1, gh1.sum(axis=0)
            for w, g_ in ((w1, gw1), (w2, gw2), (w3, gw3), (w4, gw4)):
                w -= lr * g_
            for b_, g_ in ((b1, gb1), (b2, gb2), (b3, gb3), (b4, gb4)):
                b_ -= lr * g_
        if abs(prev - last) < 1e-7:
            break
        prev = last

    full = zs.astype(np.float64)
    h1 = _tanh(full @ w1 + b1)
    h2 = _tanh(h1 @ w2 + b2)
    h3 = _tanh(h2 @ w3 + b3)
    rec = h3 @ w4 + b4
    err = ((rec - full) ** 2).sum(axis=1).astype(np.float32)
    out[valid] = percentile_rank_1d(err)
    return out


def deep_anomaly(
    evidence: Dict[str, np.ndarray],
    model: str = "pca",
    autoencoder_epochs: int = 300,
) -> Tuple[np.ndarray, str]:
    """Entry point used by the pipeline.

    Returns ``(score_map (H, W) in [0, 1], model_name_actually_used)``.
    """
    features, valid = build_feature_cube(evidence)
    shape = evidence["z_ndmi"].shape if "z_ndmi" in evidence else evidence["ndvi"].shape
    if model == "autoencoder":
        score_flat = autoencoder_anomaly(
            features, valid, epochs=autoencoder_epochs
        )
        used = "autoencoder"
    else:
        score_flat = pca_anomaly(features, valid)
        used = "pca"
    return score_flat.reshape(shape), used
