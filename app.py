"""
Streamlit GUI — Virtual SPM for Hook-Connector Beam-End Stiffness Testing
========================================================================
Cantilever beam-end-connector test (EN 15512 Annex A style) evaluated with the
EN 1993-1-8 component method adapted to hook ("lip") rows.
"""

import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
import streamlit as st

from physics_engine import (
    BeamSection, ComponentParameters, Evaluation, HookConnector,
    HookConnectorSPM, LoadSchedule, Material, NonlinearOptions, TestRig,
    UprightSection,
)

st.set_page_config(page_title="Virtual SPM — Hook Connector Tester",
                   page_icon="🏗️", layout="wide")
st.title("🏗️ Virtual SPM — Beam-End Hook Connector Stiffness Test")
st.caption("Cantilever test · Dial 1 piston @ 400 mm · Dial 2 @ 40 mm · "
           "Dial 3 @ 140 mm · component method C1–C6 · stops at max deflection")

LIP_HEIGHTS = {3: 145.0, 4: 195.0, 5: 245.0}
missing = []


def required(label, lo, hi, step, container=st, fmt=None):
    kw = {"format": fmt} if fmt else {}
    v = container.number_input(f"{label} *", lo, hi, value=None, step=step,
                               placeholder="required", **kw)
    if v is None:
        missing.append(label)
    return v


