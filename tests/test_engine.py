import numpy as np
import pytest

from physics_engine import (
    BeamSection, ComponentParameters, Evaluation, HookConnector,
    HookConnectorSPM, LoadSchedule, Material, NonlinearOptions, TestRig,
    UprightSection,
)

# Test-only inputs: the engine has no defaults for these.
MAT = Material(fy=350.0, fu=450.0)
UPRIGHT = UprightSection(face_width=90.0, depth=70.0, lip=20.0, thickness=2.0)


def make(n_lips=5, d_max=20.0, **nl):
    return HookConnectorSPM(
        MAT, BeamSection("box", 80.0, 50.0, 1.6), UPRIGHT,
        HookConnector(n_lips=n_lips), ComponentParameters(),
        TestRig(max_deflection_mm=d_max), LoadSchedule(),
        NonlinearOptions(**nl), Evaluation())


def test_default_steel_elastic_constants():
    m = Material(fy=1.0, fu=1.0)
    assert (m.E, m.nu, round(m.G)) == (210000.0, 0.3, 80769)


def test_connector_geometry():
    for n, h in ((5, 245.0), (4, 195.0), (3, 145.0)):
        con = HookConnector(n_lips=n)
        assert np.isclose(con.height, h)
        assert np.allclose(con.lip_centres_from_top()[:2], [25.1, 75.1])
    assert np.isclose(HookConnector().lip_height, 29.6)


def test_lever_arms_to_connector_bottom():
    sim = make()
    assert np.isclose(sim.compression_centre_from_top, 245.0)
    assert np.allclose([r.z for r in sim.rows], [219.9, 169.9, 119.9, 69.9, 19.9])
    assert all(r.in_tension for r in sim.rows)


def test_equal_area_recovers_linear_slope():
    th = np.linspace(0, 0.01, 200)
    assert np.isclose(HookConnectorSPM.equal_area_stiffness(th, 1e8 * th, 5e5), 1e8)


def test_more_lips_stiffer_and_stronger():
    r3, r5 = make(3).run(), make(5).run()
    assert r5["S_j_ini_Nmm_rad"] > r3["S_j_ini_Nmm_rad"]
    assert r5["M_j_Rd_Nmm"] > r3["M_j_Rd_Nmm"]


def test_small_load_rotation_matches_component_stiffness():
    sim = make(looseness_rad=0.0)
    M = 0.05 * sim.M_j_Rd
    assert np.isclose(sim.theta_connection(M), M / sim.S_j_ini, rtol=1e-3)


@pytest.mark.parametrize("d_max", [0.5, 200.0])
def test_stops_exactly_at_max_deflection(d_max):
    res = make(d_max=d_max).run()
    D1 = np.array(res["record"]["D1"])
    assert np.isclose(D1[-1], d_max, atol=1e-6)
    assert np.all(D1[:-1] < d_max)
    # small limit is reached while loading, large one after the peak
    assert res["peak_reached"] == (d_max == 200.0)


def test_starts_at_zero_load_in_increments():
    rec = make().run()["record"]
    assert rec["P"][0] == 0.0
    assert rec["D1"][0] == rec["D2"][0] == rec["D3"][0] == 0.0
    assert np.allclose(np.diff(rec["P"][:10]), 10.0)   # 0.01 kN steps


def test_component_table_has_c1_to_c6():
    tab = make().run()["component_table"]
    assert [c["Component"][:2] for c in tab] == ["C1", "C2", "C3", "C4", "C5", "C6"]


def test_sensors_monotonic_and_ordered():
    rec = make().run()["record"]
    D1, D2, D3 = map(np.array, (rec["D1"], rec["D2"], rec["D3"]))
    assert np.all(np.diff(D1) >= -1e-12)
    # Dial 1 piston @ 400 > Dial 3 @ 140 > Dial 2 @ 40 mm
    assert np.all(D1 >= D3) and np.all(D3 >= D2)
