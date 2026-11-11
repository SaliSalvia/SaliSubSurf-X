"""Unit tests for the CPF-lite statistics module (deep/cpf.py)."""

from __future__ import annotations

import numpy as np
import pytest

from subsurface_api.deep.cpf import (
    CH,
    cpf_analyze,
    confidence_from_p,
    empirical_null_scale,
    robust_context_detrend,
    whiten,
)


def _evidence_from_z(z_by_channel, shape=None):
    """Build a full evidence dict: unspecified channels stay at zero."""
    if shape is None:
        first = next(iter(z_by_channel.values()))
        shape = np.asarray(first).shape
    ev = {c: np.zeros(shape, np.float32) for c in CH}
    for c, z in z_by_channel.items():
        ev[c] = np.asarray(z, dtype=np.float32)
    return ev


def test_detrend_removes_smooth_surface():
    g = 96
    yy, xx = np.mgrid[0:g, 0:g].astype(np.float32)
    f = 0.3 * (xx / g) ** 2 + 0.2 * (yy / g) + np.random.default_rng(1).normal(0, 0.01, (g, g))
    resid = robust_context_detrend(f, deg=3)
    # the polynomial part is gone; only noise-scale residuals remain
    assert abs(float(resid.mean())) < 0.02
    assert abs(float(resid.std()) - 0.01) < 0.01


def test_whiten_decorrelates_channels():
    rng = np.random.default_rng(2)
    a = rng.normal(0, 1, (64, 64))
    b = 0.7 * a + np.sqrt(1 - 0.49) * rng.normal(0, 1, (64, 64))   # corr ~ 0.7
    c = rng.normal(0, 1, (64, 64))
    R = np.stack([a, b, c], -1)
    med, mad, Wm = whiten(R)
    Z = (R.reshape(-1, 3) - med) / mad @ Wm
    C = np.corrcoef(Z.T)
    # correlation largely removed (shrinkage keeps a little on purpose:
    # near-degenerate directions are NOT amplified into pure noise)
    assert abs(C[0, 1]) < 0.35
    assert abs(C[0, 2]) < 0.2 and abs(C[1, 2]) < 0.2


def test_empirical_null_scale_matches_chi2_median():
    rng = np.random.default_rng(3)
    d2 = rng.chisquare(6, size=100000)
    s = empirical_null_scale(d2, 6)
    assert 0.9 < s < 1.15


def test_cpf_finds_planted_blob():
    g = 96
    rng = np.random.default_rng(11)
    yy, xx = np.mgrid[0:g, 0:g].astype(np.float32)
    blob = np.exp(-(((yy - 48) / 8.0) ** 2 + ((xx - 48) / 8.0) ** 2))
    # realistic evidence: every channel carries noise; the blob rides on top
    noise = lambda: rng.normal(0, 0.5, (g, g)).astype(np.float32)
    ev = {c: noise() for c in CH}
    ev["z_ndmi"] = ev["z_ndmi"] - 4.0 * blob
    ev["z_ndvi"] = ev["z_ndvi"] - 4.0 * blob
    ev["z_bsi"] = ev["z_bsi"] + 4.0 * blob
    ev["z_nbr"] = ev["z_nbr"] - 4.0 * blob
    res = cpf_analyze(ev, n_surr=39, alpha=0.025, min_px=9, seed=7)
    assert res["significant"].any()
    # the significant pixels must sit inside the planted blob core
    core = blob > 0.25
    inside = (res["significant"] & core).sum()
    total = res["significant"].sum()
    assert inside >= 0.7 * total, f"only {inside}/{total} significant px inside the blob"
    assert any(p <= 0.025 for p in res["cluster_p"].values())


def test_cpf_quiet_on_pure_noise():
    rng = np.random.default_rng(5)
    g = 96
    ev = {c: rng.normal(0, 1.0, (g, g)).astype(np.float32) for c in CH}
    res = cpf_analyze(ev, n_surr=39, alpha=0.025, min_px=9, seed=7)
    assert float(res["significant"].mean()) < 0.02


def test_cpf_all_nan_evidence_returns_empty():
    g = 64
    ev = {c: np.full((g, g), np.nan, np.float32) for c in CH}
    res = cpf_analyze(ev, n_surr=9)
    assert not res["significant"].any()
    assert res["cluster_p"] == {}
    assert res["valid_fraction"] == 0.0


def test_cpf_missing_channel_raises():
    ev = {c: np.zeros((32, 32), np.float32) for c in CH}
    ev.pop("z_bsi")
    with pytest.raises(ValueError, match="z_bsi"):
        cpf_analyze(ev, n_surr=9)


def test_sig_score_range():
    rng = np.random.default_rng(6)
    g = 64
    ev = {c: rng.normal(0, 1, (g, g)).astype(np.float32) for c in CH}
    res = cpf_analyze(ev, n_surr=19, alpha=0.05)
    s = res["sig_score"]
    assert s.shape == (g, g)
    assert float(s.min()) >= 0.0 and float(s.max()) <= 100.0


def test_confidence_from_p_classes():
    assert confidence_from_p(0.0005) == "high"
    assert confidence_from_p(0.005) == "medium"
    assert confidence_from_p(0.05) == "low"
