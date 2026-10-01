"""
Virtual SPM — Beam Stiffness Tester (Streamlit prototype)
=========================================================
COP-style component analysis of the assembly  UPRIGHT + BEAM + HOOK CONNECTOR.
Page "Virtual Test" of the app — run with:  streamlit run app.py
"""

import base64
import os
import sys

import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
import streamlit as st

ROOT = os.path.dirname(os.path.abspath(__file__))
if ROOT not in sys.path:
    sys.path.insert(0, ROOT)

import catalog  # noqa: E402
from physics_engine import (  # noqa: E402
    BEAM_LENGTH, E, G, LOAD_ARM, NU, X_D2, X_D3,
    Beam, ComponentInputs, Connector, Material, TestSetup, Upright, VirtualSPM,
)

st.markdown("""
<style>
.dim-box {background:#EAF0F2;border:1px solid #D5DEE2;border-radius:6px;
          padding:10px 16px;display:grid;grid-template-columns:1fr 1fr;gap:8px 12px}
.dim-box .lbl {font-family:monospace;font-size:0.75rem;color:#667}
.dim-box .val {font-family:monospace;font-weight:700;font-size:1.05rem;color:#2E5566}
</style>""", unsafe_allow_html=True)

st.title("🏗️ Virtual SPM — Component-Method Beam Stiffness Tester")
st.caption("Upright + Beam + Hook Connector · component analysis (COP style) · "
           f"virtual cantilever test: beam {BEAM_LENGTH:g} mm, D1 piston @ "
           f"{LOAD_ARM:g} mm, D2 @ {X_D2:g} mm, D3 @ {X_D3:g} mm")

missing = []


def num(label, key, value=None, fmt="%.2f", min_value=0.0, container=st, help=None):
    """Required number input; empty (None) until the user enters a value."""
    v = container.number_input(label, min_value=min_value, value=value, key=key,
                               format=fmt, placeholder="0.0", help=help)
    if v is None or v <= 0:
        missing.append(label)
        return None
    return v


def dim_box(values: dict):
    cells = "".join(f"<div><div class='lbl'>{k}</div><div class='val'>{v:g}</div></div>"
                    if isinstance(v, (int, float)) else
                    f"<div><div class='lbl'>{k}</div><div class='val'>{v}</div></div>"
                    for k, v in values.items())
    st.markdown(f"<div class='dim-box'>{cells}</div>", unsafe_allow_html=True)


ASSETS = os.path.join(ROOT, "assets")


def card_image(name, height=170):
    """Section drawing centred at a fixed height, as on the client frontend."""
    path = os.path.join(ASSETS, name)
    if os.path.exists(path):
        with open(path, "rb") as f:
            data = base64.b64encode(f.read()).decode()
        st.markdown(f"<div style='text-align:center;margin-bottom:8px'>"
                    f"<img src='data:image/png;base64,{data}' "
                    f"style='height:{height}px;max-width:100%;object-fit:contain'></div>",
                    unsafe_allow_html=True)


# ============================================================
# 1. CLIENT + SECTIONS
# ============================================================

client = st.text_input("**Client Name**", placeholder="Enter client name")
mode = st.segmented_control("Section source", ["Select from list", "Customize"],
                            default="Select from list", label_visibility="collapsed")
custom = mode == "Customize"

c_up, c_beam, c_con = st.columns(3)

with c_up.container(border=True):
    card_image("upright.png")
    if custom:
        st.markdown("**Customize Upright**")
        up = {k: num(f"{k} (mm)", f"up_{k}") for k in ("D", "W", "B", "T")}
        up_name = "Custom upright"
    else:
        st.markdown("**Select Upright**")
        up_name = st.selectbox("Upright", list(catalog.UPRIGHTS), label_visibility="collapsed")
        up = catalog.UPRIGHTS[up_name]
        dim_box({f"{k} (MM)": v for k, v in up.items()})

with c_beam.container(border=True):
    card_image("beam.png")
    if custom:
        st.markdown("**Customize Beam**")
        bm = {k: num(f"{k} (mm)", f"bm_{k}") for k in ("H", "W", "T")}
        bm["type"] = st.text_input("Enter type of beam", placeholder="Enter value")
        beam_name = bm["type"] or "Custom beam"
    else:
        st.markdown("**Select Type of Beam**")
        beam_name = st.selectbox("Beam", list(catalog.BEAMS), label_visibility="collapsed")
        bm = catalog.BEAMS[beam_name]
        dim_box({f"{k} (MM)": v for k, v in bm.items() if k != "type"})

