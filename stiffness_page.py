"""
CBFEM Virtual Test — Initial & Secant Stiffness (Streamlit page)
================================================================
Hook-connector joint: upright + beam + hook connector (any number of lips).
The user chooses or enters the sections, the component properties and the
max load P. The virtual machine raises the load in steps until it reaches the
max load P, where the test stops; δ_max = P·a²(3l − a)/(6·E·I) and the moment
M = P·a are calculated at the max load. K4 = F / θ_available (kN/rad) with F and
θ_available entered by the user. Calculates the initial and secant
stiffness, and generates the curves.

Page of the app — run with:  streamlit run app.py
"""

import base64
import os

import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
import streamlit as st

import catalog
from cbfem import (BEAM_LENGTH, E, G, LOAD_ARM, NU, X_D2, X_D3, CBFEMInputs,
                   deflection, run)

ASSETS = os.path.join(os.path.dirname(os.path.abspath(__file__)), "assets")

st.markdown("""
<style>
.dim-box {background:#EAF0F2;border:1px solid #D5DEE2;border-radius:6px;
          padding:10px 16px;display:grid;grid-template-columns:1fr 1fr;gap:8px 12px}
.dim-box .lbl {font-family:monospace;font-size:0.75rem;color:#667}
.dim-box .val {font-family:monospace;font-weight:700;font-size:1.05rem;color:#2E5566}
</style>""", unsafe_allow_html=True)

st.title("🏗️ CBFEM Virtual Test — Initial & Secant Stiffness")
st.caption("Component Based Finite Element Method · Upright + Beam + Hook Connector · "
           f"a = {LOAD_ARM:g} mm (D1 piston), l = {BEAM_LENGTH:g} mm, "
           f"D2 @ {X_D2:g} mm, D3 @ {X_D3:g} mm")

missing = []


def num(label, key, fmt="%.2f", help=None, container=st):
    """Required input: empty until the user enters a value > 0."""
    v = container.number_input(label, min_value=0.0, value=None, key=key, format=fmt,
                               placeholder="0.0", help=help)
    if v is None or v <= 0:
        missing.append(label)
        return None
    return v


def show_k(name, working, value):
    """Live value with its working, e.g. K1 = 3 × 210,000 × I_b / L_b³ = **… N/mm**."""
    if value is not None:
        st.markdown(f"{name} = {working} = **{value:,.2f} N/mm**")


def dim_box(values: dict):
    cells = "".join(f"<div><div class='lbl'>{k}</div><div class='val'>{v:g}</div></div>"
                    if isinstance(v, (int, float)) else
                    f"<div><div class='lbl'>{k}</div><div class='val'>{v}</div></div>"
                    for k, v in values.items())
    st.markdown(f"<div class='dim-box'>{cells}</div>", unsafe_allow_html=True)


def card_image(name, height=170):
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
        up_name = st.selectbox("Upright", list(catalog.UPRIGHTS),
                               label_visibility="collapsed")
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
        n_lips = st.selectbox("No. of lip", [3, 4, 5])
        con = {"n_lips": n_lips,
               **{k: num(f"{k} (mm)", f"con_{k}") for k in ("H", "D", "W", "T")}}
        con_name = f"Custom {n_lips} lip connector"
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
    st.markdown("**Mechanical Properties**  \n"
                "*(Clauses 5, 10.3, 10.3.1, 11.3.1, 12.2 and 12.4)*")
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
st.info(f"**Fixed values (steel):** E = {E:,.0f} N/mm² · G = {G:,.0f} N/mm² · ν = {NU}")

# ============================================================
# 3. GEOMETRY — entered by the user
# ============================================================

st.divider()
st.subheader("📐 Hook Connector & Beam Geometry")
def card_hint(value):
    return f"Card value: {value:g} mm" if value else None


g = st.columns(4)
with g[0]:
    H = num("H — hook connector height, = h (mm)", "geo_H", help=card_hint(con.get("H")))
with g[1]:
    t_p = num("t_p — connector thickness (mm)", "geo_tp", help=card_hint(con.get("T")))
