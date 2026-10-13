"""
Stub Column Compression Test — virtual (EN 15512 Annex A.2.1) — Streamlit page
==============================================================================
Effective Width Method (EN 1993-1-3 / 1-5) for local buckling and perforations,
EN 1993-1-1 / 1-3 buckling curves for the stub. All dimensions, f_y and test
settings are entered by the user.  Page of the app — run with:  streamlit run app.py
"""

import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
import streamlit as st

import catalog
from stub import E, G, NU, ALPHA_B, StubInputs, buckling_length_b, run

st.title("🧱 Stub Column Compression Test — Virtual")
st.caption("EN 15512 Annex A.2.1 · Effective Width Method (EN 1993-1-3 / EN 1993-1-5) · "
           "load in kN · lipped-channel upright with perforations")

missing = []


def num(label, key, fmt="%.2f", help=None, allow_zero=False):
    """Required input: empty until the user enters a value (> 0, or ≥ 0 if allow_zero)."""
    v = st.number_input(label, min_value=0.0, value=None, key=key, format=fmt,
                        placeholder="0.0", help=help)
    if v is None or (v <= 0 and not allow_zero):
        missing.append(label)
        return None
    return v


def calc(text):
    st.markdown(text)


client = st.text_input("**Client Name**", placeholder="Enter client name", key="stub_client")

# ============================================================
# 1. INPUTS
# ============================================================

c1, c2, c3 = st.columns(3)
with c1.container(border=True):
    st.markdown("**Dimensions of Specimen**")
    W = num("Width W — web (mm)", "s_W")
    D = num("Depth D — flange (mm)", "s_D")
    t = num("Thickness t (mm)", "s_t")
    lip = num("Lip length (mm) — 0 if no lip", "s_lip", allow_zero=True)
    c = num("Length c — cold-formed section (mm)", "s_c")

with c2.container(border=True):
    st.markdown("**Perforations**")
    pitch = num("Perforation pitch (mm)", "s_pitch")
    n_web = num("Holes across the web in one row", "s_nweb", fmt="%.0f", allow_zero=True)
    d_web = num("Width of one web hole (mm)", "s_dweb", allow_zero=True)
    n_fl = num("Holes across each flange in one row", "s_nfl", fmt="%.0f", allow_zero=True)
    d_fl = num("Width of one flange hole (mm)", "s_dfl", allow_zero=True)

with c3.container(border=True):
    pc = st.columns(2)
    with pc[0]:
        st.markdown("**Cap Plate (a)**")
        cap_L = num("Cap length (mm)", "s_capL")
        cap_W = num("Cap width (mm)", "s_capW")
        cap_t = num("Cap thickness (mm)", "s_capt")
    with pc[1]:
        st.markdown("**Base Plate (a)**")
        base_L = num("Base length (mm)", "s_baseL")
        base_W = num("Base width (mm)", "s_baseW")
        base_t = num("Base thickness (mm)", "s_baset")
    if c and cap_t and base_t:
        st.markdown(f"Buckling length **b** = c + 2 × (cap t + base t) = {c:g} + 2 × "
                    f"({cap_t:g} + {base_t:g}) = **{c + 2 * (cap_t + base_t):g} mm**")

m1, m2 = st.columns(2)
with m1.container(border=True):
    st.markdown("**Material**")
    grade = st.selectbox("IS 2062 grade (reference)", list(catalog.IS2062_MECHANICAL),
                         key="s_grade")
    ref = next(iter(catalog.IS2062_MECHANICAL[grade].values()))
    st.caption(f"IS 2062 {grade}: ReH = {ref['ReH <20']} MPa (< 20 mm), Rm = {ref['Rm']} MPa. "
               "Enter the yield stress to use below.")
    fy = num("Yield stress f_y (N/mm²)", "s_fy")
    gamma = num("γ_M0", "s_gamma", fmt="%.2f")
    st.caption(f"Fixed: E = {E:,.0f} N/mm² · G = {G:,.0f} N/mm² · ν = {NU}")

