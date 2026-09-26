"""
Streamlit GUI — Virtual SPM for Beam Stiffness Testing (E250 Steel)
===================================================================
Load increment selectable: 0.01 or 0.02 kN per step.
Number of steps derived from max_load / increment.
"""

import streamlit as st
import numpy as np
import matplotlib.pyplot as plt
import pandas as pd

from physics_engine import (
    MaterialInput, BeamGeometry, UprightGeometry,
    ConnectionProperties, HookConnector, LoadInput,
    NonlinearOptions, ComponentMethodSPM,
)

st.set_page_config(
    page_title="Virtual SPM — Beam Stiffness Tester",
    page_icon="🏗️",
    layout="wide",
)

st.title("🏗️ Virtual SPM — Component-Method Beam Stiffness Tester")
st.caption("Upright + beam + semi-rigid connection + hook — 3-sensor layout (D1, D2, D3)")


# ============================================================
# SIDEBAR
# ============================================================

with st.sidebar:
    st.header("⚙️ Input Parameters")

    # ---------- 1. Material ----------
    st.subheader("1. Material")
    material_name = st.text_input("Material name", "E250 Steel (IS 2062)")
    col1, col2 = st.columns(2)
    with col1:
        E_GPa = st.number_input("E (GPa)", 50.0, 400.0, 200.0, 1.0)
    with col2:
        fy_MPa = st.number_input("fy (MPa)", 100.0, 1000.0, 250.0, 5.0)

    # ---------- 2. Beam ----------
    st.subheader("2. Beam Geometry")
    beam_L = st.number_input(
        "Beam length to load point (mm)", 100.0, 5000.0, 400.0, 10.0)
    beam_b = st.number_input("Beam width b (mm)", 5.0, 500.0, 30.0, 1.0)
    beam_h = st.number_input("Beam height h (mm)", 5.0, 500.0, 60.0, 1.0)
    beam_section = st.selectbox("Section type", ["rectangular", "circular"])

    # ---------- 3. Upright ----------
    st.subheader("3. Upright (Column)")
    up_H = st.number_input("Upright height (mm)", 50.0, 3000.0, 800.0, 10.0)
    up_b = st.number_input("Upright width (mm)", 10.0, 1000.0, 300.0, 10.0)
    up_t = st.number_input("Upright thickness (mm)", 2.0, 200.0, 50.0, 1.0)
    up_E = st.number_input("Upright E (GPa)", 50.0, 400.0, 200.0, 1.0)
    up_fy = st.number_input("Upright fy (MPa)", 100.0, 1000.0, 250.0, 5.0)
    up_fixity = st.selectbox("Base fixity", ["fixed", "pinned"])

    # ---------- 4. Connection ----------
    st.subheader("4. Beam–Upright Connection")
    conn_type = st.selectbox(
        "Connection type",
        ["bolted_end_plate", "welded", "custom"]
    )
    S_j = st.number_input(
        "Rotational stiffness S_j (N·mm/rad)",
        min_value=1e6, max_value=1e13, value=5e8, step=1e7,
        format="%.2e"
    )
    M_j = st.number_input(
        "Moment resistance M_j,Rd (N·mm)",
        min_value=1e4, max_value=1e10, value=1.5e6, step=1e5,
        format="%.2e"
    )
    post_yield = st.slider(
        "Connection post-yield tangent ratio", 0.001, 0.50, 0.05, 0.005)

    # ---------- 5. Hook ----------
    st.subheader("5. Hook / Connector")
    hook_L = st.number_input("Hook length (mm)", 1.0, 500.0, 100.0, 1.0)
    hook_b = st.number_input("Hook width (mm)", 1.0, 200.0, 20.0, 1.0)
    hook_t = st.number_input("Hook thickness (mm)", 1.0, 200.0, 10.0, 1.0)
    hook_E = st.number_input("Hook E (GPa)", 50.0, 400.0, 200.0, 1.0)
    hook_fy = st.number_input("Hook fy (MPa)", 100.0, 1000.0, 250.0, 5.0)
    hook_offset = st.number_input(
        "Hook offset from tip (mm)", 0.0, 500.0, 0.0, 1.0)

    # ---------- 6. Load Schedule ----------
    st.subheader("6. Load Schedule")
    max_load = st.number_input(
        "Max load (N)", 100.0, 200000.0, 12000.0, 500.0)
    failure_load = st.number_input(
        "Anticipated failure load (N)", 100.0, 300000.0, 15000.0, 500.0)
    apply_preload = st.checkbox("Apply 10% preload (Eurocode practice)", True)

    st.markdown("**Load increment per step**")
    load_increment = st.selectbox(
        "Increment (kN)",
        options=[0.01, 0.02],
        index=0,
        help="Gradual increment in applied load per step. "
             "0.01 kN → finer resolution, more steps. "
             "0.02 kN → coarser, fewer steps."
    )

    # Show derived number of steps
    n_steps_est = int(np.ceil(max_load / (load_increment * 1000.0))) + 1
    st.caption(f"→ Number of load steps: **{n_steps_est}**")

    st.markdown("**Loading-train stiffness**")
    loadcell_k = st.number_input(
        "Load-cell stiffness (N/mm)", 1e4, 1e8, 5.0e5, 1e4,
        format="%.0e")
    actuator_k = st.number_input(
        "Actuator stiffness (N/mm)", 1e4, 1e8, 1.0e6, 1e4,
        format="%.0e")

    # ---------- 7. Sensors ----------
    st.subheader("7. Sensor Layout")
    d2_pos = st.number_input(
        "D2 sensor position from root (mm)",
        min_value=0.0, max_value=5000.0,
        value=float(beam_L), step=10.0,
    )

    # ---------- 8. Non-Linear Behaviour ----------
    st.subheader("8. Non-Linear Behaviour")

    st.markdown("**A. Seating gap**")
    nl_seating = st.checkbox("Enable seating gap closure", True)
    if nl_seating:
        nl_gap = st.number_input("Initial gap (mm)", 0.0, 5.0, 0.15, 0.01)
        nl_slip = st.number_input(
            "Gap closes at load (N)", 1.0, 2000.0, 200.0, 10.0)
    else:
        nl_gap, nl_slip = 0.0, 1.0

    st.markdown("**B. Beam yielding**")
    nl_beam_yield = st.checkbox("Enable beam elastic–plastic yield", True)
    if nl_beam_yield:
        nl_hardening = st.slider(
            "Strain-hardening ratio", 0.0, 0.20, 0.02, 0.005)
    else:
        nl_hardening = 0.0

    st.markdown("**C. Connection plastic hinge**")
    nl_conn_yield = st.checkbox(
        "Enable connection post-yield softening", True)

    st.markdown("**D. Upright yielding**")
    nl_up_yield = st.checkbox("Enable upright yield", True)

    st.markdown("**E. Hook yielding**")
    nl_hook_yield = st.checkbox("Enable hook yield", True)

    st.markdown("**F. Geometric non-linearity**")
    nl_geo = st.checkbox("Enable large-deflection stiffening", False)


