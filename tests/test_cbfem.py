"""CBFEM initial / secant stiffness, checked against hand calculations.

Known values are from the 3-lip example in CBFEM_formulae.pdf. I_h, A_h and F
are not given there, so test-only placeholders are used for them.
"""
import math

import pytest

from cbfem import E, G, CBFEMInputs, H_b, calculate

PDF_3LIP = dict(H=155.0, H_t=55.0, beam_depth=80.0, t_p=3.0,
                I_b=410438.0, L_b=400.0, L_h=155.0,
                I_u=378760.0, L_u=800.0, b_l=12.1, t_l=3.0, L_l=21.6)
PLACEHOLDER = dict(I_h=1.0e5, A_h=300.0, F=10000.0)


def inp(**over):
    return CBFEMInputs(**{**PDF_3LIP, **PLACEHOLDER, **over})


def test_fixed_values():
    assert (E, round(G)) == (210000.0, 80769)


def test_geometry_from_pdf():
    i = inp()
    assert H_b(i) == 20.0
    r = calculate(i)
    assert r["theta_available_rad"] == pytest.approx(0.149, abs=5e-4)
    assert r["theta_available_deg"] == pytest.approx(8.5307, abs=1e-3)
    assert r["delta_bearing"] == 3.0


def test_component_values_by_hand():
    K = {c["C"]: c["K"] for c in calculate(inp())["components"]}
    assert K["C1"] == pytest.approx(3 * 210000 * 410438 / 400**3)        # 4040.2
    assert K["C1"] == pytest.approx(4040.2, abs=0.1)
    assert K["C2"] == pytest.approx(3 * 210000 * 1.0e5 / 155**3)
    assert K["C3"] == pytest.approx(G * 300 / 155)
    assert K["C4"] == pytest.approx(10000 / 3)                           # F / t_p
    assert K["C5"] == pytest.approx(466.1, abs=0.1)                      # 3EIu/Lu^3
    assert K["C6"] == pytest.approx(1702.0, abs=0.5)


def test_initial_and_secant_stiffness():
    r = calculate(inp())
    K = [c["K"] for c in r["components"]]
    # E*h^2/sum(1/k), k = K/E  ==  h^2/sum(1/K)   (all six components incl. K1)
    expected = 155**2 / sum(1 / k for k in K)
    assert r["S_j_ini"] == pytest.approx(expected)
    assert r["S_j_ini"] == pytest.approx(E * 155**2 / sum(E / k for k in K))
    assert r["S_j"] == pytest.approx(r["S_j_ini"] / 2)
    assert len(r["components"]) == 6


def test_check_condition_uses_L_b():
    r = calculate(inp())
    assert r["check_limit"] == pytest.approx(0.5 * 210000 * 410438 / 400)   # 107.7 kNm/rad
    assert r["check_ok"] == (r["S_j_ini"] > r["check_limit"])


def test_negative_H_b_rejected():
    with pytest.raises(ValueError):
        calculate(inp(H=120.0))