with m2.container(border=True):
    st.markdown("**Test**")
    alt = st.radio("Test arrangement / method", [1, 2, 3], key="s_alt",
                   format_func=lambda a: {1: "Alternative 1 — ball bearings",
                                          2: "Alternative 2 — clamped platen",
                                          3: "Alternative 3 — CUFSM + DSM (finite strip + "
                                             "Direct Strength Method)"}[a])
    st.caption("Alt 1: flexural buckling length = b, torsional = c/2; load position between "
               "the gross and net centroid, adjusted for the maximum failure load.  \n"
               "Alt 2: flexural and torsional buckling lengths = c (full length); concentric load.  \n"
               "Alt 3: finite strip signature curve gives the local (and distortional) buckling "
               "stress; Direct Strength Method (AISI S100, with holes) gives the strength; "
               "global lengths = c; concentric load.")
    dist = False
    if alt == 3:
        dist = st.checkbox("Include distortional buckling in the strength (DSM P_nd)",
                           key="s_dist",
                           help="EN 15512 says the stub column test is not used to observe "
                                "distortional buckling. Tick to let DSM P_nd govern if lower.")
    least = num("Dial gauge least count (mm/div)", "s_least", fmt="%.4f")
    inc = num("Load increment per step (kN)", "s_inc", fmt="%.3f")

go = st.button("▶ Run Stub Column Test", type="primary")
if go:
    if missing:
        st.session_state.pop("stub", None)
        st.warning("Enter all inputs first:\n\n" + "\n".join(f"- {m}" for m in missing))
    else:
        inp = StubInputs(W=W, D=D, t=t, lip=lip, pitch=pitch, n_web=int(n_web), d_web=d_web,
                         n_fl=int(n_fl), d_fl=d_fl, c=c, cap_L=cap_L, cap_W=cap_W, cap_t=cap_t,
                         base_L=base_L, base_W=base_W, base_t=base_t, fy=fy, gamma_M0=gamma,
                         alternative=alt, least_count=least, distortional=dist)
        try:
            with st.spinner("Running the virtual test" +
                            (" (finite strip analysis)…" if alt == 3 else "…")):
                res = run(inp, inc)
            st.session_state["stub"] = {"res": res, "inp": inp, "inc": inc,
                                        "client": client, "grade": grade}
        except ValueError as exc:
            st.session_state.pop("stub", None)
            st.error(str(exc))

if "stub" not in st.session_state:
    st.stop()

S = st.session_state["stub"]
r, inp = S["res"], S["inp"]
g, eff, cr = r["gross"], r["eff"], r["cr"]
rows = r["rows"]
N_kN = np.array([x["N"] for x in rows]) / 1000
dial = np.array([x["dial"] for x in rows])

# ============================================================
# 2. RESULTS
# ============================================================

st.header(f"📊 Results{' — ' + S['client'] if S['client'] else ''}")
st.success(f"⏹ The specimen buckled and accepted no more load at **{r['N_u'] / 1000:.2f} kN** "
           f"(failure load) after {len(rows)} readings · dial = **{dial[-1]:.1f} div** "
           f"({rows[-1]['delta']:.4f} mm shortening).")

k = st.columns(4)
k[0].metric("Failure load R_k", f"{r['R_k'] / 1000:.2f} kN")
k[0].caption("R_k = max load the virtual specimen carries (see step 5)")
k[1].metric("Effective area A_eff = R_k / f_y", f"{r['A_eff_test']:.2f} mm²")
k[1].caption(f"A_eff = {r['R_k']:,.0f} / {inp.fy:g} = **{r['R_k'] / inp.fy:.2f} mm²**"
             + ("" if r["lambda_test"] <= 0.2 else
                f" → λ̄ = {r['lambda_test']:.3f} > 0.2, adjusted so χ·A_eff·f_y = R_k: "
                f"**{r['A_eff_test']:.2f} mm²**"))
