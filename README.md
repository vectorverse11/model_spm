# Virtual SPM — Beam-End Hook Connector Stiffness Test

A software-only replica of the cantilever beam-end-connector test rig used for
steel storage racking. You enter the beam, upright and hook-connector data, and the
virtual test produces the D1/D2/D3 sensor readings under a monotonic load, the
moment–rotation curve and the design stiffness and strength.

## Install / Run
```bash
pip install -r requirements.txt
streamlit run app.py          # http://localhost:8501
python -m pytest -q tests     # engine checks
```

## Test rig replicated
```
      D1 (piston, x = a = 400)        D3 (x = 140)   D2 (x = 40)
             ↓ P                            ↓            ↓
  ┌──────────┴──────────────────────────────┴────────────┴──┐╟ upright (clamped, 800 mm)
  └─────────────────────── beam stub (500) ──────────────────┘╟ ← hook connector (3/4/5 lips)
```
* Moment at the connector: `M = P · a`
* Measured rotation: `θ = (D3 − D2) / (x3 − x2)`. A corrected value also removes the
  beam's own elastic curvature between the two LVDTs.

## Hook connector geometry (fixed product data)
| Lips | Height h_c | Lip centres from top (mm) |
|---|---|---|
| 5 | 245 | 25.1, 75.1, 125.1, 175.1, 225.1 |
| 4 | 195 | 25.1 … 175.1 |
| 3 | 145 | 25.1 … 125.1 |

Width 44 mm, pitch 50 mm, hole edge 10.3 mm from the top, 34.7 mm bottom end
distance. The engaged lip height is inferred as 2·(25.1 − 10.3) = 29.6 mm.

## Material
The default material is steel with E = 210000 N/mm², ν = 0.3 and G = E/2(1+ν) = 80769 N/mm².
The yield strength fy and ultimate strength fu have **no default** and must be entered before a test runs.

## Algorithm (component method, EN 1993-1-8 adapted to hook rows)
1. **Section properties**
   * Beam: `I_b` and `W_pl` (box, solid, or custom values).
   * Upright: `I_u`, computed as a thin-walled lipped channel × a perforation factor.
2. **Component springs per lip row r**, from the hand-written derivation:
   | | Stiffness | Resistance |
   |---|---|---|
   | C2 hook bending | `3 E I_h / l_h³`, `I_h = b_h t_h³/12` | `fy b_h t_h² /(4 l_h)` |
   | C3 hook shear | `G A_h / L_h`, `G = E/2(1+ν)` | `fy A_h / √3` |
   | C4 bearing | `E b_brg t_u / L_brg` | `2.5 fu b_brg t_u / γ_M2` |
   | C5 upright wall | `E b_u t_u³ /(4 L_u³)` | `fy b_u t_u² /(4 L_u)` |
   | C6 connector lip | `E b_l t_l³ /(4 L_l³)` | `fy b_l t_l² /(4 L_l)` |
3. **Row in series**
   * Stiffness: `k_eff,r = 1/Σ(1/K_i)`
   * Resistance: `F_Rd,r = min F_i,Rd`. The component that gives the minimum is reported as the governing component.
4. **Assembly about the centre of compression** (the bottom of the connector)
   * Lever arm of each lip: `z_r = h_c − y_r`
   * Initial rotational stiffness: `S_j,ini = Σ k_eff,r z_r²`
   * Moment resistance: `M_j,Rd = Σ F_Rd,r z_r`
   * Equivalent values `z_eq` and `k_eq` are also computed.
5. **Row non-linearity** follows EN 1993-1-8 §6.3.1(6):
   * Stiffness ratio `μ = (1.5F/F_Rd)^ψ` for `F > 2/3 F_Rd`.
   * Linear hardening beyond `F_Rd`, up to `F_u = F_Rd · fu/fy`.
   * The test fails when the first row reaches `F_u`.
   * Optional extra limits: the rotation capacity `t_p / h_e`, or the beam's plastic moment `M_pl`.
6. **Load control** at 0.01 or 0.02 kN per step. At each step:
   * `θ = θ_conn(M)` (the inverse of `Σ z_r F_r(z_r θ)`)
   * plus `θ_looseness(M)`
   * plus `θ_upright = M H /(16 E I_u)` (fixed-fixed clamping)
   * Deflection along the beam: `δ(x) = θ x + P x²(3a − x)/(6 E I_b)`
   * Sensor readings: D1 = `δ(a)` plus the load-train compliance; D2 = `δ(x2)`; D3 = `δ(x3)`
7. **Evaluation** (EN 15512 style)
   * `M_Rd = η M_max / γ_M`
   * Equal-area stiffness `k_ti` up to `M_Rd`
   * Secant stiffness from 10 % to 40 % of `M_max`
   * Joint classification per EN 1993-1-8 §5.2.2.5: semi-rigid when `0.5 E I_b / L_b < S_j,ini < k_b E I_b / L_b`
   * Idealised stiffness for global analysis `S_j = S_j,ini / η` (EN 1993-1-8 §5.1.2, η = 2 for end plates)
   * Strength classification (§5.2.3): pinned if `M_j,Rd ≤ 0.25 M_pl,beam`, full-strength if `M_j,Rd ≥ M_pl,beam`, otherwise partial-strength

## Calibration note
The component parameters (l_h, L_h, b_brg, L_brg, b_u, L_u, b_l, L_l) are
effective lengths and widths. They cannot be measured directly. Calibrate them
once against a physical test of the same connector, then use the simulator
predictively.