with g[2]:
    beam_depth = num("Beam depth (mm)", "geo_bd", help=card_hint(bm.get("H")))
with g[3]:
    H_t = num("H_t — connector above beam top (mm)", "H_t")

if H and H_t and beam_depth and t_p:
    hb = H - (H_t + beam_depth)
    if hb > 0:
        st.info(f"H_b = H − (H_t + beam depth) = {H:g} − ({H_t:g} + {beam_depth:g}) = "
                f"**{hb:g} mm** · t_p / H_b = {t_p:g}/{hb:g} = **{t_p / hb:.5f} rad** "
                "(for reference — θ_available is entered in C4)")
    else:
        st.error(f"H_b = {H:g} − ({H_t:g} + {beam_depth:g}) = {hb:g} mm. "
                 "It must be greater than 0.")

# ============================================================
# 4. COMPONENT INPUTS
# ============================================================

st.subheader("🧩 Component Stiffness")
r1 = st.columns(3)
r2 = st.columns(3)

with r1[0].container(border=True):
    st.markdown("**C1 · Beam local deformation**  \n`K1 = 3·E·I_b / L_b³`")
    I_b = num("I_b — moment of inertia of beam, x-axis (mm⁴)", "I_b", fmt="%.1f",
              help="Also used in δ_max = P·a²(3l − a)/(6·E·I).")
    L_b = num("L_b — beam length (mm)", "L_b")
    show_k("K1", f"3 × {E:,.0f} × {I_b:g} / {L_b:g}³" if I_b and L_b else "",
           3 * E * I_b / L_b**3 if I_b and L_b else None)

with r1[1].container(border=True):
    st.markdown("**C2 · Hook bending**  \n`K2 = 3·E·I_h / L_h³`")
    I_h = num("I_h — moment of inertia of hook connector (mm⁴)", "I_h", fmt="%.2f")
    L_h = num("L_h — effective hook bending / deformation length (mm)", "L_h",
              help="Used by C2 and C3.")
    show_k("K2", f"3 × {E:,.0f} × {I_h:g} / {L_h:g}³" if I_h and L_h else "",
           3 * E * I_h / L_h**3 if I_h and L_h else None)

with r1[2].container(border=True):
    st.markdown("**C3 · Hook shear**  \n`K3 = G·A_h / L_h`")
    A_h = num("A_h — effective hook shear area (mm²)", "A_h")
    st.caption("L_h is taken from C2.")
    show_k("K3", f"{G:,.0f} × {A_h:g} / {L_h:g}" if A_h and L_h else "",
           G * A_h / L_h if A_h and L_h else None)

with r2[0].container(border=True):
    st.markdown("**C4 · Hook–upright bearing**  \n`K4 = F / θ_available`  (kN/rad)")
    F_K4 = num("F — force (kN)", "F_K4", fmt="%.4f")
    theta_avail = num("θ_available (rad)", "theta_avail", fmt="%.5f",
                      help="Enter in radians. It is not converted to mm.")
    if F_K4 and theta_avail:
        st.markdown(f"K4 = {F_K4:g} / {theta_avail:g} = **{F_K4 / theta_avail:,.4f} kN/rad**")

with r2[1].container(border=True):
    st.markdown("**C5 · Upright local deformation**  \n`K5 = 3·E·I_u / L_u³`")
    I_u = num("I_u — moment of inertia of upright, x-axis (mm⁴)", "I_u", fmt="%.1f")
    L_u = num("L_u — effective length of deforming upright portion (mm)", "L_u")
    show_k("K5", f"3 × {E:,.0f} × {I_u:g} / {L_u:g}³" if I_u and L_u else "",
           3 * E * I_u / L_u**3 if I_u and L_u else None)

with r2[2].container(border=True):
    st.markdown("**C6 · Upright lip deformation**  \n`K6 = E·b_l·t_l³ / (4·L_l³)`")
    b_l = num("b_l — effective width of lip (mm)", "b_l")
    t_l = num("t_l — lip thickness (mm)", "t_l")
    L_l = num("L_l — effective lip length (mm)", "L_l")
    show_k("K6", f"{E:,.0f} × {b_l:g} × {t_l:g}³ / (4 × {L_l:g}³)" if b_l and t_l and L_l
           else "", E * b_l * t_l**3 / (4 * L_l**3) if b_l and t_l and L_l else None)