k[2].metric("N_b,Rd = R_k / γ_M0", f"{r['N_b_Rd'] / 1000:.2f} kN")
k[2].caption(f"N_b,Rd = {r['R_k'] / 1000:.2f} / {inp.gamma_M0:g} = **{r['N_b_Rd'] / 1000:.2f} kN**")
k[3].metric("Proof load", f"{r['N_proof'] / 1000:.2f} kN")
k[3].caption("Load at which the first plate starts to buckle locally (end of the linear part)")

# ---------------- graphs ----------------
gcol = st.columns(2)
fig1, ax1 = plt.subplots(figsize=(7, 4.6))
ax1.plot(dial, N_kN, "o-", ms=3, lw=1.8, color="#1f77b4")
ax1.set(xlabel="Dial Reading in div", ylabel="Load in kN", title="Load Vs Dial Reading")
ax1.grid(alpha=0.3)
gcol[0].pyplot(fig1)

d_pr, N_pr, N_u = r["dial_proof"], r["N_proof"] / 1000, r["N_u"] / 1000
sl = r["slopes"]
fig2, ax2 = plt.subplots(figsize=(7, 4.6))
ax2.plot(dial, N_kN, "o-", ms=3, lw=1.8, color="#1f77b4")
xx = np.array([0, dial[-1] * 1.05])
ax2.plot(xx, sl["Slope1"] * xx, "-", lw=1, color="#4a90d9", label=f"Slope1 = {sl['Slope1']:.3f}")
if np.isfinite(sl["Slope2"]):
    ax2.plot(xx, N_pr + sl["Slope2"] * (xx - d_pr), "-", lw=1, color="#7fb3e6",
             label=f"Slope2 = {sl['Slope2']:.3f}")
ax2.plot(xx, sl["Slope3"] * xx, "-", lw=1, color="#2c5d8f", label=f"Slope3 = {sl['Slope3']:.3f}")
ax2.axhline(N_pr, color="grey", lw=0.8)
ax2.text(dial[-1] * 0.02, N_pr, "Proof Load", va="bottom", fontsize=8)
ax2.set(xlabel="Dial Reading in div", ylabel="Load in kN", title="Load Vs Dial Reading — slopes",
        ylim=(0, N_u * 1.1), xlim=(0, dial[-1] * 1.05))
ax2.legend(fontsize=8, loc="lower right")
ax2.grid(alpha=0.3)
gcol[1].pyplot(fig2)
st.caption(f"Slope (kN/div): **Slope1** = proof load / dial at proof = {N_pr:.2f} / {d_pr:.2f} · "
           f"**Slope2** = (failure − proof) / (dial change) · **Slope3** = failure load / dial at "
           f"failure = {N_u:.2f} / {dial[-1]:.2f}")

# ---------------- step by step ----------------
st.subheader("Step-by-step")
b = r["widths"]
st.markdown("**1 · Specimen checks (EN 15512 A.2.1.2)**")
st.dataframe(pd.DataFrame([{**x, "OK": "✅" if x["OK"] else "❌"} for x in r["checks"]]),
             hide_index=True, width="stretch")

st.markdown("**2 · Section properties (centreline, square corners)**")
calc(f"""
* Flat widths: web b_w = W − t = {inp.W:g} − {inp.t:g} = **{b['web']:g} mm** · flange b_f =
  {'D − t' if inp.lip > 0 else 'D − t/2'} = **{b['flange']:g} mm**""" + (
    f" · lip b_l = d_l − t/2 = **{b['lip']:g} mm**" if inp.lip > 0 else "") + f"""
* Gross area A_g = t × Σb = {inp.t:g} × {sum(x['b'] * x['count'] for x in eff['elements']):g} =
  **{g['A']:.2f} mm²** · centroid from web x_g = **{g['xc']:.3f} mm**
* Net (minimum) area A_net = A_g − holes = {g['A']:.2f} − ({inp.n_web} × {inp.d_web:g} + 2 ×
  {inp.n_fl} × {inp.d_fl:g}) × {inp.t:g} = **{r['A_net']:.2f} mm²** · x_net = **{r['x_net']:.3f} mm**
* I_x = {g['Ix']:,.0f} mm⁴ · I_y = {g['Iy']:,.0f} mm⁴ · J = Σ b t³/3 = {g['J']:,.2f} mm⁴ ·
  I_w = {g['Iw']:,.0f} mm⁶ · shear centre x_0 = {g['xs']:.3f} mm from the centroid ·
  i_0² = {g['i0_sq']:.2f} mm²
""")

