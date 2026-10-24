"""CBFEM virtual test, checked against hand calculations.

Known values are from the 3-lip example in CBFEM_formulae.pdf. I_h and A_h are
not given there, so test-only placeholders are used for them.
"""
import pytest

import catalog
from cbfem import (E, G, LOAD_ARM, CBFEMInputs, H_b, deflection, run)

PDF_3LIP = dict(H=155.0, H_t=55.0, beam_depth=80.0, t_p=3.0,
                I_b=410438.0, L_b=400.0, L_h=155.0,
                I_u=378760.0, L_u=800.0, b_l=12.1, t_l=3.0, L_l=21.6)
PLACEHOLDER = dict(I_h=1.0e5, A_h=300.0, P_max_kN=3.86, F_kN=3.86, theta_avail=0.03634)


def inp(**over):
    return CBFEMInputs(**{**PDF_3LIP, **PLACEHOLDER, **over})


def test_fixed_values():
    assert (E, round(G)) == (210000.0, 80769)


def test_max_load_is_required():
    with pytest.raises(TypeError):
        CBFEMInputs(**PDF_3LIP, I_h=1.0e5, A_h=300.0, F_kN=3.86, theta_avail=0.03634)  # no P


def test_catalog_sections():
    con = catalog.CONNECTORS["5 Lip Connector 245mm"]
    assert (con["n_lips"], con["H"], con["T"]) == (5, 245.0, 4.0)
    assert catalog.CONNECTORS["3 Lip Connector 155mm"]["H"] == 155.0
    assert catalog.BEAMS["Beam 80 x 50 x 1.5mm"]["T"] == 1.5


def test_max_deflection_from_max_load():
    # delta_max = P a^2 (3l - a) / (6 E I), P = 3.86 kN, a = 400, l = 500
    expected = 3860 * 400**2 * (3 * 500 - 400) / (6 * 210000 * 410438)
    assert deflection(3860.0, 410438.0) == pytest.approx(expected)
    assert run(inp(), 0.01)["delta_max"] == pytest.approx(expected)     # 1.3137 mm
    assert expected == pytest.approx(1.3137, abs=1e-4)


def test_moment_output():
    r = run(inp(), 0.01)
    assert r["M_max"] == pytest.approx(r["P_stop"] * LOAD_ARM)       # M = P_stop * a
    assert r["record"]["M"][-1] == pytest.approx(r["M_max"])


def test_works_for_5_lip_connector():
    r = run(inp(H=245.0, t_p=4.0, P_max_kN=5.0), 0.02)
    assert r["P_stop"] > 0 and r["K4_kN_rad"] == pytest.approx(3.86 / 0.03634)
    assert r["record"]["D1"][-1] == pytest.approx(r["delta_max"])


def test_test_stops_when_D1_reaches_delta_max():
    r = run(inp(), 0.01)
    rec = r["record"]
    assert rec["D1"][-1] == pytest.approx(r["delta_max"], rel=1e-9)
    assert all(d < r["delta_max"] for d in rec["D1"][:-1])
    assert rec["P"][-1] == pytest.approx(r["P_stop"])


def test_component_values_by_hand():
    r = run(inp(), 0.01)
    K = {c["C"]: c["K"] for c in r["components"]}
    assert K["C1"] == pytest.approx(4040.2, abs=0.1)
    assert K["C2"] == pytest.approx(3 * 210000 * 1.0e5 / 155**3)
    assert K["C3"] == pytest.approx(G * 300 / 155)
    assert K["C4"] == pytest.approx(3860 / 0.03634)                 # K4 = F / θ, N/rad
    assert r["K4_kN_rad"] == pytest.approx(106.219, abs=1e-3)       # kN/rad
    assert K["C5"] == pytest.approx(466.1, abs=0.1)
    assert K["C6"] == pytest.approx(1702.0, abs=0.5)


def test_stiffness_as_in_formula_sheet():
    r = run(inp(), 0.01)
    K = [c["K"] for c in r["components"]]
    assert len(K) == 6
    s = sum(1 / k for k in K)
    assert r["S_j_ini"] == pytest.approx(E * 155**2 / s)    # E h^2 / (1/K1 + ... + 1/K6)
    assert r["S_j"] == pytest.approx(r["S_j_ini"] / 2)
    assert r["check_limit"] == pytest.approx(0.5 * 210000 * 410438 / 400)


@pytest.mark.parametrize("inc", [0.01, 0.02])
def test_load_steps_from_zero(inc):
    rec = run(inp(), inc)["record"]
    assert rec["P"][0] == 0.0 and rec["D1"][0] == 0.0
    assert rec["P"][1] == pytest.approx(inc * 1000)
    assert all(b >= a for a, b in zip(rec["D1"], rec["D1"][1:]))


def test_bad_geometry_rejected():
    assert H_b(inp(H=120.0)) < 0
    with pytest.raises(ValueError):
        run(inp(H=120.0), 0.01)


def test_user_hand_calc_5_lip():
    # User's 5-lip values: K4 = 3.86 / 0.03634 kN/rad, S_j,ini = E h^2 / sum(1/K)
    r = run(inp(H=245.0, t_p=4.0, I_h=3869.0, L_h=245.0, A_h=78.4, t_l=4.0, L_l=19.6),
            0.01)
    assert r["S_j_ini"] == pytest.approx(1.4556e12, rel=1e-3)


def test_K4_inputs_must_be_positive():
    with pytest.raises(ValueError):
        run(inp(theta_avail=0.0), 0.01)