with c_con.container(border=True):
    card_image("connector.png")
    if custom:
        st.markdown("**Customize Connector**")
        n = st.selectbox("No. of lip", [3, 4, 5])
        con = {"n_lips": n, **{k: num(f"{k} (mm)", f"con_{k}") for k in ("H", "D", "W", "T")}}
        con_name = f"Custom {n} lip connector"
    else:
        st.markdown("**Connector Type**")
        con_name = st.selectbox("Connector", list(catalog.CONNECTORS),
                                label_visibility="collapsed")
        con = catalog.CONNECTORS[con_name]
        dim_box({"NO. OF LIP": con["n_lips"],
                 **{f"{k} (MM)": con[k] for k in ("H", "D", "W", "T")}})

# ============================================================
# 2. MATERIAL — IS 2062 : 2011
# ============================================================

st.divider()
m_mech, m_chem = st.columns(2)
with m_mech:
    st.caption("IS 2062 : 2011")
    st.markdown("**Mechanical Properties**  \n*(Clauses 5, 10.3, 10.3.1, 11.3.1, 12.2 and 12.4)*")
    grade = st.selectbox("Grade Designation", list(catalog.IS2062_MECHANICAL))
    mech = catalog.IS2062_MECHANICAL[grade]
    st.dataframe(pd.DataFrame([
        {"Quality": q, "Tensile Strength Rm, Min MPa": r["Rm"],
         "Yield Stress <20": r["ReH <20"], "Yield Stress 20-40": r["ReH 20-40"],
         "Yield Stress >40": r["ReH >40"], "% Elongation": r["A %"]}
        for q, r in mech.items()]), hide_index=True, width="stretch")
with m_chem:
    st.caption("IS 2062 : 2011")
    st.markdown("**Chemical Properties**  \n*(Clauses 5, 8.1 and 8.2)*")
    quality = st.selectbox("Quality", list(mech))
    st.dataframe(pd.DataFrame([
        {"Quality": q, "C, Max %": r["C"], "Mn, Max %": r["Mn"], "S, Max %": r["S"],
         "P, Max %": r["P"], "Si, Max %": r["Si"], "Carbon Equiv. (CE), Max": r["CE"],
         "Mode of Deoxidation": r["Deoxidation"]}
        for q, r in catalog.IS2062_CHEMICAL[grade].items()]),
        hide_index=True, width="stretch")

thicknesses = [t for t in (up.get("T"), bm.get("T"), con.get("T")) if t]
t_max = max(thicknesses) if thicknesses else 0.0
fy = catalog.yield_strength(grade, quality, t_max)
fu = mech[quality]["Rm"]
st.info(f"**Steel {grade} {quality}:** fy = **{fy} N/mm²** (thickest part {t_max:g} mm "
        f"< 20 mm band) · fu = **{fu} N/mm²** · E = {E:.0f} N/mm² · "
        f"G = {G:.0f} N/mm² · ν = {NU}")

# ============================================================
# 3. COMPONENT STIFFNESS INPUTS
# ============================================================

st.divider()
st.subheader("🧩 Component Stiffness Inputs")
st.caption("Each component's stiffness is calculated individually from its own "
           "formula. All values are per lip for C2–C6.")


def show_k(label, value):
    if value is not None:
        st.markdown(f"**{label} = {value:,.1f} N/mm**")


r1 = st.columns(3)
r2 = st.columns(3)

with r1[0].container(border=True):
    st.markdown("**C1 · Beam local deformation**  \n`K1 = 3·E·I_b / L³`,  L = 400 mm")
    I_b = num("I_b — moment of inertia of beam (mm⁴)", "I_b", fmt="%.1f",
              help=(f"Box {bm['H']:g}×{bm['W']:g}×{bm['T']:g}: "
                    f"{Beam(bm['H'], bm['W'], bm['T']).I_box:,.0f} mm⁴")
              if all(bm.get(k) for k in ("H", "W", "T")) else None)
    show_k("K1", 3 * E * I_b / LOAD_ARM**3 if I_b else None)

with r1[1].container(border=True):
    st.markdown("**C2 · Hook bending**  \n`K2 = 3·E·I_h / l_h³`")
    I_h = num("I_h — moment of inertia of hook connector (mm⁴)", "I_h", fmt="%.2f")
    l_h = num("l_h — effective hook bending length (mm)", "l_h")
    show_k("K2", 3 * E * I_h / l_h**3 if I_h and l_h else None)

with r1[2].container(border=True):
    st.markdown("**C3 · Hook shear**  \n`K3 = G·A_h / L_h`,  G = 80769 N/mm²")
    A_h = num("A_h — effective hook shear area (mm²)", "A_h")
    L_h = num("L_h — effective hook deformation length (mm)", "L_h")
    show_k("K3", G * A_h / L_h if A_h and L_h else None)