dsm = r.get("dsm")
if dsm is None:
    st.markdown("**3 · Effective widths at f_y (EN 1993-1-5 §4.4, uniform compression)**")
    st.caption("λ_p = (b/t) / (28.4·ε·√k_σ), ε = √(235/f_y) · internal: ρ = (λ_p − 0.22)/λ_p² · "
               "outstand: ρ = (λ_p − 0.188)/λ_p² · holes removed only where they overlap the "
               "effective strips")
    st.dataframe(pd.DataFrame([{
        "Element": f"{e['name']} (×{e['count']})", "b (mm)": round(e["b"], 3),
        "Type": "internal" if e["internal"] else "outstand", "k_σ": e["k"],
        "λ_p": round(e["lambda_p"], 4), "ρ": round(e["rho"], 4),
        "holes (mm)": e["hole"], "b_eff (mm)": round(e["b_eff"], 3)} for e in eff["elements"]]),
        hide_index=True, width="stretch")
    calc(f"A_eff = t × Σ b_eff = **{eff['A_eff']:.2f} mm²** · x_eff = **{eff['x_eff']:.3f} mm** · "
         f"W_eff = I_eff / c_max = {eff['I_eff']:,.0f} / {max(eff['x_eff'], b['flange'] - eff['x_eff']):.3f}"
         f" = **{eff['W_eff']:,.1f} mm³** · Q = A_eff / A_g = **{r['Q']:.3f}**")
else:
    st.markdown("**3 · Finite strip analysis (CUFSM method) — signature curve**")
    fig3, ax3 = plt.subplots(figsize=(9, 3.6))
    ax3.semilogx(dsm["lengths"], dsm["sigma"], "-", color="#1f77b4", lw=1.8)
    ax3.plot(dsm["local"]["a"], dsm["local"]["sigma"], "o", color="#d62728",
             label=f"Local: σ_crl = {dsm['local']['sigma']:.1f} N/mm² at {dsm['local']['a']:.0f} mm")
    if dsm["dist"]:
        ax3.plot(dsm["dist"]["a"], dsm["dist"]["sigma"], "s", color="#2ca02c",
                 label=f"Distortional: σ_crd = {dsm['dist']['sigma']:.1f} N/mm² at "
                       f"{dsm['dist']['a']:.0f} mm")
    ax3.axhline(inp.fy, color="grey", lw=0.8, ls=":", label=f"f_y = {inp.fy:g}")
    ax3.set(xlabel="Half-wavelength (mm)", ylabel="Buckling stress σ_cr (N/mm²)",
            ylim=(0, min(max(dsm["sigma"]) * 1.05, 4 * max(inp.fy, dsm["local"]["sigma"]))))
    ax3.grid(alpha=0.3, which="both")
    ax3.legend(fontsize=8)
    st.pyplot(fig3)
    st.caption(f"{dsm['n_strips']} strips, {dsm['n_nodes']} nodes · each strip: linear membrane + "
               "cubic bending shape across, one sine half-wave along · K φ = λ K_g φ at each "
               "half-wavelength · first minimum = local, next minimum = distortional")
    calc(f"P_crl = σ_crl × A_g = {dsm['local']['sigma']:.2f} × {g['A']:.2f} = "
         f"**{dsm['P_crl'] / 1000:.2f} kN**" + (
             f" · P_crd = σ_crd × A_g = {dsm['dist']['sigma']:.2f} × {g['A']:.2f} = "
             f"**{dsm['P_crd'] / 1000:.2f} kN**" if dsm["dist"] else
             " · no distortional minimum on the curve"))

