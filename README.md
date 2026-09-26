# Virtual SPM — Beam-End Hook Connector Stiffness Test

A software-only replica of the cantilever beam-end-connector test rig used for
steel storage racking. You enter the beam, upright and hook-connector data. The
virtual test applies load from 0 kN in small steps until the maximum deflection
is reached. It records the D1/D2/D3 sensor readings and produces three graphs,
a component table and a CSV in the machine's format.

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
  ┌──────────┴──────────────────────────────┴────────────┴──┐╟ upright (800 mm)
  └─────────────────────── beam (500 mm) ────────────────────┘╟ ← hook connector (3/4/5 lips)
```
* The load is applied downward, so the top lips pull out and the connector's bottom edge bears on the upright.
* Moment at the connector: `M = P · a`
* Rotation: `θ = (D3 − D2) / (x3 − x2)`. A corrected value also removes the beam's own bending between D2 and D3.

## Hook connector geometry (fixed product data)
| Lips | Height h_c | Lip centres from top (mm) |
|---|---|---|
| 5 | 245 | 25.1, 75.1, 125.1, 175.1, 225.1 |
| 4 | 195 | 25.1 … 175.1 |
| 3 | 145 | 25.1 … 125.1 |

* Width 44 mm, pitch 50 mm, t_p = 4 mm.
* Hole edge 10.3 mm from the top; bottom end distance 34.7 mm.
* The engaged lip height is inferred as 2·(25.1 − 10.3) = 29.6 mm.

## Inputs
* **Material:** steel with E = 210000 N/mm², ν = 0.3, G = 80769 N/mm².
* **Required (no defaults):**
  * fy and fu
  * beam section
  * upright section (including thickness t_u)
  * maximum deflection
* **Component effective lengths and widths:** estimates, to be calibrated against a physical test.

## Algorithm (handwritten component method, C1–C6)

**Step 1 — Section properties**
* Beam: `I_b` and `W_pl`.
* Upright: `I_u`.

**Step 2 — Component stiffness K (handwritten formulae) and resistance F_Rd**

| Component | Stiffness K | Resistance F_Rd |
|---|---|---|
| C1 Beam deformation | `3 E I_b / L³`, L = 400 mm | `fy W_pl / a` |
| C2 Hook bending | `3 E I_h / l_h³`, `I_h = b_h t_h³ / 12` | `fy b_h t_h² / (4 l_h)` |
| C3 Hook shear | `G A_h / L_h`, `G = E / 2(1+ν)` | `fy A_h / √3` |
| C4 Hook–upright bearing | `E b_bearing t_u / L_bearing` | `2.5 fu b_bearing t_u / γ_M2` |
| C5 Upright local deformation | `E b_u t_u³ / (4 L_u³)` | `fy b_u t_u² / (4 L_u)` |
| C6 Lip deformation | `E b_l t_l³ / (4 L_l³)` | `fy b_l t_l² / (4 L_l)` |

The resistance formulae are not in the handwritten notes. They are plastic capacities of the same idealised parts.

**Step 3 — Each lip: C2 to C6 in series**
* Row stiffness: `k_eff = 1 / (1/K2 + 1/K3 + 1/K4 + 1/K5 + 1/K6)`
* Row resistance: `F_Rd,row = min(F2 … F6)`. The weakest component is reported as the governing one.

**Step 4 — Lips assembled about the connector bottom edge**
* Lever arm of each lip: `z = h_c − y`
* Initial rotational stiffness: `S_j,ini = Σ k_eff z²`
* Moment resistance: `M_j,Rd = Σ F_Rd,row z`

**Step 5 — Non-linear M-θ**
* Each lip follows the EN 1993-1-8 curve: `μ = (1.5 F / F_Rd)^ψ` above `2/3 F_Rd`.
* It then hardens up to `F_u = F_Rd · fu / fy`.

**Step 6 — Virtual test**
1. Start at P = 0 kN.
2. At each step, add 0.01 or 0.02 kN.
3. `M = P a`, and `θ` is obtained from the M-θ curve.
4. Deflection along the beam: `δ(x) = θ x + P x² (3a − x) / (6 E I_b)`.
5. Sensor readings: `D1 = δ(400)`, `D2 = δ(40)`, `D3 = δ(140)`.
6. The test stops when the chosen sensor reaches the maximum deflection; the last step is bisected so the reading lands exactly on the limit.
7. If full capacity is reached first, the load is held while the deflection grows to the limit.

**Step 7 — Outputs**
* **Component table:** stiffness, resistance, force, deformation δ and whether it yielded, for each of C1 to C6 (as in the handwritten table).
* **Stiffness and strength values:** S_j,ini, M_j,Rd, the equal-area stiffness k_ti, and `M_Rd = η M_max / γ_M`.
* **Checks:**
  * semi-rigid when `0.5 E I_b / L_b < S_j,ini < k_b E I_b / L_b`
  * rotation capacity `φ = t_p / h_e`

## Optional additional effects (off by default)
These are not part of the handwritten C1–C6 method. They can be switched on in sidebar section 8:
* connector looseness
* global bending of the upright
* piston / load-cell compliance

## Output CSV (machine format)
`Load 1 kN, Dial 1 mm, Dial 2 mm, Dial 3 mm, Time Sec.`
* Starts from 0 kN.
* Dials are rounded to 0.01 mm.
* A detailed CSV adds moment, rotations and the force in each lip.