with r2[0].container(border=True):
    st.markdown("**C4 · Hook–upright bearing**  \n`K4 = F / δ_bearing`")
    F_b = num("F — max load at hook–upright contact (N)", "F_b", fmt="%.1f")
    d_b = num("δ_bearing — max deflection at contact (mm)", "d_b", fmt="%.3f")
    show_k("K4", F_b / d_b if F_b and d_b else None)

with r2[1].container(border=True):
    st.markdown("**C5 · Upright local deformation**  \n`K5 = 3·E·I_u / L_u³`")
    L_u = num("L_u — effective length of deforming upright portion (mm)", "L_u")
    I_u = num("I_u — second moment of area of effective upright strip (mm⁴)", "I_u",
              fmt="%.3f")
    b_u = num("b_u — effective width of upright wall (mm)", "b_u")
    t_u = num("t_u — thickness of upright (mm)", "t_u", value=up.get("T"))
    show_k("K5", 3 * E * I_u / L_u**3 if I_u and L_u else None)
    if b_u and t_u:
        st.caption(f"Check: b_u·t_u³/12 = {b_u * t_u**3 / 12:,.3f} mm⁴")

with r2[2].container(border=True):
    st.markdown("**C6 · Upright lip deformation**  \n`K6 = E·b_l·t_l³ / (4·L_l³)`")
    b_l = num("b_l — effective width of lip (mm)", "b_l")
    t_l = num("t_l — lip thickness (mm)", "t_l", value=con.get("T"))
    L_l = num("L_l — effective lip length (mm)", "L_l")
    show_k("K6", E * b_l * t_l**3 / (4 * L_l**3) if b_l and t_l and L_l else None)

# ============================================================
# 4. LOAD SCHEDULE + RUN
# ============================================================

st.divider()
st.subheader("⚙️ Load Schedule")
s1, s2, s3 = st.columns([1, 1, 1])
increment = s1.selectbox("Load increment per step (kN)", [0.01, 0.02],
                         help="Load starts at 0 kN and increases gradually by this "
                              "amount per step.")
d_max = num("Max deflection — test stops when D1 reaches it (mm)", "d_max",
            container=s2)
s3.write("")
s3.write("")
run = s3.button("▶ Run Virtual Test", type="primary", width="stretch")

if run:
    if missing:
        st.session_state.pop("results", None)
        st.warning("Enter all required inputs first:\n\n"
                   + "\n".join(f"- {m}" for m in missing))
    else:
        try:
            sim = VirtualSPM(
                Material(grade, quality, fy, fu),
                Upright(up["D"], up["W"], up["B"], up["T"]),
                Beam(bm["H"], bm["W"], bm["T"], bm.get("type", "")),
                Connector(con["n_lips"], con["H"], con["D"], con["W"], con["T"]),
                ComponentInputs(I_b, I_h, l_h, A_h, L_h, F_b, d_b,
                                L_u, I_u, b_u, t_u, b_l, t_l, L_l),
                TestSetup(increment, d_max),
            )
            st.session_state["results"] = {
                "res": sim.run(), "client": client, "increment": increment,
                "d_max": d_max, "names": (up_name, beam_name, con_name),
                "steel": f"IS 2062 {grade} {quality} (fy {fy}, fu {fu})"}
        except ValueError as exc:
            st.session_state.pop("results", None)
            st.error(str(exc))

if "results" not in st.session_state:
    st.stop()

# ============================================================
# 5. RESULTS
# ============================================================

R = st.session_state["results"]
res, rec = R["res"], R["res"]["record"]
st.divider()
st.header(f"📊 Results{' — ' + R['client'] if R['client'] else ''}")
st.caption(" · ".join(R["names"]) + " · " + R["steel"])

m = st.columns(4)
m[0].metric("Rotational stiffness — elastic  S_j,ini", f"{res['S_j_ini'] / 1e6:.2f} kN·m/rad")
m[1].metric("Rotational stiffness — plastic  S_j", f"{res['S_j'] / 1e6:.2f} kN·m/rad")
m[2].metric("Moment resistance — elastic  M_j,el", f"{res['M_j_el'] / 1e6:.3f} kN·m")
m[3].metric("Moment resistance — plastic  M_j,Rd", f"{res['M_j_Rd'] / 1e6:.3f} kN·m")
st.caption(
    f"📈 Load increment: **{R['increment']} kN/step** | Total steps: **{res['steps']}** | "
    f"Max deflection: **{R['d_max']:g} mm** | Peak load: **{res['P_peak'] / 1000:.3f} kN** | "
    f"M_j,Rd governed by: **{res['M_governed_by']}**")

P_kN = np.array(rec["P"]) / 1000
fig, axes = plt.subplots(1, 3, figsize=(17, 5))