st.markdown("**4 · Buckling of the stub (EN 1993-1-1 §6.3.1, EN 1993-1-3 §6.2.3)**")
calc(f"""
* Buckling lengths (Alternative {inp.alternative}): flexural L_F = **{cr['L_F']:g} mm**,
  torsional L_T = **{cr['L_T']:g} mm** (b = {r['b']:g} mm, c = {inp.c:g} mm)
* N_cr,x = π²·E·I_x / L_F² = **{cr['N_cr_x'] / 1000:,.1f} kN** · N_cr,y = π²·E·I_y / L_F² =
  **{cr['N_cr_y'] / 1000:,.1f} kN**
* N_cr,T = (G·J + π²·E·I_w / L_T²) / i_0² = **{cr['N_cr_T'] / 1000:,.1f} kN** ·
  lowest root of the torsional-flexural equation = **{cr['N_cr_TF'] / 1000:,.1f} kN**
""" + ("" if dsm else f"""* λ̄ = √(A_eff·f_y / N_cr) = √({eff['A_eff']:.2f} × {inp.fy:g} / {cr['N_cr']:,.0f}) =
  **{r['lambda_bar']:.4f}** → χ = **{r['chi']:.4f}** (curve b, α = {ALPHA_B};
  χ = 1 when λ̄ ≤ 0.2)
* N_c = χ·A_eff·f_y = {r['chi']:.4f} × {eff['A_eff']:.2f} × {inp.fy:g} = **{r['N_c'] / 1000:.2f} kN**
"""))

st.markdown("**5 · Failure load**")
if dsm:
    fmt = lambda v: "—" if v is None else f"{v / 1000:,.2f}"
    calc(f"""
* **Global** (P_cre = N_cr above): λ_c = √(P_y / P_cre) = √({dsm['P_y'] / 1000:.2f} /
  {dsm['P_cre'] / 1000:,.1f}) = **{dsm['lam_c']:.4f}** → P_ne = 0.658^(λ_c²)·P_y
  (0.877/λ_c²·P_y if λ_c > 1.5), ≤ P_ynet = A_net·f_y = {dsm['P_ynet'] / 1000:.2f} →
  **P_ne = {dsm['P_ne'] / 1000:.2f} kN**
* **Local**: λ_l = √(P_ne / P_crl) = √({dsm['P_ne'] / 1000:.2f} / {dsm['P_crl'] / 1000:.2f}) =
  **{dsm['lam_l']:.4f}** → P_nl = P_ne if λ_l ≤ 0.776, else
  [1 − 0.15(P_crl/P_ne)^0.4](P_crl/P_ne)^0.4·P_ne, ≤ P_ynet → **P_nl = {dsm['P_nl'] / 1000:.2f} kN**
* **Distortional**: λ_d = √(P_y / P_crd) = {'—' if dsm['lam_d'] is None else f"{dsm['lam_d']:.4f}"}
  → P_nd = **{fmt(dsm['P_nd'])} kN** (net-section form for members with holes)
  {'— **included**' if dsm['distortional_used'] else '— not included (stub test excludes distortional buckling)'}
* **P_n = {'min(P_nl, P_nd)' if dsm['distortional_used'] else 'P_nl'} = {dsm['P_n'] / 1000:.2f} kN**
  (governed by {dsm['governs']} buckling) → N_u = **{r['N_u'] / 1000:.2f} kN**
""")
    st.caption("P_y = A_g·f_y = " f"{dsm['P_y'] / 1000:.2f} kN · DSM: AISI S100 (Direct Strength "
               "Method) · Q = R_k / (A_g·f_y)")
