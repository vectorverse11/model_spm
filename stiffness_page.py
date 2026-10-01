"""
CBFEM Stiffness Calculator — Initial & Secant Stiffness (Streamlit)
===================================================================
Hook-connector joint (3-lip): upright + beam + hook connector.
All dimensions are entered by the user.

Page "Stiffness Calculator" of the app — run with:  streamlit run app.py
"""

from math import atan, degrees

import pandas as pd
import streamlit as st

from cbfem import E, G, NU, CBFEMInputs, calculate

st.title("🏗️ CBFEM — Initial & Secant Stiffness")
st.caption("Component Based Finite Element Method · Upright + Beam + Hook "
           "Connector · 3-lip hook connector")

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
# GEOMETRY
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
        st.info(f"**H_b** = H − (H_t + beam depth) = {H:g} − ({H_t:g} + {beam_depth:g}) "
                f"= **{hb:g} mm**  ·  **θ_available** = tan⁻¹(t_p / H_b) = "
                f"tan⁻¹({t_p:g}/{hb:g}) = **{degrees(th):.4f}° = {th:.4f} rad**  ·  "
                f"**δ_bearing** = θ_available × H_b = t_p = **{t_p:g} mm**")
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
    F = num("F — max load (N)", "F", fmt="%.1f")
    st.caption("δ_bearing = θ_available × H_b = t_p (from the geometry above).")
    show_k("K4", F / t_p if F and t_p else None)

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
# CALCULATE
# ============================================================

st.divider()
go = st.button("▶ Calculate Initial & Secant Stiffness", type="primary")

if go:
    if missing:
        st.session_state.pop("cbfem", None)
        st.warning("Enter all inputs first:\n\n" + "\n".join(f"- {m}" for m in missing))
    else:
        inp = CBFEMInputs(H=H, H_t=H_t, beam_depth=beam_depth, t_p=t_p,
                          I_b=I_b, L_b=L_b, I_h=I_h, L_h=L_h, A_h=A_h, F=F,
                          I_u=I_u, L_u=L_u, b_l=b_l, t_l=t_l, L_l=L_l)
        try:
            st.session_state["cbfem"] = {"res": calculate(inp), "inp": inp}
        except ValueError as exc:
            st.session_state.pop("cbfem", None)
            st.error(str(exc))

if "cbfem" not in st.session_state:
    st.stop()

R = st.session_state["cbfem"]
res, inp = R["res"], R["inp"]

st.header("📊 Results")
m = st.columns(3)
m[0].metric("Initial stiffness S_j,ini", f"{res['S_j_ini'] / 1e6:,.3f} kN·m/rad")
m[1].metric("Secant stiffness S_j = S_j,ini / 2", f"{res['S_j'] / 1e6:,.3f} kN·m/rad")
m[2].metric("Check: S_j,ini > 0.5·E·I_b / L_b",
            "✅ Satisfied" if res["check_ok"] else "❌ Not satisfied",
            f"limit {res['check_limit'] / 1e6:,.3f} kN·m/rad", delta_color="off")

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

st.subheader("Step-by-step")
terms = " + ".join(f"{c['1/k']:,.3f}" for c in res["components"])
st.markdown(f"""
1. **Stiffness coefficients** (EN 1993-1-8 §6.3.1): k_i = K_i / E, in mm.
2. **Σ(1/k_i)** = {terms} = **{res['sum_inv_k']:,.3f} mm⁻¹**
3. **Lever arm** h = total hook connector height = **{res['h']:g} mm**
4. **Initial stiffness**
   S_j,ini = E·h² / Σ(1/k_i) = {E:,.0f} × {res['h']:g}² / {res['sum_inv_k']:,.3f}
   = **{res['S_j_ini']:,.0f} N·mm/rad = {res['S_j_ini'] / 1e6:,.3f} kN·m/rad**
5. **Secant stiffness**
   S_j = S_j,ini / 2 = **{res['S_j'] / 1e6:,.3f} kN·m/rad**
6. **Check**
   0.5·E·I_b / L_b = 0.5 × {E:,.0f} × {inp.I_b:g} / {inp.L_b:g}
   = {res['check_limit'] / 1e6:,.3f} kN·m/rad → S_j,ini {'>' if res['check_ok'] else '≤'} limit:
   **{'satisfied' if res['check_ok'] else 'not satisfied'}**
""")
st.caption(
    f"Also: H_b = {res['H_b']:g} mm · θ_available = {res['theta_available_deg']:.4f}° "
    f"= {res['theta_available_rad']:.4f} rad · δ_bearing = t_p = {res['delta_bearing']:g} mm. "
    "Because K_i already contains E, E·h²/Σ(1/k_i) with k_i = K_i/E equals h²/Σ(1/K_i).")

summary = pd.concat([
    comp_df,
    pd.DataFrame([
        {"Component": "Σ(1/k)", "1/k (1/mm)": round(res["sum_inv_k"], 3)},
        {"Component": "h (mm)", "Working": f"{res['h']:g}"},
        {"Component": "S_j,ini (kN·m/rad)", "Working": f"{res['S_j_ini'] / 1e6:.4f}"},
        {"Component": "S_j (kN·m/rad)", "Working": f"{res['S_j'] / 1e6:.4f}"},
        {"Component": "Check limit 0.5·E·I_b/L_b (kN·m/rad)",
         "Working": f"{res['check_limit'] / 1e6:.4f}"},
        {"Component": "Check satisfied", "Working": str(res["check_ok"])},
    ]),
])
st.download_button("📥 Download results (CSV)", summary.to_csv(index=False).encode("utf-8"),
                   "cbfem_stiffness_results.csv", "text/csv")