# ============================================================
# BUILD MODEL OBJECTS
# ============================================================

material = MaterialInput(
    name=material_name,
    youngs_modulus_GPa=E_GPa,
    yield_strength_MPa=fy_MPa,
)
beam = BeamGeometry(beam_L, beam_b, beam_h, beam_section)
upright = UprightGeometry(
    height_mm=up_H, width_mm=up_b, thickness_mm=up_t,
    youngs_modulus_GPa=up_E, yield_strength_MPa=up_fy,
    base_fixity=up_fixity,
)
connection = ConnectionProperties(
    rotational_stiffness_Nmm_per_rad=S_j,
    moment_resistance_Nmm=M_j,
    connection_type=conn_type,
    post_yield_stiffness_ratio=post_yield,
)
hook = HookConnector(
    length_mm=hook_L, width_mm=hook_b, thickness_mm=hook_t,
    youngs_modulus_GPa=hook_E, yield_strength_MPa=hook_fy,
    offset_from_tip_mm=hook_offset,
)
load_in = LoadInput(
    max_load_N=max_load,
    failure_load_N=failure_load,
    apply_preload=apply_preload,
    loadcell_stiffness_N_per_mm=loadcell_k,
    actuator_stiffness_N_per_mm=actuator_k,
    load_increment_kN=load_increment,      # ← 0.01 or 0.02
)
nonlinear = NonlinearOptions(
    enable_seating=nl_seating,
    seating_gap_mm=nl_gap,
    seating_slip_load_N=nl_slip,
    enable_beam_yield=nl_beam_yield,
    beam_strain_hardening_ratio=nl_hardening,
    enable_connection_yield=nl_conn_yield,
    enable_upright_yield=nl_up_yield,
    enable_hook_yield=nl_hook_yield,
    enable_geometric_nl=nl_geo,
)

