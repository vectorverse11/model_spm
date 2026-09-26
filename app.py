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
st.caption("Cantilever test · D1 piston @ 400 mm · D2 LVDT @ 40 mm · D3 LVDT @ 140 mm · "
           "component method C1–C6")

LIP_HEIGHTS = {3: 145.0, 4: 195.0, 5: 245.0}

# ============================================================
# SIDEBAR
# ============================================================
with st.sidebar:
    st.header("⚙️ Input Parameters")

    st.subheader("1. Material")
    mat_name = st.text_input("Material", "E250 Steel (IS 2062)")
    c1, c2 = st.columns(2)
    E = c1.number_input("E (N/mm²)", 50000.0, 300000.0, 210000.0, 1000.0)
    nu = c2.number_input("ν", 0.1, 0.5, 0.3, 0.01)
    fy = c1.number_input("fy (N/mm²)", 100.0, 1000.0, 250.0, 5.0)
    fu = c2.number_input("fu (N/mm²)", 100.0, 1200.0, 410.0, 5.0)
    st.caption(f"G = E / 2(1+ν) = **{E / (2 * (1 + nu)):.0f} N/mm²**")

    st.subheader("2. Beam")
    beam_type = st.selectbox("Section", ["box", "solid_rect", "custom"])
    beam_h = st.number_input("Depth h_b (mm)", 20.0, 300.0, 80.0, 1.0)
    beam_b = st.number_input("Width b (mm)", 10.0, 200.0, 50.0, 1.0)
    beam_t = st.number_input("Wall thickness (mm)", 0.5, 10.0, 1.6, 0.1,
                             disabled=beam_type != "box")
    I_cust = st.number_input("Custom I (mm⁴)", 1e3, 1e8, 3.7e5, 1e4,
                             format="%.3e", disabled=beam_type != "custom")
    W_cust = st.number_input("Custom W_pl (mm³)", 1e2, 1e7, 1.1e4, 1e3,
                             format="%.3e", disabled=beam_type != "custom")
    beam_Lb = st.number_input("Rack beam span L_b for classification (mm)",
                              500.0, 6000.0, 2700.0, 50.0)

    st.subheader("3. Upright")
    up_B = st.number_input("Slotted face width (mm)", 30.0, 200.0, 90.0, 1.0)
    up_D = st.number_input("Side-wall depth (mm)", 20.0, 200.0, 70.0, 1.0)
    up_c = st.number_input("Return lip (mm)", 0.0, 60.0, 20.0, 1.0)
    up_t = st.number_input("Thickness t_u (mm)", 1.0, 6.0, 2.0, 0.1)
    up_perf = st.slider("Perforation factor I_net/I_gross", 0.5, 1.0, 0.85, 0.01)
    up_H = st.number_input("Clamp length (mm)", 200.0, 3000.0, 800.0, 10.0)
    up_fix = st.selectbox("Rig clamping", ["fixed-fixed", "pinned-pinned", "rigid"])

    st.subheader("4. Hook Connector")
    n_lips = st.selectbox("Number of lips", [5, 4, 3], index=0)
    st.caption(f"Height = **{LIP_HEIGHTS[n_lips]:.0f} mm** · width 44 mm · "
               "pitch 50 mm · top 10.3 / bottom 34.7 mm · 1st lip centre 25.1 mm")
    t_p = st.number_input("Connector plate thickness t_p (mm)", 1.0, 10.0, 4.0, 0.5)

    st.subheader("5. Component Parameters (per lip)")
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
    a = st.number_input("Load arm a (mm) — D1 piston sensor", 100.0, 1000.0, 400.0, 10.0)
    x2 = st.number_input("D2 LVDT from upright face (mm)", 0.0, 1000.0, 40.0, 5.0)
    x3 = st.number_input("D3 LVDT from upright face (mm)", 10.0, 1000.0, 140.0, 5.0)
    k_train = st.number_input("Actuator + load-cell stiffness (N/mm)",
                              1e3, 1e8, 2e5, 1e4, format="%.0e")
    noise = st.number_input("LVDT noise σ (mm)", 0.0, 0.1, 0.0, 0.001, format="%.3f")

    st.subheader("7. Load Schedule")
    inc = st.selectbox("Load increment (kN/step)", [0.01, 0.02])
    P_max = st.number_input("Max load (N)", 100.0, 100000.0, 5000.0, 100.0)
    stop_fail = st.checkbox("Stop test at failure", True)

    st.subheader("8. Non-linear Behaviour")
    loose = st.number_input("Looseness θ₀ (rad)", 0.0, 0.05, 0.004, 0.001, format="%.3f")
    loose_M = st.number_input("Looseness closure moment (N·mm)", 1e3, 1e6, 5e4, 1e3,
                              format="%.0e")
    psi = st.slider("ψ (EN 1993-1-8 shape factor)", 1.0, 4.0, 2.7, 0.1)
    hard = st.slider("Post-yield hardening ratio", 0.001, 0.2, 0.02, 0.001)
    rot_cap = st.checkbox("Fail at rotation capacity φ = t_p / h_e", False)

    st.subheader("9. Evaluation")
    gamma_M = st.number_input("γ_M (connections)", 1.0, 1.5, 1.1, 0.05)
    eta = st.number_input("η (design moment factor)", 0.5, 1.0, 1.0, 0.05)
    braced = st.checkbox("Braced frame (k_b = 8, else 25)", False)
    eta_S = st.number_input("Stiffness modification η for S_j = S_j,ini/η",
                            1.0, 3.5, 2.0, 0.1)