elif inp.alternative == 1:
    calc(f"""
* Load position swept from the gross centroid (x = {r['x_gross']:.3f} mm) to the net centroid
  (x = {r['x_net']:.3f} mm); maximum at x = **{r['x_load']:.3f} mm**
* Eccentricity to the effective centroid e = {r['x_load']:.3f} − {eff['x_eff']:.3f} =
  **{r['e']:.3f} mm**
* N_u = 1 / (1/N_c + |e| / (W_eff·f_y)) = 1 / (1/{r['N_c']:,.0f} + {abs(r['e']):.3f} /
  ({eff['W_eff']:,.1f} × {inp.fy:g})) = **{r['N_u'] / 1000:.2f} kN**
""")
else:
    calc(f"* Concentric load (platen clamped): N_u = N_c = **{r['N_u'] / 1000:.2f} kN**")
if dsm:
    calc(f"* Proof load = 0.776² × σ_crl × A_net (where the DSM local curve starts to drop) = "
         f"**{r['N_proof'] / 1000:.2f} kN**")
else:
    calc(f"* Proof load = σ at first local buckling × A_net = **{r['N_proof'] / 1000:.2f} kN**")

with st.expander("How the load – dial curve is built"):
    st.markdown(f"""
* Load rises from 0 in {S['inc']} kN steps up to the failure load.
* At each load N the edge stress σ = N / A_eff(σ) is found by iteration; A_eff falls once the
  plates buckle locally, so the curve bends over.
* Alternative 3: A_eff(σ) = A_g × DSM local ratio [1 − 0.15(σ_crl/σ)^0.4](σ_crl/σ)^0.4
  (1 below λ = 0.776), capped at A_net.
* Shortening δ = N·c / (E·A_eff(σ)) and dial reading = δ / {inp.least_count:g} mm per div.
""")

# ---------------- table + CSV ----------------
st.subheader("📡 Readings")
table = pd.DataFrame({"Load in kN": np.round(N_kN, 3),
                      "Dial Gauge Reading in div": np.round(dial, 2),
                      "Shortening (mm)": np.round([x["delta"] for x in rows], 5),
                      "A_eff (mm²)": np.round([x["A_eff"] for x in rows], 2)})
with st.expander("🔍 View readings", expanded=True):
    st.dataframe(table, hide_index=True, width="stretch", height=320)

summary = pd.DataFrame([
    {"Item": "Client", "Value": S["client"]},
    {"Item": "Test arrangement", "Value": f"Alternative {inp.alternative}"},
    {"Item": "A_g (mm²)", "Value": f"{g['A']:.2f}"},
    {"Item": "A_net (mm²)", "Value": f"{r['A_net']:.2f}"},
    {"Item": "A_eff at f_y (mm²)", "Value": f"{eff['A_eff']:.2f}"},
    {"Item": "Q = A_eff / A_g", "Value": f"{r['Q']:.4f}"},
    {"Item": "Buckling length b (mm)", "Value": f"{r['b']:g}"},
    {"Item": "λ̄", "Value": f"{r['lambda_bar']:.4f}"},
    {"Item": "χ", "Value": f"{r['chi']:.4f}"},
    {"Item": "Failure load R_k (kN)", "Value": f"{r['R_k'] / 1000:.3f}"},
    {"Item": "A_eff = R_k / f_y (mm²)", "Value": f"{r['A_eff_test']:.2f}"},
    {"Item": "N_b,Rd = R_k / γ_M0 (kN)", "Value": f"{r['N_b_Rd'] / 1000:.3f}"},
    {"Item": "Proof load (kN)", "Value": f"{r['N_proof'] / 1000:.3f}"},
    *[{"Item": k_, "Value": f"{v:.4f}"} for k_, v in r["slopes"].items()],
])
d1, d2 = st.columns(2)
d1.download_button("📥 Download readings (CSV)", table.to_csv(index=False).encode("utf-8"),
                   "stub_column_readings.csv", "text/csv", width="stretch")
d2.download_button("📥 Download results (CSV)", summary.to_csv(index=False).encode("utf-8"),
                   "stub_column_results.csv", "text/csv", width="stretch")
