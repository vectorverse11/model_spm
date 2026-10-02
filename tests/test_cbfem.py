"""CBFEM virtual test, checked against hand calculations.

Known values are from the 3-lip example in CBFEM_formulae.pdf. I_h and A_h are
not given there, so test-only placeholders are used for them.
"""
import math

import pytest

from cbfem import E, G, LOAD_ARM, CBFEMInputs, H_b, delta_max, run, theta_available

PDF_3LIP = dict(H=155.0, H_t=55.0, beam_depth=80.0, t_p=3.0,
                I_b=410438.0, L_b=400.0, L_h=155.0,
                I_u=378760.0, L_u=800.0, b_l=12.1, t_l=3.0, L_l=21.6)
PLACEHOLDER = dict(I_h=1.0e5, A_h=300.0)


def inp(**over):
    return CBFEMInputs(**{**PDF_3LIP, **PLACEHOLDER, **over})


def test_fixed_values():
    assert (E, round(G)) == (210000.0, 80769)


def test_max_deflection_from_geometry():
    i = inp()
    assert H_b(i) == 20.0
    assert theta_available(i) == pytest.approx(0.149, abs=5e-4)
    assert math.degrees(theta_available(i)) == pytest.approx(8.5307, abs=1e-3)



def test_max_deflection_formula():
    # delta_max = P a^2 (3l - a) / (6 E I), a = 400, l = 500, I = I_b
    assert delta_max(1000.0, 410438.0) == pytest.approx(
        1000 * 400**2 * (3 * 500 - 400) / (6 * 210000 * 410438))
    r = run(inp(), 0.01)
    assert r["delta_max"] == pytest.approx(delta_max(r["F"], 410438.0))


def test_fixed_component_values_by_hand():
    K = {c["C"]: c["K"] for c in run(inp(), 0.01)["components"]}
    assert K["C1"] == pytest.approx(4040.2, abs=0.1)
    assert K["C2"] == pytest.approx(3 * 210000 * 1.0e5 / 155**3)
    assert K["C3"] == pytest.approx(G * 300 / 155)
    assert K["C5"] == pytest.approx(466.1, abs=0.1)
    assert K["C6"] == pytest.approx(1702.0, abs=0.5)


def test_F_and_K4_are_consistent():
    r = run(inp(), 0.01)
    F, K4 = r["F"], r["K4"]
    assert F > 0
    assert K4 == pytest.approx(F / 3.0)                      # K4 = F / t_p
    # The test with this K4 stops exactly at theta_available:
    # theta at M_max = M_max / S_j = 2 F a / S_j,ini
    assert 2 * F * LOAD_ARM / r["S_j_ini"] == pytest.approx(r["theta_available_rad"])
    # the iteration converges to the closed form
    assert r["iterations"][-1]["Test stops at F (N)"] == pytest.approx(F, rel=1e-5)


def test_stiffness_formulae():
    r = run(inp(), 0.01)
    K = [c["K"] for c in r["components"]]
    assert len(K) == 6
    assert r["S_j_ini"] == pytest.approx(155**2 / sum(1 / k for k in K))
    assert r["S_j_ini"] == pytest.approx(E * 155**2 / sum(E / k for k in K))
    assert r["S_j"] == pytest.approx(r["S_j_ini"] / 2)
    assert r["check_limit"] == pytest.approx(0.5 * 210000 * 410438 / 400)


@pytest.mark.parametrize("inc", [0.01, 0.02])
def test_virtual_test_runs_from_zero_to_max_deflection(inc):
    r = run(inp(), inc)
    rec = r["record"]
    assert rec["P"][0] == 0.0 and rec["D1"][0] == 0.0
    assert rec["P"][1] == pytest.approx(inc * 1000)
    assert rec["P"][-1] == pytest.approx(r["F"])
    assert rec["theta"][-1] == pytest.approx(r["theta_available_rad"])
    assert rec["D1"][-1] == pytest.approx(400 * math.tan(r["theta_available_rad"]))
    assert all(b >= a for a, b in zip(rec["D1"], rec["D1"][1:]))
    # elastic slope is S_j,ini
    assert rec["M"][1] / rec["theta"][1] == pytest.approx(r["S_j_ini"])


def test_bad_geometry_rejected():
    with pytest.raises(ValueError):
        run(inp(H=120.0), 0.01)          # H_b <= 0
    with pytest.raises(ValueError):
        run(inp(H_t=20.0), 0.01)          # H_b = 55: theta_av*h^2/(2a) = 1.64 <= t_p