# ============================================================
# SIDEBAR
# ============================================================
with st.sidebar:
    st.header("⚙️ Input Parameters")
    st.caption("Fields marked * are required.")

    st.subheader("1. Material (steel)")
    mat_name = st.text_input("Material", "Steel")
    c1, c2 = st.columns(2)
    E = c1.number_input("E (N/mm²)", 50000.0, 300000.0, 210000.0, 1000.0)
    nu = c2.number_input("ν", 0.1, 0.5, 0.3, 0.01)
    fy = required("fy (N/mm²)", 100.0, 1000.0, 5.0, c1)
    fu = required("fu (N/mm²)", 100.0, 1200.0, 5.0, c2)
    st.caption(f"G = E / 2(1+ν) = **{E / (2 * (1 + nu)):.0f} N/mm²**")

    st.subheader("2. Beam (length 500 mm)")
    beam_type = st.selectbox("Section", ["box", "solid_rect", "custom"])
    beam_h = required("Depth h_b (mm)", 10.0, 300.0, 1.0)
    beam_b = beam_t = I_cust = W_cust = None
    if beam_type in ("box", "solid_rect"):
        beam_b = required("Width b (mm)", 5.0, 200.0, 1.0)
    if beam_type == "box":
        beam_t = required("Wall thickness (mm)", 0.5, 10.0, 0.1)
    if beam_type == "custom":
        I_cust = required("I (mm⁴)", 1e3, 1e8, 1e4, fmt="%.3e")
        W_cust = required("W_pl (mm³)", 1e2, 1e7, 1e3, fmt="%.3e")
    beam_Lb = st.number_input("Rack beam span L_b for classification (mm)",
                              500.0, 6000.0, value=None, step=50.0,
                              placeholder="optional")

    st.subheader("3. Upright (length 800 mm)")
    up_B = required("Slotted face width (mm)", 20.0, 200.0, 1.0)
    up_D = required("Side-wall depth (mm)", 10.0, 200.0, 1.0)
    up_c = required("Return lip (mm)", 0.0, 60.0, 1.0)
    up_t = required("Thickness t_u (mm)", 0.5, 8.0, 0.1)
    up_I = st.number_input("I_u override (mm⁴)", 1e3, 1e8, value=None,
                           step=1e4, format="%.3e", placeholder="computed")
    up_perf = st.slider("Perforation factor I_net/I_gross", 0.5, 1.0, 1.0, 0.01)
    up_H = st.number_input("Upright length (mm)", 200.0, 3000.0, 800.0, 10.0)
    up_fix = st.selectbox("Rig clamping", ["fixed-fixed", "pinned-pinned", "rigid"])

    st.subheader("4. Hook Connector")
    n_lips = st.selectbox("Number of lips", [5, 4, 3], index=0)
    st.caption(f"Height = **{LIP_HEIGHTS[n_lips]:.0f} mm** · width 44 mm · "
               "pitch 50 mm · top 10.3 / bottom 34.7 mm · 1st lip centre 25.1 mm")
    t_p = st.number_input("Connector plate thickness t_p (mm)", 1.0, 10.0, 4.0, 0.5)
    ext_above = st.number_input("Connector above beam top (mm)", 0.0, 200.0, 55.0, 1.0)
    ext_below = st.number_input("Connector below beam bottom (mm)", 0.0, 200.0, 55.0, 1.0)
    cc = st.selectbox("Centre of compression",
                      ["beam_bottom", "connector_bottom"],
                      format_func=lambda s: {
                          "beam_bottom": "Beam bottom flange (EN 1993-1-8)",
                          "connector_bottom": "Connector bottom edge"}[s])

    st.subheader("5. Component Parameters (per lip)")
    st.caption("Effective lengths/widths — estimates, calibrate against a real test.")
    with st.expander("C2/C3 — Hook bending & shear"):
        l_h = st.number_input("Hook bending length l_h (mm)", 1.0, 50.0, 8.0, 0.5)
        L_h = st.number_input("Hook shear length L_h (mm)", 1.0, 50.0, 8.0, 0.5)
        b_h = st.number_input("Hook width b_h (mm) — 0 = lip height 29.6",
                              0.0, 60.0, 0.0, 0.5)
    with st.expander("C4 — Hook-upright bearing"):
        b_brg = st.number_input("Bearing width (mm)", 1.0, 60.0, 12.0, 0.5)
        L_brg = st.number_input("Bearing length (mm)", 1.0, 60.0, 10.0, 0.5)
    with st.expander("C5 — Upright wall local deformation"):
        b_u = st.number_input("Effective width b_u (mm)", 5.0, 150.0, 40.0, 1.0)
        L_u = st.number_input("Effective length L_u (mm)", 2.0, 100.0, 15.0, 0.5)
    with st.expander("C6 — Connector lip bending"):
        b_l = st.number_input("Effective width b_l (mm) — 0 = pitch 50",
                              0.0, 100.0, 0.0, 1.0)
        L_l = st.number_input("Effective length L_l (mm)", 2.0, 100.0, 20.0, 0.5)
    g_M0 = st.number_input("γ_M0 on component resistances", 1.0, 1.5, 1.0, 0.05)

    st.subheader("6. Test Rig & Sensors")
    a = st.number_input("Piston position a (mm) — Dial 1", 100.0, 500.0, 400.0, 10.0)
    x2 = st.number_input("Dial 2 from upright face (mm)", 0.0, 500.0, 40.0, 5.0)
    x3 = st.number_input("Dial 3 from upright face (mm)", 10.0, 500.0, 140.0, 5.0)
    k_train = st.number_input("Piston load-train stiffness (N/mm)",
                              1e3, 1e8, 2e5, 1e4, format="%.0e")
    noise = st.number_input("Dial noise σ (mm)", 0.0, 0.1, 0.0, 0.001, format="%.3f")

    st.subheader("7. Loading & Stop Condition")
    inc = st.selectbox("Load increment (kN/step)", [0.01, 0.02])
    P0 = st.number_input("Initial load, dials zeroed here (kN)", 0.0, 5.0, 0.0, 0.001,
                         format="%.3f")
    d_max = required("Max deflection — test stops (mm)", 0.1, 500.0, 1.0)
    stop_key = st.selectbox("Deflection checked on", ["D1", "D2", "D3"],
                            format_func=lambda k: {"D1": "Dial 1 (piston)",
                                                   "D2": "Dial 2", "D3": "Dial 3"}[k])
    dt = st.number_input("Time per recorded step (s)", 0.001, 10.0, 0.02, 0.001,
                         format="%.3f")
    dial_res = st.number_input("Dial resolution (mm)", 0.001, 0.1, 0.01, 0.001,
                               format="%.3f")

    st.subheader("8. Non-linear Behaviour")
    loose = st.number_input("Looseness θ₀ (rad)", 0.0, 0.05, 0.004, 0.001, format="%.3f")
    loose_M = st.number_input("Looseness closure moment (N·mm)", 1e3, 1e6, 5e4, 1e3,
                              format="%.0e")
    psi = st.slider("ψ (EN 1993-1-8 shape factor)", 1.0, 4.0, 2.7, 0.1)
    hard = st.slider("Post-yield hardening ratio", 0.001, 0.2, 0.02, 0.001)

    st.subheader("9. Evaluation")
    gamma_M = st.number_input("γ_M (connections)", 1.0, 1.5, 1.1, 0.05)
    eta = st.number_input("η (design moment factor)", 0.5, 1.0, 1.0, 0.05)
    braced = st.checkbox("Braced frame (k_b = 8, else 25)", False)
    eta_S = st.number_input("Stiffness modification η for S_j = S_j,ini/η",
                            1.0, 3.5, 2.0, 0.1)

