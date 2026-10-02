"""
CBFEM Virtual Test — Initial & Secant Stiffness (Streamlit page)
================================================================
Hook-connector joint (3-lip): upright + beam + hook connector.
All dimensions are entered by the user. The virtual machine finds the maximum
deflection, the load F at which it is reached, K4 = F / t_p, the initial and
secant stiffness, and generates the curves.

Page "CBFEM Virtual Test" of the app — run with:  streamlit run app.py
"""

from math import atan, degrees

import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
import streamlit as st

from cbfem import BEAM_LENGTH, E, G, LOAD_ARM, NU, X_D2, X_D3, CBFEMInputs, run

st.title("🏗️ CBFEM Virtual Test — Initial & Secant Stiffness")
st.caption("Component Based Finite Element Method · Upright + Beam + Hook Connector · "
           f"3-lip hook connector · D1 piston @ {LOAD_ARM:g} mm, D2 @ {X_D2:g} mm, "
           f"D3 @ {X_D3:g} mm")

missing = []


def num(label, key, fmt="%.2f", help=None):
    """Required input: empty until the user enters a value > 0."""
    v = st.number_input(label, min_value=0.0, value=None, key=key, format=fmt,
                        placeholder="0.0", help=help)
    if v is None or v <= 0:
        missing.append(label)
        return None
    return v


def show_k(name, value):
    if value is not None:
        st.markdown(f"**{name} = {value:,.2f} N/mm**")


# ============================================================
# FIXED VALUES
# ============================================================

with st.container(border=True):
    st.markdown("**Fixed values (steel)**")
    f1, f2, f3 = st.columns(3)
    f1.metric("E — Young's modulus", f"{E:,.0f} N/mm²")
    f2.metric("G — Modulus of rigidity", f"{G:,.0f} N/mm²")
    f3.metric("ν — Poisson's ratio", f"{NU}")

# ============================================================
# GEOMETRY → MAX DEFLECTION
# ============================================================

st.subheader("📐 Hook Connector & Beam Geometry")
g = st.columns(4)
with g[0]:
    H = num("H — total hook connector height (mm)", "H",
            help="Also used as the lever arm h in S_j,ini = E·h² / Σ(1/k).")
with g[1]:
    H_t = num("H_t — connector above beam top (mm)", "H_t")
with g[2]:
    beam_depth = num("Beam depth / height (mm)", "beam_depth")
with g[3]:
    t_p = num("t_p — connector thickness (mm)", "t_p")

if H and H_t and beam_depth and t_p:
    hb = H - (H_t + beam_depth)
    if hb > 0:
        th = atan(t_p / hb)
        st.info(
            f"**Test stop (calculated):** H_b = H − (H_t + beam depth) = "
            f"{H:g} − ({H_t:g} + {beam_depth:g}) = **{hb:g} mm** · "
            f"θ_available = tan⁻¹(t_p / H_b) = tan⁻¹({t_p:g}/{hb:g}) = "
            f"**{degrees(th):.4f}° = {th:.4f} rad** · "
            f"δ_bearing = θ_available × H_b = t_p = **{t_p:g} mm** · "
            f"max deflection δ_max = P·a²(3l − a)/(6·E·I_b) is calculated at the "
            f"stop load.")
    else:
        st.error(f"H_b = {H:g} − ({H_t:g} + {beam_depth:g}) = {hb:g} mm. "
                 "It must be greater than 0.")

# ============================================================
# COMPONENT INPUTS
# ============================================================

st.subheader("🧩 Component Stiffness")
r1 = st.columns(3)
r2 = st.columns(3)

with r1[0].container(border=True):
    st.markdown("**C1 · Beam local deformation**  \n`K1 = 3·E·I_b / L_b³`")
    I_b = num("I_b — moment of inertia of beam, x-axis (mm⁴)", "I_b", fmt="%.1f")
    L_b = num("L_b — beam length (mm)", "L_b")
    show_k("K1", 3 * E * I_b / L_b**3 if I_b and L_b else None)

with r1[1].container(border=True):
    st.markdown("**C2 · Hook bending**  \n`K2 = 3·E·I_h / L_h³`")
    I_h = num("I_h — moment of inertia of hook connector (mm⁴)", "I_h", fmt="%.2f")
    L_h = num("L_h — effective hook bending / deformation length (mm)", "L_h",
              help="Used by C2 and C3.")
    show_k("K2", 3 * E * I_h / L_h**3 if I_h and L_h else None)