ax = axes[0]
ax.plot(rec["D1"], P_kN, "g-", lw=2, label="D1 piston")
ax.plot(rec["D2"], P_kN, "b-", lw=2, label="D2 LVDT (40 mm)")
ax.plot(rec["D3"], P_kN, "r--", lw=1.5, label="D3 LVDT (140 mm)")
ax.axhline(res["P_el"] / 1000, color="orange", ls=":", alpha=0.8, label="Elastic limit")
ax.axhline(res["P_Rd"] / 1000, color="grey", ls=":", alpha=0.8, label="Plastic limit")
ax.set(xlabel="Displacement (mm)", ylabel="Load P (kN)",
       title="Load vs Displacement (all sensors)")
ax.grid(True, alpha=0.3)
ax.legend(loc="lower right", fontsize=8)

ax = axes[1]
th = np.array(rec["theta_meas"])
ax.plot(th, np.array(rec["M"]) / 1e6, "r-", lw=2.2, label="Test: θ = (D3 − D2)/100")
ax.plot(rec["theta"], np.array(rec["M"]) / 1e6, "k:", lw=1.3, label="Connection only")
ax.axhline(res["M_j_el"] / 1e6, color="orange", ls=":", label="M_j,el")
ax.axhline(res["M_j_Rd"] / 1e6, color="grey", ls=":", label="M_j,Rd")
ax.set(xlabel="Rotation θ (rad)", ylabel="Moment M (kN·m)", title="Moment vs Rotation")
ax.grid(True, alpha=0.3)
ax.legend(loc="lower right", fontsize=8)

ax = axes[2]
ax.plot(rec["step"], P_kN, "m-", lw=2)
ax.set(xlabel="Step number", ylabel="Load P (kN)",
       title=f"Load vs Step (increment = {R['increment']} kN)")
ax.grid(True, alpha=0.3)
plt.tight_layout()
st.pyplot(fig)

st.subheader("🧩 Component Analysis")
comp_df = pd.DataFrame(res["components"])
comp_df = comp_df.round({"Stiffness K (N/mm)": 1, "Resistance F_Rd (N)": 0,
                         "Deformation δ (mm)": 4})
st.dataframe(comp_df, hide_index=True, width="stretch")
st.caption(f"Per lip: C2–C6 in series → k_lip = {res['k_lip']:,.1f} N/mm; "
           f"governing component: {res['governing']}. Deformation δ at the last "
           "recorded load.")
with st.expander("Lip assembly (lever arms to connector bottom edge)"):
    st.dataframe(pd.DataFrame(res["lips"]).round(3), hide_index=True, width="stretch")

if res["plastic_plateau"]:
    st.warning(f"M_j,Rd reached at P = {res['P_Rd'] / 1000:.3f} kN; the load was held "
               f"while deflection increased to {R['d_max']:g} mm.")
else:
    st.success(f"Max deflection {R['d_max']:g} mm reached at P = "
               f"{res['P_peak'] / 1000:.3f} kN.")

st.subheader("📡 Sensor Data")
sensor_df = pd.DataFrame({
    "Load (kN)": np.round(P_kN, 3),
    "D1 piston (mm)": np.round(rec["D1"], 2),
    "D2 (mm)": np.round(rec["D2"], 2),
    "D3 (mm)": np.round(rec["D3"], 2),
})
with st.expander("🔍 View sensor data", expanded=True):
    st.dataframe(sensor_df, hide_index=True, width="stretch", height=320)

summary_df = pd.DataFrame({
    "Quantity": ["Client", "Upright", "Beam", "Connector", "Steel",
                 "Rotational stiffness elastic S_j,ini (kN·m/rad)",
                 "Rotational stiffness plastic S_j (kN·m/rad)",
                 "Moment resistance elastic M_j,el (kN·m)",
                 "Moment resistance plastic M_j,Rd (kN·m)"]
    + [f"{c['Component']} K (N/mm)" for c in res["components"]],
    "Value": [R["client"], *R["names"], R["steel"],
              round(res["S_j_ini"] / 1e6, 3), round(res["S_j"] / 1e6, 3),
              round(res["M_j_el"] / 1e6, 4), round(res["M_j_Rd"] / 1e6, 4)]
    + [round(c["Stiffness K (N/mm)"], 1) for c in res["components"]],
})
d1, d2 = st.columns(2)
d1.download_button("📥 Download sensor readings (CSV)",
                   sensor_df.to_csv(index=False).encode("utf-8"),
                   "spm_sensor_readings.csv", "text/csv", width="stretch")
d2.download_button("📥 Download results summary (CSV)",
                   summary_df.to_csv(index=False).encode("utf-8"),
                   "spm_results_summary.csv", "text/csv", width="stretch")