# ============================================================
# VALIDATION
# ============================================================
if missing:
    st.warning("Enter the required inputs in the sidebar to run the test:\n\n"
               + "\n".join(f"- {m}" for m in missing))
    st.stop()
errors = []
if fu < fy:
    errors.append("fu must be greater than or equal to fy.")
if x3 <= x2:
    errors.append("Dial 3 must be further from the upright than Dial 2.")
if beam_type == "box" and 2 * beam_t >= min(beam_h, beam_b):
    errors.append("Box wall thickness is too large for the section.")
h_c = LIP_HEIGHTS[n_lips]
if ext_above + beam_h > h_c:
    errors.append(f"Connector above beam + beam depth = {ext_above + beam_h:.0f} mm "
                  f"does not fit on the {h_c:.0f} mm connector.")
if errors:
    for e in errors:
        st.error(e)
    st.stop()
fit = ext_above + beam_h + ext_below
if abs(fit - h_c) > 0.5:
    st.warning(f"Connector above + beam depth + connector below = {fit:.1f} mm, "
               f"but the {n_lips}-lip connector is {h_c:.0f} mm high. "
               f"The beam is positioned using the 'above' distance "
               f"({ext_above:.0f} mm); actual distance below = "
               f"{h_c - ext_above - beam_h:.1f} mm.")

# ============================================================
# RUN
# ============================================================
try:
    sim = HookConnectorSPM(
        Material(fy=fy, fu=fu, E=E, nu=nu, name=mat_name),
        BeamSection(beam_type, beam_h, beam_b, beam_t, I_cust, W_cust,
                    span_for_classification=beam_Lb),
        UprightSection(up_B, up_D, up_c, up_t, up_perf, up_I, up_H, up_fix),
        HookConnector(n_lips=n_lips, plate_thickness=t_p,
                      extension_above=ext_above, extension_below=ext_below),
        ComponentParameters(
            hook_width_bh=b_h or None, hook_bending_length_lh=l_h,
            hook_shear_length_Lh=L_h, bearing_width=b_brg, bearing_length=L_brg,
            upright_eff_width_bu=b_u, upright_eff_length_Lu=L_u,
            lip_eff_width_bl=b_l or None, lip_eff_length_Ll=L_l, gamma_M0=g_M0),
        TestRig(d_max, stop_key, a, x2, x3, cc, k_train, noise),
        LoadSchedule(inc, P0, dt, dial_res),
        NonlinearOptions(loose, loose_M, psi, hard),
        Evaluation(gamma_M, eta, braced, eta_S),
    )
except ValueError as exc:
    st.error(str(exc))
    st.stop()
res = sim.run()
rec = res["record"]

# ============================================================
# METRICS
# ============================================================
m = st.columns(5)
m[0].metric("S_j,ini (component)", f"{res['S_j_ini_Nmm_rad'] / 1e6:.1f} kN·m/rad")
k_ti = res["k_ti_Nmm_rad"]
m[1].metric("k_ti (equal-area, test)",
            f"{k_ti / 1e6:.1f} kN·m/rad" if np.isfinite(k_ti) else "—")