with r1[2].container(border=True):
    st.markdown("**C3 · Hook shear**  \n`K3 = G·A_h / L_h`")
    A_h = num("A_h — effective hook shear area (mm²)", "A_h")
    st.caption("L_h is taken from C2.")
    show_k("K3", G * A_h / L_h if A_h and L_h else None)

with r2[0].container(border=True):
    st.markdown("**C4 · Hook–upright bearing**  \n`K4 = F / δ_bearing = F / t_p`")
    st.caption("**Calculated by the virtual machine — no input.** "
               "φ_avail = t_p / H_b → δ_bearing = φ_avail × H_b = t_p. "
               "F is the load noted when the test stops at the max deflection.")

with r2[1].container(border=True):
    st.markdown("**C5 · Upright local deformation**  \n`K5 = 3·E·I_u / L_u³`")
    I_u = num("I_u — moment of inertia of upright, x-axis (mm⁴)", "I_u", fmt="%.1f")
    L_u = num("L_u — effective length of deforming upright portion (mm)", "L_u")
    show_k("K5", 3 * E * I_u / L_u**3 if I_u and L_u else None)

with r2[2].container(border=True):
    st.markdown("**C6 · Upright lip deformation**  \n`K6 = E·b_l·t_l³ / (4·L_l³)`")
    b_l = num("b_l — effective width of lip (mm)", "b_l")
    t_l = num("t_l — lip thickness (mm)", "t_l")
    L_l = num("L_l — effective lip length (mm)", "L_l")
    show_k("K6", E * b_l * t_l**3 / (4 * L_l**3) if b_l and t_l and L_l else None)

# ============================================================
# RUN
# ============================================================

st.divider()
c_inc, c_btn = st.columns([1, 2])
increment = c_inc.selectbox("Load increment per step (kN)", [0.01, 0.02],
                            help="Load starts at 0 kN and increases by this amount "
                                 "every step until the max deflection is reached.")
c_btn.write("")
c_btn.write("")
go = c_btn.button("▶ Run Virtual Test", type="primary")

if go:
    if missing:
        st.session_state.pop("cbfem", None)
        st.warning("Enter all inputs first:\n\n" + "\n".join(f"- {m}" for m in missing))
    else:
        inp = CBFEMInputs(H=H, H_t=H_t, beam_depth=beam_depth, t_p=t_p,
                          I_b=I_b, L_b=L_b, I_h=I_h, L_h=L_h, A_h=A_h,
                          I_u=I_u, L_u=L_u, b_l=b_l, t_l=t_l, L_l=L_l)
        try:
            st.session_state["cbfem"] = {"res": run(inp, increment), "inp": inp,
                                         "inc": increment}
        except ValueError as exc:
            st.session_state.pop("cbfem", None)
            st.error(str(exc))

if "cbfem" not in st.session_state:
    st.stop()

R = st.session_state["cbfem"]
res, inp, rec = R["res"], R["inp"], R["res"]["record"]

# ============================================================
# RESULTS
# ============================================================

st.header("📊 Results")
st.success(f"⏹ Test stopped at θ_available = {res['theta_available_rad']:.4f} rad "
           f"after {res['steps']} steps. Load noted: **F = {res['F']:,.2f} N "
           f"({res['F'] / 1000:.4f} kN)** · max deflection "
           f"**δ_max = {res['delta_max']:.4f} mm**.")

m1 = st.columns(4)
m1[0].metric("Stop rotation θ_available", f"{res['theta_available_rad']:.4f} rad",
             f"{res['theta_available_deg']:.3f}°", delta_color="off")
m1[1].metric("Max deflection δ_max", f"{res['delta_max']:.4f} mm",
             "P·a²(3l − a) / 6EI", delta_color="off")
