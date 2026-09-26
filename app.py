"""
Streamlit GUI — Virtual SPM for Beam-End Hook Connector Stiffness Testing
========================================================================
Cantilever beam-end-connector test evaluated with the EN 1993-1-8 component
method (as in COP) adapted to hook ("lip") rows, components C1–C6.
Load starts at 0 kN and increases by 0.01 or 0.02 kN per step until the
maximum deflection is reached.
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

st.set_page_config(
    page_title="Virtual SPM — Beam Stiffness Tester",
    page_icon="🏗️",
    layout="wide",
)

st.title("🏗️ Virtual SPM — Component-Method Beam Stiffness Tester")
st.caption("Upright + beam + hook connector — 3-sensor layout "
           "(D1 piston @ 400 mm, D2 @ 40 mm, D3 @ 140 mm)")

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

    # ---------- 1. Material ----------
    st.subheader("1. Material (Steel)")
    material_name = st.text_input("Material name", "Steel")
    col1, col2 = st.columns(2)
    with col1:
        E = st.number_input("E (N/mm²)", 50000.0, 300000.0, 210000.0, 1000.0)
        fy = required("fy (N/mm²)", 100.0, 1000.0, 5.0)
    with col2:
        nu = st.number_input("ν", 0.1, 0.5, 0.3, 0.01)
        fu = required("fu (N/mm²)", 100.0, 1200.0, 5.0)
    st.caption(f"G = E / 2(1+ν) = **{E / (2 * (1 + nu)):.0f} N/mm²**")

    # ---------- 2. Beam ----------
    st.subheader("2. Beam Geometry (C1)")
    beam_L = st.number_input("Beam length (mm)", 100.0, 2000.0, 500.0, 10.0)
    beam_section = st.selectbox("Section type", ["box", "solid_rect", "custom"])
    beam_h = required("Beam depth h_b (mm)", 5.0, 500.0, 1.0)
    beam_b = beam_t = I_cust = W_cust = None
    if beam_section in ("box", "solid_rect"):
        beam_b = required("Beam width b (mm)", 5.0, 500.0, 1.0)
    if beam_section == "box":
        beam_t = required("Beam wall thickness (mm)", 0.5, 20.0, 0.1)
    if beam_section == "custom":
        I_cust = required("Beam I_b (mm⁴)", 1e3, 1e9, 1e4, fmt="%.3e")
        W_cust = required("Beam W_pl (mm³)", 1e2, 1e8, 1e3, fmt="%.3e")
    beam_Lb = st.number_input("Rack beam span L_b for classification (mm)",
                              500.0, 10000.0, value=None, step=50.0,
                              placeholder="optional")

    # ---------- 3. Upright ----------
    st.subheader("3. Upright (Column)")
    up_H = st.number_input("Upright length (mm)", 100.0, 3000.0, 800.0, 10.0)
    up_B = required("Slotted face width (mm)", 10.0, 300.0, 1.0)
    up_D = required("Side-wall depth (mm)", 10.0, 300.0, 1.0)
    up_c = required("Return lip (mm)", 0.0, 100.0, 1.0)
    up_t = required("Upright thickness t_u (mm)", 0.5, 10.0, 0.1)
    up_I = st.number_input("I_u override (mm⁴)", 1e3, 1e9, value=None, step=1e4,
                           format="%.3e", placeholder="computed from section")
    up_perf = st.slider("Perforation factor I_net/I_gross", 0.5, 1.0, 1.0, 0.01)

    # ---------- 4. Hook connector ----------
    st.subheader("4. Hook Connector")
    n_lips = st.selectbox("Number of lips", [5, 4, 3], index=0)
    st.caption(f"Height h_c = **{LIP_HEIGHTS[n_lips]:.0f} mm** · width 44 mm · "
               "pitch 50 mm · top 10.3 / bottom 34.7 mm · "
               "1st lip centre 25.1 mm")
    t_p = st.number_input("Connector thickness t_p (mm)", 1.0, 10.0, 4.0, 0.5)

    # ---------- 5. Component parameters ----------
    st.subheader("5. Component Parameters (per lip)")
    st.caption("Effective lengths / widths from the component formulae — "
               "estimates, to be calibrated against a physical test.")
    with st.expander("C2 Hook bending · K2 = 3EI_h / l_h³"):
        l_h = st.number_input("Effective hook bending length l_h (mm)",
                              1.0, 50.0, 8.0, 0.5)
        b_h = st.number_input("Hook width b_h (mm) — 0 = lip height 29.6",
                              0.0, 60.0, 0.0, 0.5)
    with st.expander("C3 Hook shear · K3 = G·A_h / L_h"):
        L_h = st.number_input("Effective hook deformation length L_h (mm)",
                              1.0, 50.0, 8.0, 0.5)
    with st.expander("C4 Hook–upright bearing · K4 = E·b·t_u / L"):
        b_brg = st.number_input("Bearing width b_bearing (mm)", 1.0, 60.0, 12.0, 0.5)
        L_brg = st.number_input("Bearing length L_bearing (mm)", 1.0, 60.0, 10.0, 0.5)
    with st.expander("C5 Upright local · K5 = E·b_u·t_u³ / 4L_u³"):
        b_u = st.number_input("Effective upright width b_u (mm)", 5.0, 150.0, 40.0, 1.0)
        L_u = st.number_input("Effective upright length L_u (mm)", 2.0, 100.0, 15.0, 0.5)
    with st.expander("C6 Lip deformation · K6 = E·b_l·t_l³ / 4L_l³"):
        b_l = st.number_input("Effective lip width b_l (mm) — 0 = pitch 50",
                              0.0, 100.0, 0.0, 1.0)
        L_l = st.number_input("Effective lip length L_l (mm)", 2.0, 100.0, 20.0, 0.5)

    # ---------- 6. Load schedule ----------
    st.subheader("6. Load Schedule")
    st.markdown("**Load increment per step** (starts at 0 kN)")
    load_increment = st.selectbox(
        "Increment (kN)", options=[0.01, 0.02], index=0,
        help="Gradual increment in applied load per step.")
    max_defl = required("Max deflection — test stops (mm)", 0.1, 500.0, 1.0)
    stop_sensor = st.selectbox(
        "Max deflection measured on", ["D1", "D2", "D3"],
        format_func=lambda k: {"D1": "D1 piston", "D2": "D2", "D3": "D3"}[k])
    dt = st.number_input("Time per step (s)", 0.001, 10.0, 0.02, 0.001, format="%.3f")

    # ---------- 7. Sensors ----------
    st.subheader("7. Sensor Layout")
    a = st.number_input("D1 piston position from upright face (mm)",
                        50.0, 2000.0, 400.0, 10.0)
    x2 = st.number_input("D2 position from upright face (mm)", 0.0, 2000.0, 40.0, 5.0)
    x3 = st.number_input("D3 position from upright face (mm)", 1.0, 2000.0, 140.0, 5.0)
    dial_res = st.number_input("Sensor resolution (mm)", 0.001, 0.1, 0.01, 0.001,
                               format="%.3f")
    noise = st.number_input("Sensor noise σ (mm)", 0.0, 0.1, 0.0, 0.001, format="%.3f")

    # ---------- 8. Non-linear behaviour ----------
    st.subheader("8. Non-Linear Behaviour")
    psi = st.slider("ψ — M-θ curve shape (EN 1993-1-8)", 1.0, 4.0, 2.7, 0.1)
    hard = st.slider("Post-yield hardening ratio", 0.001, 0.20, 0.02, 0.001)

    st.markdown("**Additional effects** (not part of the handwritten C1–C6 method)")
    extras = st.checkbox("Include additional effects", False)
    loose, loose_M, up_fixity, k_train = 0.0, 5e4, "rigid", 1e15
    if extras:
        loose = st.number_input("Connector looseness θ₀ (rad)", 0.0, 0.05, 0.004,
                                0.001, format="%.3f")
        loose_M = st.number_input("Looseness closure moment (N·mm)", 1e3, 1e7, 5e4,
                                  1e3, format="%.0e")
        up_fixity = st.selectbox("Upright global bending (clamping)",
                                 ["fixed-fixed", "pinned-pinned", "rigid"])
        k_train = st.number_input("Piston + load-cell stiffness (N/mm)",
                                  1e3, 1e8, 2e5, 1e4, format="%.0e")

    # ---------- 9. Evaluation ----------
    st.subheader("9. Evaluation")
    gamma_M0 = st.number_input("γ_M0 (component resistances)", 1.0, 1.5, 1.0, 0.05)
    gamma_M = st.number_input("γ_M (connection design moment)", 1.0, 1.5, 1.1, 0.05)
    eta = st.number_input("η (design moment factor)", 0.5, 1.0, 1.0, 0.05)
    eta_S = st.number_input("η for idealised S_j = S_j,ini/η", 1.0, 3.5, 2.0, 0.1)
    braced = st.checkbox("Braced frame (k_b = 8, else 25)", False)


# ============================================================
# VALIDATION
# ============================================================

if missing:
    st.warning("Enter the required inputs in the sidebar to run the virtual "
               "test:\n\n" + "\n".join(f"- {m}" for m in missing))
    st.stop()
errors = []
if fu < fy:
    errors.append("fu must be greater than or equal to fy.")
if x3 <= x2:
    errors.append("D3 must be further from the upright than D2.")
if max(a, x3) > beam_L:
    errors.append("Piston and sensors must lie on the beam (≤ beam length).")
if beam_section == "box" and 2 * beam_t >= min(beam_h, beam_b):
    errors.append("Beam wall thickness is too large for the section.")
for e in errors:
    st.error(e)
if errors:
    st.stop()


# ============================================================
# BUILD MODEL + RUN
# ============================================================

sim = HookConnectorSPM(
    Material(fy=fy, fu=fu, E=E, nu=nu, name=material_name),
    BeamSection(beam_section, beam_h, beam_b, beam_t, I_cust, W_cust,
                length=beam_L, span_for_classification=beam_Lb),
    UprightSection(up_B, up_D, up_c, up_t, up_perf, up_I, up_H, up_fixity),
    HookConnector(n_lips=n_lips, plate_thickness=t_p),
    ComponentParameters(
        hook_width_bh=b_h or None, hook_bending_length_lh=l_h,
        hook_shear_length_Lh=L_h, bearing_width=b_brg, bearing_length=L_brg,
        upright_eff_width_bu=b_u, upright_eff_length_Lu=L_u,
        lip_eff_width_bl=b_l or None, lip_eff_length_Ll=L_l, gamma_M0=gamma_M0),
    TestRig(max_defl, stop_sensor, a, x2, x3, k_train, noise),
    LoadSchedule(load_increment, dt, dial_res),
    NonlinearOptions(loose, loose_M, psi, hard),
    Evaluation(gamma_M, eta, braced, eta_S),
)
results = sim.run()
rec = results["record"]


# ============================================================
# METRICS
# ============================================================

col_a, col_b, col_c, col_d, col_e = st.columns(5)
k_ti = results["k_ti_Nmm_rad"]
col_a.metric("Initial Stiffness S_j,ini",
             f"{results['S_j_ini_Nmm_rad'] / 1e6:.1f} kN·m/rad")
col_b.metric("Test Stiffness k_ti (D3−D2)",
             f"{k_ti / 1e6:.1f} kN·m/rad" if np.isfinite(k_ti) else "—")
col_c.metric("Peak Load", f"{results['P_max_N'] / 1000:.3f} kN")
col_d.metric("Moment Resistance M_j,Rd",
             f"{results['M_j_Rd_Nmm'] / 1e6:.3f} kN·m")
col_e.metric("Joint Classification", results["classification"].split(" (")[0])

st.caption(
    f"📈 Load increment: **{load_increment} kN/step**  |  "
    f"Total steps: **{results['total_steps']}**  |  "
    f"Max deflection: **{max_defl:g} mm on {stop_sensor}**  |  "
    f"Connector: **{n_lips} lips, {results['connector_height_mm']:.0f} mm**"
)

st.divider()


# ============================================================
# CURVES
# ============================================================

P_kN = np.array(rec["P"]) / 1000.0
fig, axes = plt.subplots(1, 3, figsize=(17, 5))

# --- Load vs Deflection ---
ax = axes[0]
ax.plot(rec["D1"], P_kN, "g-", lw=2.0, label=f"D1 piston ({a:.0f} mm)")
ax.plot(rec["D2"], P_kN, "b-", lw=2.0, label=f"D2 ({x2:.0f} mm)")
ax.plot(rec["D3"], P_kN, "r--", lw=1.5, label=f"D3 ({x3:.0f} mm)")
ax.axhline(results["M_j_Rd_Nmm"] / a / 1000, color="orange", ls=":", alpha=0.8,
           label="M_j,Rd / a")
ax.set_xlabel("Displacement (mm)")
ax.set_ylabel("Load P (kN)")
ax.set_title("Load vs Displacement (all sensors)")
ax.grid(True, alpha=0.3)
ax.legend(loc="lower right", fontsize=8)

# --- Moment vs Rotation ---
ax = axes[1]
th = np.array(rec["theta_corr"])
Mk = np.array(rec["M"]) / 1e6
ax.plot(th, Mk, "r-", lw=2.2, label="θ = (D3 − D2) / (x3 − x2)")
th_line = np.linspace(0, min(th.max(), 1.2 * Mk.max() * 1e6
                             / results["S_j_ini_Nmm_rad"]), 50)
ax.plot(th_line, results["S_j_ini_Nmm_rad"] * th_line / 1e6, "k:", lw=1.2,
        label="S_j,ini")
if np.isfinite(k_ti):
    ax.plot([0, results["M_Rd_Nmm"] / k_ti], [0, results["M_Rd_Nmm"] / 1e6],
            "b--", lw=1.4, label="k_ti (equal area)")
ax.set_ylim(0, Mk.max() * 1.1 if Mk.max() > 0 else 1)
ax.set_xlabel("Rotation θ (rad)")
ax.set_ylabel("Moment M (kN·m)")
ax.set_title("Moment vs Rotation")
ax.grid(True, alpha=0.3)
ax.legend(loc="lower right", fontsize=8)

# --- Load vs Step ---
ax = axes[2]
ax.plot(rec["step"], P_kN, "m-", lw=2.0)
ax.set_xlabel("Step number")
ax.set_ylabel("Load P (kN)")
ax.set_title(f"Load vs Step (increment = {load_increment} kN)")
ax.grid(True, alpha=0.3)

plt.tight_layout()
st.pyplot(fig)

st.divider()


# ============================================================
# COMPONENT TABLE
# ============================================================

st.subheader("🧩 Component Yield Check (Component Method, EN 1993-1-8)")
comp_df = pd.DataFrame([
    {
        "Component": c["Component"],
        "Stiffness K (N/mm)": f"{c['Stiffness K (N/mm)']:.1f}",
        "Resistance F_Rd (N)": f"{c['Resistance F_Rd (N)']:.0f}",
        "Force at peak (N)": f"{c['Force at peak (N)']:.0f}",
        "Deformation δ (mm)": f"{c['Deformation δ at peak (mm)']:.4f}",
        "Yielded at peak?": "✅ YES" if c["Yielded?"] else "—",
    }
    for c in results["component_table"]
])
st.dataframe(comp_df, width="stretch", hide_index=True)

with st.expander("Per-lip assembly (C2–C6 in series, lever arm z to connector bottom)"):
    st.dataframe(pd.DataFrame(results["rows_table"]).round(1),
                 width="stretch", hide_index=True)


# ============================================================
# SUMMARY
# ============================================================

st.subheader("📋 Summary")
lims = results["class_limits_Nmm_rad"]
summary_df = pd.DataFrame({
    "Quantity": [
        "Young's Modulus E", "Shear Modulus G", "Yield Strength fy",
        "Beam I_b", "Beam W_pl", "Upright I_u",
        "Load arm a (D1)", "Load increment", "Total steps", "Stop reason",
        "Beam stiffness K1 = 3EI_b/a³",
        "Equivalent lever arm z_eq", "Equivalent stiffness k_eq",
        "Initial stiffness S_j,ini = Σ k_eff z²",
        "Idealised stiffness S_j = S_j,ini/η",
        "Moment resistance M_j,Rd = Σ F_Rd z",
        "Test stiffness k_ti (equal area)", "Secant stiffness 10–40 % M_max",
        "Peak moment M_max", "Design moment M_Rd = η M_max/γ_M",
        "Rotation capacity φ = t_p/h_e", "Max rotation in test",
        "Stiffness classification", "Strength classification",
    ],
    "Value": [
        f"{E:.0f} N/mm²", f"{E / (2 * (1 + nu)):.0f} N/mm²", f"{fy:.0f} N/mm²",
        f"{results['I_beam_mm4']:.3e} mm⁴", f"{sim.Wpl_b:.3e} mm³",
        f"{results['I_upright_mm4']:.3e} mm⁴",
        f"{a:.0f} mm", f"{load_increment} kN", f"{results['total_steps']}",
        results["stop_reason"],
        f"{results['K1_N_mm']:.1f} N/mm",
        f"{results['z_eq_mm']:.1f} mm", f"{results['k_eq_N_mm']:.0f} N/mm",
        f"{results['S_j_ini_Nmm_rad'] / 1e6:.2f} kN·m/rad",
        f"{results['S_j_ideal_Nmm_rad'] / 1e6:.2f} kN·m/rad",
        f"{results['M_j_Rd_Nmm'] / 1e6:.3f} kN·m",
        f"{k_ti / 1e6:.2f} kN·m/rad" if np.isfinite(k_ti) else "—",
        f"{results['k_secant_Nmm_rad'] / 1e6:.2f} kN·m/rad",
        f"{results['M_max_Nmm'] / 1e6:.3f} kN·m",
        f"{results['M_Rd_Nmm'] / 1e6:.3f} kN·m",
        f"{results['theta_avail_rad']:.4f} rad",
        f"{results['theta_max_rad']:.4f} rad",
        results["classification"]
        + (f" ({lims[0] / 1e6:.1f} – {lims[1] / 1e6:.1f} kN·m/rad)" if lims else ""),
        results["strength_classification"],
    ],
})
st.dataframe(summary_df, width="stretch", hide_index=True)


# ============================================================
# WARNINGS
# ============================================================

for c in results["component_table"]:
    if c["Yielded?"]:
        st.info(f"🔵 {c['Component']} yielded — post-yield stiffness reduced.")
if results["rotation_capacity_exceeded"]:
    st.warning(f"⚠️ Rotation {results['theta_max_rad']:.4f} rad exceeds the "
               f"available rotation φ = t_p/h_e = {results['theta_avail_rad']:.4f} rad.")
if results["peak_reached"]:
    st.error(f"🚨 {results['stop_reason']}. Peak load "
             f"{results['P_cap_N'] / 1000:.3f} kN.")
else:
    st.success(f"⏹ {results['stop_reason']} at P = {results['P_max_N'] / 1000:.3f} kN.")


# ============================================================
# SENSOR DATA + CSV
# ============================================================

st.divider()
st.subheader("📡 Sensor Data (D1, D2, D3)")


def quantise(v, q):
    return np.round(np.round(np.asarray(v) / q) * q, 6)


sensor_df = pd.DataFrame({
    "Load 1 kN": np.round(P_kN, 3),
    "Dial 1 mm": quantise(rec["D1"], dial_res),
    "Dial 2 mm": quantise(rec["D2"], dial_res),
    "Dial 3 mm": quantise(rec["D3"], dial_res),
    "Time Sec.": np.round(rec["time_s"], 3),
})
detail_df = pd.DataFrame({
    "Step": rec["step"], "Time (s)": rec["time_s"], "Load (N)": rec["P"],
    "D1_piston_mm": rec["D1"], "D2_mm": rec["D2"], "D3_mm": rec["D3"],
    "Moment (N·mm)": rec["M"],
    "Rotation (D3-D2)/dx (rad)": rec["theta_meas"],
    "Rotation corrected (rad)": rec["theta_corr"],
})
for idx, f in results["row_forces"].items():
    detail_df[f"Lip{idx} force (N)"] = f

with st.expander("🔍 View sensor data", expanded=True):
    st.dataframe(sensor_df, width="stretch", height=350, hide_index=True)

st.download_button("📥 Download sensor readings (CSV)",
                   sensor_df.to_csv(index=False).encode("utf-8"),
                   "spm_sensor_readings.csv", "text/csv")
st.download_button("📥 Download detailed readings (CSV)",
                   detail_df.to_csv(index=False).encode("utf-8"),
                   "spm_detailed_readings.csv", "text/csv")
st.download_button("📥 Download summary (CSV)",
                   pd.concat([summary_df, comp_df.rename(
                       columns={"Component": "Quantity"})], axis=0)
                   .to_csv(index=False).encode("utf-8"),
                   "spm_summary.csv", "text/csv")