sim = ComponentMethodSPM(
    material, beam, upright, connection, hook, load_in, nonlinear,
    d2_position_mm=d2_pos,
)
results = sim.run()


# ============================================================
# METRICS
# ============================================================

col_a, col_b, col_c, col_d, col_e = st.columns(5)
col_a.metric("Measured Stiffness (δ_tip)",
             f"{results['k_linear_N_per_mm']:.1f} N/mm")
col_b.metric("Corrected (D2 − D3)",
             f"{results['k_corrected_N_per_mm']:.1f} N/mm")
col_c.metric("Ideal Beam Stiffness",
             f"{results['k_beam_ideal_N_per_mm']:.1f} N/mm")
col_d.metric("Stiffness Loss",
             f"{results['stiffness_loss_pct']:.1f} %")
col_e.metric("Rigidity Ratio",
             f"{results['rigidity_ratio']*100:.1f} %")

st.caption(
    f"📈 Load increment: **{results['load_increment_kN']} kN/step**  |  "
    f"Total steps: **{results['total_steps']}**  |  "
    f"Max load: **{max_load:.0f} N**"
)

st.divider()


# ============================================================
# CURVES
# ============================================================

fig, axes = plt.subplots(1, 3, figsize=(17, 5))

# --- Load vs Deflection ---
ax = axes[0]
ax.plot(results["D1"], results["loads"], "g-",  lw=2.0, label="D1 piston")
ax.plot(results["D2"], results["loads"], "b-",  lw=2.0, label="D2 LVDT")
ax.plot(results["D3"], results["loads"], "r--", lw=1.5, label="D3 root")
ax.plot(results["beam_only"], results["loads"], "k:", lw=2.0,
        label="Beam only (D2−D3)")
for s in results["springs"]:
    if s.enabled and s.F_Rd < max(results["loads"]):
        ax.axhline(s.F_Rd, color="orange", ls=":", alpha=0.6)
ax.set_xlabel("Displacement (mm)")
ax.set_ylabel("Load P (N)")
ax.set_title("Load vs Displacement (all sensors)")
ax.grid(True, alpha=0.3)
ax.legend(loc="lower right", fontsize=8)

# --- Moment vs Rotation ---
ax = axes[1]
ax.plot(results["rotations"], results["moments"], "r-", lw=2.2)
ax.set_xlabel("Rotation θ (rad)")
ax.set_ylabel("Moment M (N·mm)")
ax.set_title("Moment vs Rotation")
ax.grid(True, alpha=0.3)

# --- Load vs Step ---
ax = axes[2]
ax.plot(results["steps"], results["loads"], "m-", lw=2.0)
ax.set_xlabel("Step number")
ax.set_ylabel("Load P (N)")
ax.set_title(f"Load vs Step (increment = {results['load_increment_kN']} kN)")
ax.grid(True, alpha=0.3)

plt.tight_layout()
st.pyplot(fig)

st.divider()


# ============================================================
# COMPONENT YIELD TABLE
# ============================================================