m1[2].metric("Load at max deflection F", f"{res['F'] / 1000:.4f} kN")
m1[3].metric("K4 = F / t_p", f"{res['K4']:,.2f} N/mm")
m2 = st.columns(3)
m2[0].metric("Initial stiffness S_j,ini", f"{res['S_j_ini'] / 1e6:,.3f} kN·m/rad")
m2[1].metric("Secant stiffness S_j = S_j,ini / 2", f"{res['S_j'] / 1e6:,.3f} kN·m/rad")
m2[2].metric("Check: S_j,ini > 0.5·E·I_b / L_b",
             "✅ Satisfied" if res["check_ok"] else "❌ Not satisfied",
             f"limit {res['check_limit'] / 1e6:,.3f} kN·m/rad", delta_color="off")

# ---------------- curves ----------------
P_kN = np.array(rec["P"]) / 1000
M_kNm = np.array(rec["M"]) / 1e6
th = np.array(rec["theta"])
fig, ax = plt.subplots(1, 3, figsize=(17, 5))

ax[0].plot(rec["D1"], P_kN, "g-", lw=2, label=f"D1 piston ({LOAD_ARM:g} mm)")
ax[0].plot(rec["D3"], P_kN, "r--", lw=1.6, label=f"D3 ({X_D3:g} mm)")
ax[0].plot(rec["D2"], P_kN, "b-", lw=2, label=f"D2 ({X_D2:g} mm)")
ax[0].axhline(res["F"] / 1000, color="grey", ls=":", label="F (test stop)")
ax[0].set(xlabel="Displacement (mm)", ylabel="Load P (kN)",
          title="Load vs Displacement (all sensors)")
ax[0].grid(alpha=0.3)
ax[0].legend(loc="lower right", fontsize=8)

ax[1].plot(th, M_kNm, "r-", lw=2.2, label="Virtual test (θ = (D3 − D2)/100)")
th_ini = res["M_el"] / res["S_j_ini"]
ax[1].plot([0, th_ini * 1.15], [0, res["S_j_ini"] * th_ini * 1.15 / 1e6], "k:", lw=1.3,
           label="Initial stiffness S_j,ini")
ax[1].plot([0, res["theta_available_rad"]], [0, res["M_max"] / 1e6], "b--", lw=1.3,
           label="Secant stiffness S_j = S_j,ini/2")
ax[1].axvline(res["theta_available_rad"], color="grey", ls=":", label="θ_available")
ax[1].set(xlabel="Rotation θ (rad)", ylabel="Moment M (kN·m)", title="Moment vs Rotation")
ax[1].grid(alpha=0.3)
ax[1].legend(loc="lower right", fontsize=8)

ax[2].plot(rec["step"], P_kN, "m-", lw=2)
ax[2].set(xlabel="Step number", ylabel="Load P (kN)",
          title=f"Load vs Step (increment = {R['inc']} kN)")
ax[2].grid(alpha=0.3)
plt.tight_layout()
st.pyplot(fig)

# ---------------- component table ----------------
st.subheader("Component stiffness")
comp_df = pd.DataFrame([{
    "Component": f"{c['C']} {c['Component']}",
    "Formula": c["Formula"],
    "Working": c["Working"],
    "K (N/mm)": round(c["K"], 3),
    "k = K/E (mm)": round(c["k = K/E"], 6),
    "1/k (1/mm)": round(c["1/k"], 3),
} for c in res["components"]])
st.dataframe(comp_df, hide_index=True, width="stretch")

