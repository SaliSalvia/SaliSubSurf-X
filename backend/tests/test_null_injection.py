"""Null / drift / injection tests: legacy Sal-Subsurf fusion vs CPF-lite.

Adapted from the external review prototype (``null_injection_tests.py``):
synthetic 9-scene stacks with configurable planted-anomaly amplitude, noise
and smooth seasonal drift are pushed through the REAL pipeline modules
(raster → temporal → model/fusion).  We then compare:

* ``legacy`` — the v1.2.x hand-weighted score + threshold detector;
* ``cpf``    — context-detrended, surrogate-calibrated cluster detection.

The assertions encode the calibration contract: under smooth seasonal drift
with NO anomaly the legacy detector flags a large share of the region
(drift looks like change), while CPF keeps false-positive area small; with a
planted anomaly CPF retains high recall.
"""

from __future__ import annotations

import numpy as np

from subsurface_api.deep import raster, temporal as T, cdse_process as C
from subsurface_api.deep.cpf import cpf_analyze
from subsurface_api.deep.fusion import fuse
from subsurface_api.deep.model import deep_anomaly

G = 96          # grid size (small → fast CI)
N_SCENES = 9
N_SURR = 99     # add-1 p floor = 1/100 = 0.01 ≤ alpha=0.01 (production defaults)
ALPHA = 0.01


def synth(g, n, amp, noise, season, seed):
    """Synthetic 8-band stacks: texture + noise + optional smooth drift + ellipse."""
    rng = np.random.default_rng(seed)
    yy, xx = np.mgrid[0:g, 0:g].astype(np.float32)
    tex = 0.5 + 0.5 * np.sin(xx / 17.0) * np.sin(yy / 23.0)
    cy, cx, ay, ax = g * .38, g * .62, g * .11, g * .15
    ell = np.exp(-(((yy - cy) / ay) ** 2 + ((xx - cx) / ax) ** 2)).astype(np.float32)
    ramp = np.clip((np.arange(n) - (n - 5)) / 4., 0, 1).astype(np.float32)
    out = []
    for t in range(n):
        a = ell * ramp[t] * amp
        ph = season * (t / (n - 1)) * (0.5 + 0.5 * np.sin(xx / 40. + yy / 55.))
        nz = lambda: rng.normal(0, noise, (g, g)).astype(np.float32)
        b = [(0.05 + 0.01 * tex + nz()) * (1 + 0.15 * a),
             (0.09 + 0.015 * tex + nz()) * (1 + 0.15 * a),
             (0.06 + 0.02 * tex + nz()) * (1 + 0.60 * a + 0.8 * ph),
             (0.34 + 0.05 * tex + nz()) * (1 - 0.28 * a - 0.35 * ph),
             (0.20 + 0.02 * tex + nz()) * (1 + 0.38 * a + 0.3 * ph),
             (0.13 + 0.015 * tex + nz()) * (1 + 0.22 * a + 0.2 * ph)]
        dn = [np.clip(x, 0, 1.4) * 1e4 + C.DN_OFFSET for x in b]
        out.append(np.stack(
            dn + [np.full((g, g), 4, np.uint16), np.ones((g, g), np.uint16)], -1
        ).astype(np.uint16))
    return out, (ell > 0.37)   # ground-truth mask = e^-1 contour of the ellipse


def evidence_from(stacks):
    class S:
        pass
    sc = []
    for t, st in enumerate(stacks):
        s = S()
        s.date = f"2026-10-{t + 1:02d}"
        refl = raster.to_reflectance(st)
        v = raster.valid_mask(st)
        s.indices = raster.compute_indices(refl, v)
        sc.append(s)
    dates, stk = raster.stack_scenes(sc)
    return T.temporal_evidence(dates, stk, 4, 1.5)


def legacy_mask(ev):
    dm, _ = deep_anomaly(ev, "pca")
    f = fuse(ev, dm)
    return f["score_0_100"] >= 55.0


def cpf_mask(ev):
    res = cpf_analyze(ev, n_surr=N_SURR, alpha=ALPHA, min_px=9)
    return res["significant"]


def metrics(mask, ell):
    """(recall on the planted core, false-positive area outside the support)."""
    core, support = ell > 0.37, ell > 0.02
    recall = (mask & core).sum() / max(1, core.sum())
    fp_area = (mask & ~support).sum() / max(1, (~support).sum())
    return float(recall), float(fp_area)


# ---------------------------------------------------------------------- cases

CASES = {
    "B_null": dict(amp=0.0, noise=0.0008, season=0.0),
    "D_null_drift": dict(amp=0.0, noise=0.0008, season=0.15),
    "E_planted_drift": dict(amp=1.0, noise=0.0008, season=0.15),
    "F_weak_planted_drift": dict(amp=0.35, noise=0.0008, season=0.15),
}


def _run(case):
    cfg = CASES[case]
    stacks, ell = synth(G, N_SCENES, cfg["amp"], cfg["noise"], cfg["season"], seed=3)
    ev = evidence_from(stacks)
    return ev, ell


def test_null_no_anomaly_both_quiet():
    ev, ell = _run("B_null")
    rl, fl = metrics(legacy_mask(ev), ell)
    rc, fc = metrics(cpf_mask(ev), ell)
    # pure noise, no drift: neither detector should light up the whole map
    assert fl < 0.10, f"legacy FP on pure null too high: {fl:.2%}"
    assert fc < 0.02, f"CPF FP on pure null too high: {fc:.2%}"


def test_drift_legacy_overflags_cpf_stays_calibrated():
    ev, ell = _run("D_null_drift")
    rl, fl = metrics(legacy_mask(ev), ell)
    rc, fc = metrics(cpf_mask(ev), ell)
    # THE headline result: seasonal drift fools the legacy score detector …
    assert fl >= 0.15, f"legacy FP under drift unexpectedly low: {fl:.2%}"
    # … while the surrogate-calibrated CPF keeps false positives small.
    assert fc <= 0.08, f"CPF FP under drift too high: {fc:.2%}"
    assert fc < fl, "CPF must not flag more drift area than legacy"


def test_planted_with_drift_cpf_finds_it():
    ev, ell = _run("E_planted_drift")
    rc, fc = metrics(cpf_mask(ev), ell)
    # measured on this suite: recall 1.00, FP 7.5 % (legacy flags 72 % of the
    # same scene).  The drift here is deliberately extreme (±0.12 reflectance
    # on red); a ~10x false-positive reduction with full recall is the contract.
    assert rc >= 0.90, f"CPF recall on planted+drift too low: {rc:.2f}"
    assert fc <= 0.10, f"CPF FP on planted+drift too high: {fc:.2%}"


def test_weak_planted_still_recovered():
    ev, ell = _run("F_weak_planted_drift")
    rc, fc = metrics(cpf_mask(ev), ell)
    # a 35 % -amplitude anomaly is still largely recovered (measured: 0.96)
    assert rc >= 0.80, f"CPF recall on weak planted too low: {rc:.2f}"
    assert fc <= 0.06


def test_cpf_pvalues_in_range():
    ev, _ = _run("E_planted_drift")
    res = cpf_analyze(ev, n_surr=N_SURR, alpha=ALPHA, min_px=9)
    for p in res["cluster_p"].values():
        assert 0.0 < p <= 1.0
    assert res["sig_score"].shape == (G, G)
    assert float(res["sig_score"].min()) >= 0.0
    assert float(res["sig_score"].max()) <= 100.0
