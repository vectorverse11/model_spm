import numpy as np
import pytest

import catalog
from physics_engine import (
    E, G, LOAD_ARM, Beam, ComponentInputs, Connector, Material, TestSetup,
    Upright, VirtualSPM,
)

# Test-only component inputs (illustrative values).
COMP = dict(I_b=2.8e5, I_h=158.0, l_h=8.0, A_h=118.4, L_h=8.0,
            F_bearing=20000.0, delta_bearing=0.05, L_u=15.0, I_u=9.15,
            b_u=40.0, t_u=1.4, b_l=41.0, t_l=4.0, L_l=20.0)


def make(d_max=50.0, inc=0.01, **over):
    up = catalog.UPRIGHTS["Upright 90 x 1.4mm"]
    bm = catalog.BEAMS["RFB 80 - 1.2mm"]
    con = catalog.CONNECTORS["3 Lip Connector"]
    return VirtualSPM(
        Material("E 250", "A", 250.0, 410.0),
        Upright(**up), Beam(bm["H"], bm["W"], bm["T"], bm["type"]),
        Connector(con["n_lips"], con["H"], con["D"], con["W"], con["T"]),
        ComponentInputs(**{**COMP, **over}), TestSetup(inc, d_max))


def test_constants():
    assert (E, round(G)) == (210000.0, 80769)


def test_is2062_e250():
    assert catalog.yield_strength("E 250", "A", 4.0) == 250
    assert catalog.yield_strength("E 250", "A", 25.0) == 240
    assert catalog.IS2062_MECHANICAL["E 250"]["C"]["Rm"] == 410
    assert catalog.chemical_row("E 250", "B0")["CE"] == 0.41


def test_component_stiffness_formulae():
    s = make()
    c = COMP
    K = {x.code: x.K for x in [s.C1, *s.lip_components]}
    assert np.isclose(K["C1"], 3 * E * c["I_b"] / LOAD_ARM**3)
    assert np.isclose(K["C2"], 3 * E * c["I_h"] / c["l_h"] ** 3)
    assert np.isclose(K["C3"], G * c["A_h"] / c["L_h"])
    assert np.isclose(K["C4"], c["F_bearing"] / c["delta_bearing"])
    assert np.isclose(K["C5"], 3 * E * c["I_u"] / c["L_u"] ** 3)
    assert np.isclose(K["C6"], E * c["b_l"] * c["t_l"] ** 3 / (4 * c["L_l"] ** 3))


def test_assembly_and_four_outputs():
    s = make()
    z = 190.0 - np.array([25.1, 75.1, 125.1])
    assert np.allclose(s.z, z)
    assert np.isclose(s.S_j_ini, s.k_lip * np.sum(z**2))
    assert np.isclose(s.S_j, s.S_j_ini / 2)
    assert np.isclose(s.M_j_el, 2 / 3 * s.M_j_Rd)


def test_load_starts_at_zero_and_steps_by_increment():
    for inc in (0.01, 0.02):
        rec = make(inc=inc).run()["record"]
        assert rec["P"][0] == 0.0 and rec["D1"][0] == 0.0
        assert np.allclose(np.diff(rec["P"][:10]), inc * 1000)


@pytest.mark.parametrize("d_max", [0.5, 50.0])
def test_stops_at_max_deflection(d_max):
    res = make(d_max=d_max).run()
    D1 = np.array(res["record"]["D1"])
    assert np.isclose(D1[-1], d_max, atol=1e-6) and np.all(D1[:-1] < d_max)


def test_elastic_slope_matches_S_j_ini():
    res = make().run()
    rec = res["record"]
    i = next(k for k, M in enumerate(rec["M"]) if M > 0)
    assert np.isclose(rec["M"][i] / rec["theta"][i], res["S_j_ini"])


def test_sensor_order():
    rec = make().run()["record"]
    D1, D2, D3 = map(np.array, (rec["D1"], rec["D2"], rec["D3"]))
    assert np.all(D1 >= D3) and np.all(D3 >= D2)


def test_lips_must_fit_connector():
    with pytest.raises(ValueError):
        VirtualSPM(Material("E 250", "A", 250, 410), Upright(65.2, 90, 51.8, 1.4),
                   Beam(80, 50, 1.2), Connector(5, 190.0, 63, 41, 4),
                   ComponentInputs(**COMP), TestSetup(0.01, 10))