# ============================================================
# 5. MAX DEFLECTION + RUN
# ============================================================

st.subheader("⏹ Max Load (test stop) & Max Deflection")
with st.container(border=True):
    st.markdown("`δ_max = [P·a²·(3l − a)] / (6·E·I)`  ·  P = max load, a = 400 mm, "
                "l = 500 mm, I = I_b (from C1)")
    m_cols = st.columns([1, 2])
    with m_cols[0]:
        P_max = num("P — max load (kN)", "P_max", fmt="%.3f",
                    help="The test stops when the load reaches this value. Also used for δ_max.")
    if P_max and I_b:
        m_cols[1].markdown(
            f"δ_max = {P_max * 1000:,.0f} × {LOAD_ARM:g}² × (3 × {BEAM_LENGTH:g} − "
            f"{LOAD_ARM:g}) / (6 × {E:,.0f} × {I_b:g}) = "
            f"**{deflection(P_max * 1000, I_b):.4f} mm**")

st.divider()
c_inc, c_btn = st.columns([1, 2])
with c_inc:
    increment = num("Load increment per step (kN)", "increment", fmt="%.3f",
                    help="Load starts at 0 kN and increases by this amount "
                         "every step until the max load is reached.")
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
                          I_u=I_u, L_u=L_u, b_l=b_l, t_l=t_l, L_l=L_l,
                          P_max_kN=P_max, F_kN=F_K4, theta_avail=theta_avail)
        try:
            st.session_state["cbfem"] = {
                "res": run(inp, increment), "inp": inp, "inc": increment,
                "client": client, "names": (up_name, beam_name, con_name),
                "steel": f"IS 2062 {grade} {quality}"}
        except ValueError as exc:
            st.session_state.pop("cbfem", None)
            st.error(str(exc))

if "cbfem" not in st.session_state:
    st.stop()

R = st.session_state["cbfem"]
res, inp, rec = R["res"], R["inp"], R["res"]["record"]
a = LOAD_ARM

# ============================================================
# 6. RESULTS
# ============================================================

st.header(f"📊 Results{' — ' + R['client'] if R['client'] else ''}")
st.caption(" · ".join(R["names"]) + " · " + R["steel"])
st.success(f"⏹ Test stopped at the max load **P = {res['P_stop'] / 1000:.3f} kN** after "
           f"{res['steps']} steps · D1 = **{rec['D1'][-1]:.4f} mm** · moment "
           f"**M = P × a = {res['M_max'] / 1e6:.4f} kN·m** · δ_max = "
           f"**{res['delta_max']:.4f} mm**.")

m1 = st.columns(4)
m1[0].metric("Max deflection δ_max", f"{res['delta_max']:.4f} mm",
             "P·a²(3l − a) / 6EI", delta_color="off")
m1[1].metric("D1 at max load", f"{rec['D1'][-1]:.4f} mm")
m1[2].metric("Moment M = P × a", f"{res['M_max'] / 1e6:.4f} kN·m")
m1[3].metric("K4 = F / θ_available", f"{res['K4_kN_rad']:,.4f} kN/rad")
m1[0].caption(f"δ_max = {res['P_max']:,.0f} × {a:g}² × (3 × {BEAM_LENGTH:g} − {a:g}) / "
              f"(6 × {E:,.0f} × {inp.I_b:g}) = **{res['delta_max']:.4f} mm**")
m1[1].caption(f"D1 = P·a³/(3·E·I_b) + a·tan θ = {res['P_stop']:,.0f} × {a:g}³ / (3 × "
              f"{E:,.0f} × {inp.I_b:g}) + {a:g} × tan({rec['theta'][-1]:.6g}) = "
              f"**{rec['D1'][-1]:.4f} mm**")
m1[2].caption(f"M = P × a = {res['P_stop']:,.2f} × {a:g} = {res['M_max']:,.0f} N·mm = "
              f"**{res['M_max'] / 1e6:.4f} kN·m**")