# ---------------- step by step ----------------
st.subheader("Step-by-step")
terms = " + ".join(f"{c['1/k']:,.3f}" for c in res["components"])
a = LOAD_ARM
st.markdown(f"""
1. **Test stop:** H_b = {res['H_b']:g} mm, θ_available = tan⁻¹({inp.t_p:g}/{res['H_b']:g})
   = **{res['theta_available_rad']:.4f} rad**.
2. **Load at max deflection (F):** the load rises in {R['inc']} kN steps until θ reaches
   θ_available. F and K4 depend on each other, so they are solved together:
   F = (θ_available·h²/(2·a) − t_p) / Σ(1/K, without K4) =
   ({res['theta_available_rad']:.4f} × {res['h']:g}² / (2 × {a:g}) − {inp.t_p:g}) /
   {res['R_without_K4']:.6f} = **{res['F']:,.2f} N**
3. **K4 = F / δ_bearing = F / t_p** = {res['F']:,.2f} / {inp.t_p:g} = **{res['K4']:,.2f} N/mm**
4. **Σ(1/k_i)** with k_i = K_i / E: {terms} = **{res['sum_inv_k']:,.3f} mm⁻¹**
5. **Initial stiffness** S_j,ini = E·h² / Σ(1/k_i) = {E:,.0f} × {res['h']:g}² /
   {res['sum_inv_k']:,.3f} = **{res['S_j_ini'] / 1e6:,.3f} kN·m/rad**
6. **Secant stiffness** S_j = S_j,ini / 2 = **{res['S_j'] / 1e6:,.3f} kN·m/rad**
7. **Check** 0.5·E·I_b / L_b = {res['check_limit'] / 1e6:,.3f} kN·m/rad →
   **{'satisfied' if res['check_ok'] else 'not satisfied'}**
8. **Max deflection** δ_max = P·a²·(3l − a) / (6·E·I) with P = F, a = {a:g} mm,
   l = {BEAM_LENGTH:g} mm, I = I_b: {res['F']:,.2f} × {a:g}² × (3 × {BEAM_LENGTH:g} − {a:g}) /
   (6 × {E:,.0f} × {inp.I_b:g}) = **{res['delta_max']:.4f} mm**
""")

with st.expander("How the machine finds F: run → note F → K4 = F/t_p → run again"):
    st.caption("Run 1 starts without K4 (bearing taken as rigid). Each run stops at "
               "θ_available; the load noted there updates K4 for the next run, until "
               "F no longer changes. The result equals the closed form in step 2.")
    st.dataframe(pd.DataFrame(res["iterations"]).round(4), hide_index=True,
                 width="stretch")

with st.expander("How the curve is built"):
    st.markdown(f"""
* Moment at the connector: M = P × {a:g} mm. The test stops at M_max = F × {a:g} =
  {res['M_max'] / 1e6:.4f} kN·m.
* Up to ⅔·M_max (the EN 1993-1-8 elastic limit) the slope is **S_j,ini**.
* From there the curve goes straight to the stop point (θ_available, M_max), so the
  line from the origin to the stop point has the slope **S_j = S_j,ini / 2**.
* Sensors: D(x) = x · tan θ at D1 = {a:g}, D2 = {X_D2:g} and D3 = {X_D3:g} mm.
  The beam (K1) is already inside S_j,ini, so it is not added again.
""")

# ---------------- CSVs ----------------
st.subheader("📡 Sensor Data")
sensor_df = pd.DataFrame({
    "Load (kN)": np.round(P_kN, 4),
    "D1 piston (mm)": np.round(rec["D1"], 3),
    "D2 (mm)": np.round(rec["D2"], 3),
    "D3 (mm)": np.round(rec["D3"], 3),
})
with st.expander("🔍 View sensor data", expanded=False):
    st.dataframe(sensor_df, hide_index=True, width="stretch", height=320)

summary = pd.concat([
    comp_df,
    pd.DataFrame([
        {"Component": "θ_available (rad)", "Working": f"{res['theta_available_rad']:.5f}"},
        {"Component": "Max deflection δ_max (mm)", "Working": f"{res['delta_max']:.4f}"},
        {"Component": "F — load at max deflection (N)", "Working": f"{res['F']:.3f}"},
        {"Component": "Σ(1/k)", "1/k (1/mm)": round(res["sum_inv_k"], 3)},
        {"Component": "h (mm)", "Working": f"{res['h']:g}"},
        {"Component": "S_j,ini (kN·m/rad)", "Working": f"{res['S_j_ini'] / 1e6:.4f}"},
        {"Component": "S_j (kN·m/rad)", "Working": f"{res['S_j'] / 1e6:.4f}"},
        {"Component": "Check limit 0.5·E·I_b/L_b (kN·m/rad)",
         "Working": f"{res['check_limit'] / 1e6:.4f}"},
        {"Component": "Check satisfied", "Working": str(res["check_ok"])},
    ]),
])
d1, d2 = st.columns(2)
d1.download_button("📥 Download sensor readings (CSV)",
                   sensor_df.to_csv(index=False).encode("utf-8"),
                   "cbfem_sensor_readings.csv", "text/csv", width="stretch")
d2.download_button("📥 Download results (CSV)", summary.to_csv(index=False).encode("utf-8"),
                   "cbfem_results.csv", "text/csv", width="stretch")