if x3 <= x2:
    st.error("D3 must be further from the upright than D2.")
    st.stop()

# ============================================================
# RUN
# ============================================================
sim = HookConnectorSPM(
    Material(mat_name, E, nu, fy, fu),
    BeamSection(beam_type, beam_h, beam_b, beam_t, I_cust, W_cust,
                span_for_classification=beam_Lb),
    UprightSection(up_B, up_D, up_c, up_t, up_perf, None, up_H, up_fix),
    HookConnector(n_lips=n_lips, plate_thickness=t_p),
    ComponentParameters(
        hook_width_bh=b_h or None, hook_bending_length_lh=l_h,
        hook_shear_length_Lh=L_h, bearing_width=b_brg, bearing_length=L_brg,
        upright_eff_width_bu=b_u, upright_eff_length_Lu=L_u,
        lip_eff_width_bl=b_l or None, lip_eff_length_Ll=L_l, gamma_M0=g_M0),
    TestRig(a, x2, x3, k_train, noise),
    LoadSchedule(inc, P_max, stop_fail),
    NonlinearOptions(loose, loose_M, psi, hard, rot_cap),
    Evaluation(gamma_M, eta, braced, eta_S),
)
res = sim.run()
rec = res["record"]

# ============================================================
# METRICS
# ============================================================
m = st.columns(5)
m[0].metric("S_j,ini (component)", f"{res['S_j_ini_Nmm_rad'] / 1e6:.1f} kN·m/rad")
m[1].metric("k_ti (equal-area, test)", f"{res['k_ti_Nmm_rad'] / 1e6:.1f} kN·m/rad")
m[2].metric("M_max (test)", f"{res['M_max_Nmm'] / 1e6:.3f} kN·m")
m[3].metric("M_Rd = η·M_max/γ_M", f"{res['M_Rd_Nmm'] / 1e6:.3f} kN·m")
m[4].metric("Classification", res["classification"])

if res["failed"]:
    st.error(f"🚨 Failure at P = {res['P_fail_N']:.0f} N "
             f"(M = {res['P_fail_N'] * a / 1e6:.3f} kN·m) — {res['failure_mode']}")
else:
    st.info(f"Max load reached without failure. Predicted failure at "
            f"P = {res['P_fail_N']:.0f} N — {res['failure_mode']}")
st.caption(f"Increment **{inc} kN/step** · steps **{res['total_steps']}** · "
           f"connector height **{res['connector_height_mm']:.0f} mm** · "
           f"lip height **{res['lip_height_mm']:.1f} mm**")

st.divider()

# ============================================================
# CURVES
# ============================================================
P = np.array(rec["P"])
fig, ax = plt.subplots(1, 3, figsize=(17, 5))

ax[0].plot(rec["D1"], P, "g-", lw=2, label=f"D1 piston (x={a:.0f})")
ax[0].plot(rec["D2"], P, "b-", lw=2, label=f"D2 LVDT (x={x2:.0f})")
ax[0].plot(rec["D3"], P, "r--", lw=1.5, label=f"D3 LVDT (x={x3:.0f})")
ax[0].set(xlabel="Displacement (mm)", ylabel="Load P (N)",
          title="Load vs Displacement")
ax[0].grid(alpha=0.3)
ax[0].legend(loc="lower right", fontsize=8)

th = np.array(rec["theta_corr"])
Mk = np.array(rec["M"]) / 1e6
ax[1].plot(th, Mk, "r-", lw=2.2, label="Test (D3−D2)/Δx")
th_line = np.linspace(0, th.max(), 50)
ax[1].plot(th_line, res["S_j_ini_Nmm_rad"] * th_line / 1e6, "k:", lw=1.2,
           label="S_j,ini (component)")