m[2].metric("Peak load", f"{res['P_max_N'] / 1000:.3f} kN")
m[3].metric("M_Rd = η·M_max/γ_M", f"{res['M_Rd_Nmm'] / 1e6:.3f} kN·m")
m[4].metric("Classification", res["classification"])

(st.error if res["peak_reached"] else st.success)(
    f"⏹ Test stopped: {res['stop_reason']}")
st.caption(f"Increment **{inc} kN/step** · records **{res['total_steps']}** · "
           f"connector **{res['connector_height_mm']:.0f} mm** · centre of "
           f"compression **{res['compression_centre_mm']:.1f} mm** from top · "
           f"first lip to reach F_u: {res['first_row_ultimate']}")

st.divider()

# ============================================================
# CURVES
# ============================================================
P_kN = np.array(rec["P"]) / 1000.0
fig, ax = plt.subplots(1, 3, figsize=(17, 5))

ax[0].plot(rec["D1"], P_kN, "g-", lw=2, label=f"Dial 1 piston (x={a:.0f})")
ax[0].plot(rec["D2"], P_kN, "b-", lw=2, label=f"Dial 2 (x={x2:.0f})")
ax[0].plot(rec["D3"], P_kN, "r--", lw=1.5, label=f"Dial 3 (x={x3:.0f})")
ax[0].axvline(d_max, color="grey", ls=":", label="Max deflection")
ax[0].set(xlabel="Displacement (mm)", ylabel="Load (kN)",
          title="Load vs Displacement")
ax[0].grid(alpha=0.3)
ax[0].legend(loc="lower right", fontsize=8)

th = np.array(rec["theta_corr"])
Mk = np.array(rec["M"]) / 1e6
ax[1].plot(th, Mk, "r-", lw=2.2, label="Test (D3−D2)/Δx")
th_line = np.linspace(0, min(th.max(), 1.2 * Mk.max() * 1e6 / res["S_j_ini_Nmm_rad"]), 50)
ax[1].plot(th_line, res["S_j_ini_Nmm_rad"] * th_line / 1e6, "k:", lw=1.2,
           label="S_j,ini (component)")
if np.isfinite(k_ti):
    ax[1].plot([0, res["M_Rd_Nmm"] / k_ti], [0, res["M_Rd_Nmm"] / 1e6], "b--",
               lw=1.5, label="k_ti equal-area")
ax[1].axhline(res["M_Rd_Nmm"] / 1e6, color="orange", ls=":", label="M_Rd")
ax[1].set_ylim(0, Mk.max() * 1.1 if Mk.max() > 0 else 1)
ax[1].set(xlabel="Rotation θ (rad)", ylabel="Moment M (kN·m)",
          title="Moment vs Rotation")
ax[1].grid(alpha=0.3)
ax[1].legend(loc="lower right", fontsize=8)

ax[2].plot(rec["step"], P_kN, "m-", lw=2)
ax[2].set(xlabel="Step number", ylabel="Load (kN)",
          title=f"Load vs Step ({inc} kN/step)")
ax[2].grid(alpha=0.3)

plt.tight_layout()
st.pyplot(fig)

st.divider()

# ============================================================
# COMPONENT TABLES
# ============================================================
st.subheader("🧩 Component Analysis (per lip row, C2–C6 in series)")
rows_df = pd.DataFrame(res["rows_table"])
st.dataframe(rows_df.round(1), width="stretch", hide_index=True)