m1[3].caption(f"K4 = F / θ_available = {inp.F_kN:g} kN / {inp.theta_avail:g} rad = "
              f"**{res['K4_kN_rad']:,.4f} kN/rad** (used as {res['K4_kN_rad'] * 1000:,.1f} "
              "N/rad in 1/K1 + … + 1/K6)")
m2 = st.columns(3)
m2[0].metric("Initial stiffness S_j,ini", f"{res['S_j_ini'] / 1e6:,.3f} kN·m/rad")
m2[1].metric("Secant stiffness S_j = S_j,ini / 2", f"{res['S_j'] / 1e6:,.3f} kN·m/rad")
m2[2].metric("Check: S_j,ini > 0.5·E·I_b / L_b",
             "✅ Satisfied" if res["check_ok"] else "❌ Not satisfied",
             f"limit {res['check_limit'] / 1e6:,.3f} kN·m/rad", delta_color="off")
m2[0].caption(f"S_j,ini = E × h² / (1/K1 + … + 1/K6) = {E:,.0f} × {res['h']:g}² / "
              f"{res['sum_inv_K']:.6g} = {res['S_j_ini']:,.6g} N·mm/rad = "
              f"**{res['S_j_ini'] / 1e6:,.3f} kN·m/rad**")
m2[1].caption(f"S_j = S_j,ini / 2 = {res['S_j_ini'] / 1e6:,.3f} / 2 = "
              f"**{res['S_j'] / 1e6:,.3f} kN·m/rad**")
m2[2].caption(f"0.5 × E × I_b / L_b = 0.5 × {E:,.0f} × {inp.I_b:g} / {inp.L_b:g} = "
              f"{res['check_limit']:,.0f} N·mm/rad = **{res['check_limit'] / 1e6:,.3f} "
              f"kN·m/rad** → {res['S_j_ini'] / 1e6:,.3f} "
              f"{'>' if res['check_ok'] else '≤'} {res['check_limit'] / 1e6:,.3f}")

# ---------------- curves ----------------
P_kN = np.array(rec["P"]) / 1000
M_kNm = np.array(rec["M"]) / 1e6
th = np.array(rec["theta"])
fig, ax = plt.subplots(1, 3, figsize=(17, 5))

ax[0].plot(rec["D1"], P_kN, "g-", lw=2, label=f"D1 piston ({a:g} mm)")
ax[0].plot(rec["D3"], P_kN, "r--", lw=1.5, label=f"D3 ({X_D3:g} mm)")
ax[0].plot(rec["D2"], P_kN, "b-", lw=1.5, label=f"D2 ({X_D2:g} mm)")
ax[0].axvline(res["delta_max"], color="grey", ls=":", label="δ_max (beam, at max load)")
ax[0].set(xlabel="Displacement (mm)", ylabel="Load P (kN)", title="Load vs Displacement")
ax[0].grid(alpha=0.3)
ax[0].legend(loc="lower right", fontsize=8)

ax[1].plot(th, M_kNm, "r-", lw=2.2, label="Virtual test")
th_ini = res["M_el"] / res["S_j_ini"]
ax[1].plot([0, th_ini * 1.15], [0, res["S_j_ini"] * th_ini * 1.15 / 1e6], "k:", lw=1.3,
           label="Initial stiffness S_j,ini")
ax[1].plot([0, th[-1]], [0, res["M_max"] / 1e6], "b--", lw=1.3,
           label="Secant stiffness S_j = S_j,ini/2")
ax[1].axhline(res["M_max"] / 1e6, color="grey", ls=":", label="M = P × a (max load)")
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
    "K (N/mm; K4 in N/rad)": round(c["K"], 3),
    "1/K": c["1/K"],
} for c in res["components"]])
st.dataframe(comp_df, hide_index=True, width="stretch")