k_ti = res["k_ti_Nmm_rad"]
if np.isfinite(k_ti):
    th_k = res["M_Rd_Nmm"] / k_ti
    ax[1].plot([0, th_k], [0, res["M_Rd_Nmm"] / 1e6], "b--", lw=1.5,
               label="k_ti equal-area")
ax[1].axhline(res["M_Rd_Nmm"] / 1e6, color="orange", ls=":", label="M_Rd")
ax[1].set_ylim(0, Mk.max() * 1.1 if Mk.max() > 0 else 1)
ax[1].set(xlabel="Rotation θ (rad)", ylabel="Moment M (kN·m)",
          title="Moment vs Rotation")
ax[1].grid(alpha=0.3)
ax[1].legend(loc="lower right", fontsize=8)

ax[2].plot(rec["step"], P, "m-", lw=2)
ax[2].set(xlabel="Step number", ylabel="Load P (N)",
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
lo, hi = res["class_limits_Nmm_rad"]
summary = pd.DataFrame({
    "Quantity": [
        "C1 Beam K1 = 3EI_b/a³", "C1 Beam F1,Rd = M_pl/a", "Beam I", "Upright I",
        "z_eq", "k_eq", "S_j,ini = Σ k_eff z²", "M_j,Rd = Σ F_Rd z",
        "k_ti (equal area)", "Secant 10–40 % M_max", "M_max (test)", "M_Rd",
        "Rotation capacity φ = t_p/h_e", "Pinned limit 0.5 EI_b/L_b",
        "Rigid limit k_b EI_b/L_b", "Classification (stiffness)",
        "Idealised S_j = S_j,ini/η", "Beam M_pl", "Classification (strength)",
        "Failure mode",
    ],
    "Value": [
        f"{res['K1_N_mm']:.1f} N/mm", f"{res['F1_Rd_N']:.0f} N",
        f"{res['I_beam_mm4']:.3e} mm⁴", f"{res['I_upright_mm4']:.3e} mm⁴",
        f"{res['z_eq_mm']:.1f} mm", f"{res['k_eq_N_mm']:.0f} N/mm",
        f"{res['S_j_ini_Nmm_rad'] / 1e6:.2f} kN·m/rad",
        f"{res['M_j_Rd_Nmm'] / 1e6:.3f} kN·m",
        f"{k_ti / 1e6:.2f} kN·m/rad",
        f"{res['k_secant_Nmm_rad'] / 1e6:.2f} kN·m/rad",
        f"{res['M_max_Nmm'] / 1e6:.3f} kN·m", f"{res['M_Rd_Nmm'] / 1e6:.3f} kN·m",
        f"{res['theta_avail_rad']:.4f} rad",
        f"{lo / 1e6:.2f} kN·m/rad", f"{hi / 1e6:.2f} kN·m/rad",
        res["classification"],
        f"{res['S_j_ideal_Nmm_rad'] / 1e6:.2f} kN·m/rad",
        f"{res['M_pl_beam_Nmm'] / 1e6:.3f} kN·m",
        res["strength_classification"], res["failure_mode"],
    ],
})
st.dataframe(summary, width="stretch", hide_index=True)

# ============================================================
# SENSOR DATA + CSV
# ============================================================
st.divider()
st.subheader("📡 Sensor Data (D1, D2, D3)")
sensor_df = pd.DataFrame({
    "Step": rec["step"],
    "Load (N)": rec["P"],
    "D1_piston_mm": rec["D1"],
    "D2_LVDT_mm": rec["D2"],
    "D3_LVDT_mm": rec["D3"],
    "Moment (N·mm)": rec["M"],
    "Rotation_measured (rad)": rec["theta_meas"],
    "Rotation_corrected (rad)": rec["theta_corr"],
})
for idx, f in res["row_forces"].items():
    sensor_df[f"Lip{idx}_force (N)"] = f

with st.expander("🔍 View sensor data", expanded=False):
    st.dataframe(sensor_df, width="stretch", height=350)

st.download_button("📥 Download sensor readings (CSV)",
                   sensor_df.to_csv(index=False).encode("utf-8"),
                   "spm_sensor_readings.csv", "text/csv")
st.download_button("📥 Download summary (CSV)",
                   pd.concat([summary, rows_df.astype(str)], axis=0)
                   .to_csv(index=False).encode("utf-8"),
                   "spm_summary.csv", "text/csv")