st.subheader("📋 Summary")
lims = res["class_limits_Nmm_rad"]
summary = pd.DataFrame({
    "Quantity": [
        "C1 Beam K1 = 3EI_b/a³", "C1 Beam F1,Rd = M_pl/a", "Beam I", "Upright I",
        "Centre of compression (from connector top)",
        "z_eq", "k_eq", "S_j,ini = Σ k_eff z²", "M_j,Rd = Σ F_Rd z",
        "k_ti (equal area)", "Secant 10–40 % M_max", "M_max (test)", "M_Rd",
        "Rotation capacity φ = t_p/h_e", "Max rotation in test",
        "Pinned limit 0.5 EI_b/L_b", "Rigid limit k_b EI_b/L_b",
        "Classification (stiffness)", "Idealised S_j = S_j,ini/η",
        "Beam M_pl", "Classification (strength)", "Stop reason",
    ],
    "Value": [
        f"{res['K1_N_mm']:.1f} N/mm", f"{res['F1_Rd_N']:.0f} N",
        f"{res['I_beam_mm4']:.3e} mm⁴", f"{res['I_upright_mm4']:.3e} mm⁴",
        f"{res['compression_centre_mm']:.1f} mm",
        f"{res['z_eq_mm']:.1f} mm", f"{res['k_eq_N_mm']:.0f} N/mm",
        f"{res['S_j_ini_Nmm_rad'] / 1e6:.2f} kN·m/rad",
        f"{res['M_j_Rd_Nmm'] / 1e6:.3f} kN·m",
        f"{k_ti / 1e6:.2f} kN·m/rad" if np.isfinite(k_ti) else "—",
        f"{res['k_secant_Nmm_rad'] / 1e6:.2f} kN·m/rad",
        f"{res['M_max_Nmm'] / 1e6:.3f} kN·m", f"{res['M_Rd_Nmm'] / 1e6:.3f} kN·m",
        f"{res['theta_avail_rad']:.4f} rad",
        f"{res['theta_max_rad']:.4f} rad"
        + (" (exceeds φ)" if res["rotation_capacity_exceeded"] else ""),
        f"{lims[0] / 1e6:.2f} kN·m/rad" if lims else "—",
        f"{lims[1] / 1e6:.2f} kN·m/rad" if lims else "—",
        res["classification"],
        f"{res['S_j_ideal_Nmm_rad'] / 1e6:.2f} kN·m/rad",
        f"{res['M_pl_beam_Nmm'] / 1e6:.3f} kN·m",
        res["strength_classification"], res["stop_reason"],
    ],
})
st.dataframe(summary, width="stretch", hide_index=True)

# ============================================================
# SENSOR DATA + CSV
# ============================================================
st.divider()
st.subheader("📡 Sensor Data")


def quantise(v, q):
    return np.round(np.round(np.asarray(v) / q) * q, 6)


machine_df = pd.DataFrame({
    "Load 1 kN": np.round(P_kN, 3),
    "Dial 1 mm": quantise(rec["D1"], dial_res),
    "Dial 2 mm": quantise(rec["D2"], dial_res),
    "Dial 3 mm": quantise(rec["D3"], dial_res),
    "Time Sec.": np.round(rec["time_s"], 3),
})
detail_df = pd.DataFrame({
    "Step": rec["step"], "Time (s)": rec["time_s"], "Load (N)": rec["P"],
    "Dial1_piston_mm": rec["D1"], "Dial2_mm": rec["D2"], "Dial3_mm": rec["D3"],
    "Moment (N·mm)": rec["M"],
    "Rotation_measured (rad)": rec["theta_meas"],
    "Rotation_corrected (rad)": rec["theta_corr"],
})
for idx, f in res["row_forces"].items():
    detail_df[f"Lip{idx}_force (N)"] = f

tab1, tab2 = st.tabs(["Machine format", "Detailed"])
with tab1:
    st.dataframe(machine_df, width="stretch", height=350, hide_index=True)
with tab2:
    st.dataframe(detail_df, width="stretch", height=350, hide_index=True)

st.download_button("📥 Download sensor readings — machine format (CSV)",
                   machine_df.to_csv(index=False).encode("utf-8"),
                   "spm_sensor_readings.csv", "text/csv")
st.download_button("📥 Download detailed readings (CSV)",
                   detail_df.to_csv(index=False).encode("utf-8"),
                   "spm_detailed_readings.csv", "text/csv")
st.download_button("📥 Download summary (CSV)",
                   pd.concat([summary, rows_df.astype(str)], axis=0)
                   .to_csv(index=False).encode("utf-8"),
                   "spm_summary.csv", "text/csv")