st.subheader("🧩 Component Yield Check (Eurocode-style)")
yt = results["yield_table"]
yield_df = pd.DataFrame([
    {
        "Component": name,
        "Elastic k (N/mm)": f"{v['k_N_per_mm']:.1f}",
        "Yield load F_Rd (N)": f"{v['F_Rd_N']:.0f}",
        "Yielded at P_max?": "✅ YES" if v["yielded"] else "—",
    }
    for name, v in yt.items()
])
st.dataframe(yield_df, width="stretch", hide_index=True)


# ============================================================
# SUMMARY
# ============================================================

st.subheader("📋 Summary")

summary_df = pd.DataFrame({
    "Quantity": [
        "Young's Modulus E", "Yield Strength fy",
        "Beam I", "Beam Z", "Upright I",
        "Effective Length L_eff", "D2 sensor position",
        "Preload Applied",
        "Load increment",
        "Total steps",
        "Measured Stiffness (δ_tip)",
        "Corrected Stiffness (D2−D3)",
        "Ideal Beam Stiffness",
        "Max Bending Stress", "Beam Yielded?",
        "Load at Beam Yield",
        "Parasitic Deflection",
        "Loading-train Deflection",
        "Rigidity Ratio",
    ],
    "Value": [
        f"{results['E_MPa']:.0f} MPa",
        f"{results['fy_MPa']:.0f} MPa",
        f"{results['I_beam_mm4']:.0f} mm⁴",
        f"{results['Z_beam_mm3']:.0f} mm³",
        f"{results['I_upright_mm4']:.0f} mm⁴",
        f"{results['L_eff_mm']:.1f} mm",
        f"{results['D2_position_mm']:.1f} mm",
        f"{results['preload_N']:.1f} N",
        f"{results['load_increment_kN']} kN",
        f"{results['total_steps']}",
        f"{results['k_linear_N_per_mm']:.1f} N/mm",
        f"{results['k_corrected_N_per_mm']:.1f} N/mm",
        f"{results['k_beam_ideal_N_per_mm']:.1f} N/mm",
        f"{results['max_stress_MPa']:.1f} MPa",
        "YES" if results["yielded"] else "NO",
        f"{results['P_yield_N']:.1f} N" if results["P_yield_N"] else "—",
        f"{results['parasitic_deflection_mm']:.4f} mm",
        f"{results['load_train_deflection_mm']:.4f} mm",
        f"{results['rigidity_ratio']*100:.2f} %",
    ]
})
st.dataframe(summary_df, width="stretch", hide_index=True)


# ============================================================
# WARNINGS
# ============================================================

for name, flag in results["yielded_flags"].items():
    if flag:
        st.info(f"🔵 {name} yielded — post-yield stiffness reduced.")

if results["rigidity_ratio"] > 0.20:
    st.warning(
        f"⚠️ Machine compliance is {results['rigidity_ratio']*100:.1f}% "
        "of total deflection."
    )

if results["yielded"]:
    st.error(
        f"🚨 Beam first yielded at P = {results['P_yield_N']:.1f} N."
    )


# ============================================================
# SENSOR DATA + CSV
# ============================================================

st.divider()
st.subheader("📡 Sensor Data (D1, D2, D3)")

sensor_df = pd.DataFrame({
    "Step":                  results["steps"],
    "Load (N)":              results["loads"],
    "D1_piston_mm":          results["D1"],
    "D2_beam_mm":            results["D2"],
    "D3_root_mm":            results["D3"],
    "Beam_only_mm_(D2-D3)":  results["beam_only"],
    "Moment (N·mm)":         results["moments"],
    "Rotation (rad)":        results["rotations"],
    "Stress (MPa)":          results["stresses"],
})

with st.expander("🔍 View sensor data", expanded=True):
    st.dataframe(sensor_df, width="stretch", height=350)

csv_sensors = sensor_df.to_csv(index=False).encode("utf-8")
st.download_button(
    "📥 Download sensor readings (CSV)",
    csv_sensors,
    "spm_sensor_readings.csv",
    "text/csv",
)

csv_summary = summary_df.to_csv(index=False).encode("utf-8")
st.download_button(
    "📥 Download summary (CSV)",
    csv_summary,
    "spm_summary.csv",
    "text/csv",
)