"""Finite strip solver and Alternative 3 (CUFSM + DSM) against closed-form results."""
from math import pi

import numpy as np
import pytest

import fsm
from stub import StubInputs, gross_properties, nodes, run

E, NU = 210000.0, 0.3


def test_simply_supported_plate_matches_k4():
    b, t = 100.0, 2.0
    nd, st = fsm.mesh(np.array([[0.0, 0.0], [b, 0.0]]), 10)
    fixed = [2, 4 * (len(nd) - 1) + 2]                       # w = 0 on both long edges
    D = E * t**3 / (12 * (1 - NU**2))
    s, _ = fsm.sigma_cr(nd, st, t, b, E, NU, fixed)          # half-wavelength a = b
    assert s == pytest.approx(4 * pi**2 * D / (b**2 * t), rel=1e-4)


def test_long_channel_matches_euler_torsional():
    inp = StubInputs(W=102, D=51, t=2, lip=0, pitch=60, n_web=0, d_web=0, n_fl=0, d_fl=0,
                     c=300, cap_L=130, cap_W=100, cap_t=30, base_L=130, base_W=100, base_t=10,
                     fy=350, gamma_M0=1, alternative=2, least_count=0.01)
    g = gross_properties(inp)
    nd, st = fsm.mesh(nodes(inp), 5)
    a = 5000.0
    s, _ = fsm.sigma_cr(nd, st, 2.0, a, E, NU)
    Nx, Ny = pi**2 * E * g["Ix"] / a**2, pi**2 * E * g["Iy"] / a**2
    NT = (E / 2.6 * g["J"] + pi**2 * E * g["Iw"] / a**2) / g["i0_sq"]
    p = (np.poly1d([1, -Nx]) * np.poly1d([1, -Ny]) * np.poly1d([1, -NT]) * g["i0_sq"]
         - np.poly1d([1, 0, 0]) * g["x0"]**2 * np.poly1d([1, -Ny]))
    roots = [r.real for r in p.r if abs(r.imag) < 1e-6 and r.real > 0]
    assert s == pytest.approx(min(roots + [Nx, Ny]) / g["A"], rel=2e-3)


def lipped(**over):
    return StubInputs(**{**dict(W=110, D=90, t=2, lip=20, pitch=60, n_web=2, d_web=10, n_fl=1,
                                d_fl=8, c=300, cap_L=130, cap_W=100, cap_t=30, base_L=130,
                                base_W=100, base_t=10, fy=350, gamma_M0=1.0, alternative=3,
                                least_count=0.01), **over})


def test_alternative_3_dsm():
    r = run(lipped(), 2.0)
    d = r["dsm"]
    assert d["local"]["a"] < d["dist"]["a"]                   # local minimum before distortional
    assert d["P_ne"] <= d["P_ynet"] and d["P_nl"] <= d["P_ne"]
    lam = (d["P_ne"] / d["P_crl"]) ** 0.5
    rr = (d["P_crl"] / d["P_ne"]) ** 0.4
    assert lam > 0.776 and d["P_nl"] == pytest.approx((1 - 0.15 * rr) * rr * d["P_ne"])
    assert r["N_u"] == pytest.approx(d["P_nl"]) and r["rows"][-1]["N"] == pytest.approx(r["N_u"])
    assert r["N_u"] == pytest.approx(run(lipped(alternative=2), 2.0)["N_u"], rel=0.10)  # EWM ≈ DSM
    rd = run(lipped(distortional=True), 2.0)
    assert rd["N_u"] == pytest.approx(min(d["P_nl"], d["P_nd"]))
