"""Virtual stub column test — section properties against textbook formulas."""
import pytest

from stub import E, StubInputs, gross_properties, rho_of, run

BASE = dict(pitch=60, n_web=0, d_web=0, n_fl=0, d_fl=0, c=300, cap_L=130, cap_W=110, cap_t=30,
            base_L=130, base_W=110, base_t=10, fy=350, gamma_M0=1.0, alternative=1,
            least_count=0.01)


def inp(**over):
    return StubInputs(**{**dict(W=110, D=90, t=2, lip=20, n_web=2, d_web=10, n_fl=1, d_fl=8),
                         **{k: v for k, v in BASE.items() if k not in ("n_web", "d_web",
                                                                       "n_fl", "d_fl")},
                         **over})


def channel():
    # plain channel, centreline web h = 100, flange b = 50, t = 2
    return StubInputs(W=102, D=51, t=2, lip=0, **BASE)


def test_channel_properties_match_textbook():
    g = gross_properties(channel())
    h, b, t = 100, 50, 2
    assert g["A"] == pytest.approx(t * (h + 2 * b))
    assert g["Ix"] == pytest.approx(t * h**3 / 12 + 2 * b * t * (h / 2) ** 2)
    assert g["Iw"] == pytest.approx(t * b**3 * h**2 * (3 * b + 2 * h) / (12 * (6 * b + h)))
    assert g["xs"] + g["xc"] == pytest.approx(-3 * b**2 / (h + 6 * b))   # shear centre


def test_effective_width_formula():
    rho, lam = rho_of(108, 2, 4.0, True, 350, 350)
    assert lam == pytest.approx((108 / 2) / (28.4 * (235 / 350) ** 0.5 * 2))
    assert rho == pytest.approx((lam - 0.22) / lam**2)


def test_virtual_test_runs_to_failure():
    r = run(inp(), 1.0)
    rows = r["rows"]
    assert rows[0]["N"] == 0 and rows[-1]["N"] == pytest.approx(r["N_u"])
    assert all(b["dial"] >= a["dial"] for a, b in zip(rows, rows[1:]))
    assert r["A_net"] < r["gross"]["A"] and r["eff"]["A_eff"] <= r["A_net"]
    assert r["A_eff_test"] == pytest.approx(r["R_k"] / 350)                # lambda <= 0.2
    assert 0 < r["N_proof"] <= r["N_u"]
    assert rows[-1]["delta"] == pytest.approx(r["N_u"] * 300 / (E * rows[-1]["A_eff"]))


def test_alternative_2_is_concentric_and_not_lower():
    r1, r2 = run(inp(alternative=1), 1.0), run(inp(alternative=2), 1.0)
    assert r2["e"] == 0 and r2["N_u"] >= r1["N_u"]
    assert r1["cr"]["L_F"] == 380 and r2["cr"]["L_F"] == r2["cr"]["L_T"] == 300


def test_bad_holes_rejected():
    with pytest.raises(ValueError):
        run(inp(n_web=20, d_web=10), 1.0)


def test_plate_projection_checked_along_web_only():
    chk = {c["Criterion"]: c for c in run(inp(cap_L=130, cap_W=100, base_L=130, base_W=100),
                                          1.0)["checks"]}
    row = next(v for k, v in chk.items() if k.startswith("Plates project"))
    assert row["OK"]                                     # (130 − 110)/2 = 10 ≥ 10
    row = next(v for k, v in {c["Criterion"]: c for c in run(inp(cap_L=120), 1.0)["checks"]}
               .items() if k.startswith("Plates project"))
    assert not row["OK"]                                 # (120 − 110)/2 = 5 < 10


def test_area_adjusted_when_slenderness_exceeds_0_2():
    r = run(inp(alternative=2, c=1500), 1.0)
    assert r["cr"]["L_F"] == r["cr"]["L_T"] == 1500                # full length for Alt 2
    assert r["lambda_bar"] > 0.2 and r["chi"] < 1
    assert r["A_eff_test"] > r["R_k"] / 350                         # area adjusted
    assert r["A_eff_test"] == pytest.approx(r["eff"]["A_eff"], rel=1e-6)
    assert r["N_b_Rd"] == pytest.approx(r["R_k"] / 1.0)             # N_b,Rd = R_k / γ_M0


def test_custom_cg_moves_alt1_load_position():
    r0 = run(inp(alternative=1), 1.0)
    r1 = run(inp(alternative=1, cg_x=40.0), 1.0)
    assert r0["x_cg"] == pytest.approx(r0["x_gross"]) and not r0["cg_custom"]
    assert r1["x_cg"] == 40.0 and r1["cg_custom"] and r1["N_u"] != r0["N_u"]


def test_lipped_channel_cg_closed_form():
    from stub import gross_properties
    g = gross_properties(inp())
    bw, bf, bl = 108, 88, 19
    assert g["xc"] == pytest.approx(bf * (bf + 2 * bl) / (bw + 2 * bf + 2 * bl))


def test_eccentric_curve_secant_formula():
    from math import cos, pi, sqrt
    from stub import eccentric_test
    i = inp(alternative=2)
    r = run(i, 1.0)
    ec = eccentric_test(i, r, 5.0, 1.0)
    assert 0 < ec["N_ue"] < r["N_u"]
    last = ec["rows"][-1]
    assert last["w"] == pytest.approx(5.0 * (1 / cos(pi / 2 * sqrt(last["N"] / ec["N_cr"])) - 1))
    U = ec["N_ue"] / ec["N_c"] + last["M"] / (ec["W_eff"] * 350)
    assert U == pytest.approx(1.0, rel=1e-6)
    assert eccentric_test(i, r, 0.0, 1.0)["N_ue"] == pytest.approx(r["N_u"])


def test_grade_yield_by_thickness():
    import catalog
    assert catalog.grade_yield("E 350", 2.0) == 350
    assert catalog.grade_yield("E 350", 25.0) == 330
    assert list(catalog.STEEL_GRADES)[-1] == "E 650"


def test_pdf_report_with_and_without_graph():
    from stub import eccentric_test
    from stub_report import build_report
    i = inp(alternative=2)
    r = run(i, 1.0)
    ec = eccentric_test(i, r, 5.0, 1.0)
    a = build_report(i, r, "Client", "E 350", "Standard formula", 1.0, ec, with_graph=True)
    b = build_report(i, r, "Client", "E 350", "Standard formula", 1.0, None, with_graph=False)
    assert a[:4] == b[:4] == b"%PDF" and len(a) > len(b)


def test_column_buckling_half_length():
    from stub_report import build_report
    s = run(inp(alternative=2, c=1200), 5.0)
    c = run(inp(alternative=2, c=1200, half_length=True), 5.0)
    assert s["cr"]["L_F"] == 1200 and c["cr"]["L_F"] == c["cr"]["L_T"] == 600
    assert c["b"] == 1200 + 2 * 30 + 2 * 10                      # L = L1 + 2a + 2b
    assert c["N_u"] > s["N_u"]                                   # shorter buckling length
    a1 = run(inp(alternative=1, c=1200, half_length=True), 5.0)
    assert a1["cr"]["L_F"] == 1280 and a1["cr"]["L_T"] == 600    # Alt 1 unchanged
    pdf = build_report(inp(c=1200, half_length=True), c, "X", "E 350", "Standard formula", 5.0,
                       column=True)
    assert pdf[:4] == b"%PDF"
