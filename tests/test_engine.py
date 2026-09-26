import numpy as np

from physics_engine import (
    BeamSection, ComponentParameters, Evaluation, HookConnector,
    HookConnectorSPM, LoadSchedule, Material, NonlinearOptions, TestRig,
    UprightSection,
)


# Test-only strengths; the engine has no default fy / fu.
MAT = Material(fy=350.0, fu=450.0)


def make(n_lips=5, **nl):
    return HookConnectorSPM(
        MAT, BeamSection(), UprightSection(), HookConnector(n_lips=n_lips),
        ComponentParameters(), TestRig(), LoadSchedule(),
        NonlinearOptions(**nl), Evaluation())


def test_connector_geometry():
    for n, h in ((5, 245.0), (4, 195.0), (3, 145.0)):
        con = HookConnector(n_lips=n)
        assert np.isclose(con.height, h)
        assert np.allclose(con.lip_centres_from_top()[:2], [25.1, 75.1])
    assert np.isclose(HookConnector().lip_height, 29.6)


def test_equal_area_recovers_linear_slope():
    th = np.linspace(0, 0.01, 200)
    assert np.isclose(HookConnectorSPM.equal_area_stiffness(th, 1e8 * th, 5e5), 1e8)


def test_more_lips_stiffer_and_stronger():
    r3, r5 = make(3).run(), make(5).run()
    assert r5["S_j_ini_Nmm_rad"] > r3["S_j_ini_Nmm_rad"]
    assert r5["M_j_Rd_Nmm"] > r3["M_j_Rd_Nmm"]


def test_small_load_rotation_matches_component_stiffness():
    sim = make(looseness_rad=0.0)
    M = 0.05 * sim.M_j_Rd   # well inside the elastic range
    assert np.isclose(sim.theta_connection(M), M / sim.S_j_ini, rtol=1e-3)


def test_sensors_monotonic_and_ordered():
    rec = make().run()["record"]
    D1, D2, D3 = map(np.array, (rec["D1"], rec["D2"], rec["D3"]))
    assert np.all(np.diff(D1) >= 0)
    # D1 piston @ 400 > D3 @ 140 > D2 @ 40 mm from the upright face
    assert np.all(D1 >= D3) and np.all(D3 >= D2)


def test_default_steel_elastic_constants():
    m = Material(fy=1.0, fu=1.0)
    assert (m.E, m.nu, round(m.G)) == (210000.0, 0.3, 80769)