# ---------------- step by step ----------------
st.subheader("Step-by-step")
terms = " + ".join(f"1/{c['K']:,.2f}" for c in res["components"])
st.markdown(f"""
1. **Max deflection** (P = max load = {res['P_max'] / 1000:g} kN):
   δ_max = [P·a²·(3l − a)] / (6·E·I) =
   {res['P_max']:,.0f} × {a:g}² × (3 × {BEAM_LENGTH:g} − {a:g}) / (6 × {E:,.0f} × {inp.I_b:g})
   = **{res['delta_max']:.4f} mm**
2. **Virtual test:** the load rises from 0 in {R['inc']} kN steps and the D1 piston
   reading grows with it. The test stops at the max load
   **P = {res['P_stop']:,.2f} N**, where D1 = **{rec['D1'][-1]:.4f} mm**
3. **Moment** M = P × a = {res['P_stop']:,.2f} × {a:g} = {res['M_max']:,.0f} N·mm =
   **{res['M_max'] / 1e6:.4f} kN·m**
4. **K4 = F / θ_available** = {inp.F_kN:g} kN / {inp.theta_avail:g} rad =
   **{res['K4_kN_rad']:,.4f} kN/rad** (θ_available in radians, not converted to mm)
5. **1/K1 + 1/K2 + 1/K3 + 1/K4 + 1/K5 + 1/K6** = {terms} = **{res['sum_inv_K']:.6g}**
   (K4 used as {res['K4_kN_rad'] * 1000:,.1f} N/rad)
6. **Initial stiffness** S_j,ini = E × h² / (1/K1 + … + 1/K6) =
   {E:,.0f} × {res['h']:g}² / {res['sum_inv_K']:.6g} = {res['S_j_ini']:,.4g}
   → **{res['S_j_ini'] / 1e6:,.3f} kN·m/rad**
7. **Secant stiffness** S_j = S_j,ini / 2 = **{res['S_j'] / 1e6:,.3f} kN·m/rad**
8. **Check** 0.5·E·I_b / L_b = 0.5 × {E:,.0f} × {inp.I_b:g} / {inp.L_b:g} =
   {res['check_limit'] / 1e6:,.3f} kN·m/rad → **{'satisfied' if res['check_ok'] else 'not satisfied'}**
""")

with st.expander("How the curves are built"):
    st.markdown(f"""
* Moment at the connector at every step: M = P × {a:g} mm.
* Moment–rotation: slope **S_j,ini** up to ⅔·M (EN 1993-1-8 elastic limit), then
  straight to the stop point so that the secant there is **S_j = S_j,ini / 2**.
* Sensors: D(x) = P·x²·(3a − x)/(6·E·I_b) + x·tan θ at D1 = {a:g}, D2 = {X_D2:g} and
  D3 = {X_D3:g} mm.
""")

# ---------------- CSVs ----------------
st.subheader("📡 Sensor Data")
sensor_df = pd.DataFrame({
    "Load (kN)": np.round(P_kN, 4),
    "Moment (kN·m)": np.round(M_kNm, 6),
    "D1 piston (mm)": np.round(rec["D1"], 4),
    "D2 (mm)": np.round(rec["D2"], 4),
    "D3 (mm)": np.round(rec["D3"], 4),
})
with st.expander("🔍 View sensor data", expanded=False):
    st.dataframe(sensor_df, hide_index=True, width="stretch", height=320)

summary = pd.concat([
    pd.DataFrame([
        {"Component": "Client", "Working": R["client"]},
        {"Component": "Upright / Beam / Connector", "Working": " · ".join(R["names"])},
        {"Component": "Steel", "Working": R["steel"]},
    ]),
    comp_df,
    pd.DataFrame([
        {"Component": "Max load P (kN)", "Working": f"{res['P_max'] / 1000:g}"},
        {"Component": "Max deflection δ_max (mm)", "Working": f"{res['delta_max']:.4f}"},
        {"Component": "D1 at max load (mm)", "Working": f"{rec['D1'][-1]:.4f}"},
        {"Component": "Moment M = P × a (kN·m)", "Working": f"{res['M_max'] / 1e6:.4f}"},
        {"Component": "K4 = F / θ_available (kN/rad)", "Working": f"{res['K4_kN_rad']:.4f}"},
        {"Component": "1/K1 + … + 1/K6", "1/K": res["sum_inv_K"]},
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
