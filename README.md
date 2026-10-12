# Virtual SPM — Component-Method Beam Stiffness Tester

A software-only tool for the beam-end hook-connector joint used in steel storage
racking: **upright + beam + hook connector**. It follows the COP-style component
analysis. Each component's stiffness is calculated from its own formula, and the
components are then assembled into the joint stiffness.

The app is the **CBFEM Virtual Test**. It calculates the max deflection δ_max
from the max load P, then raises the load in steps until it reaches the max load P,
where the test stops. It calculates K4 = F / (θ_available × H_b), the **initial stiffness S_j,ini**
and the **secant stiffness S_j**, and generates the curves and CSV. It works for any
hook connector (3, 4 or 5 lips). The sections, component properties and max load are
all entered by the user.

## Install / Run
Requires Python 3.10 or newer.
```bash
python -m pip install -r requirements.txt
python -m streamlit run app.py      # opens http://localhost:8501
```
Optional checks: `python -m pip install pytest`, then `python -m pytest -q tests`.

## Files
| File | Purpose |
|---|---|
| `app.py` | Entry point (two pages: CBFEM Virtual Test, Stub Column Test) |
| `stub_page.py` | Stub Column Test page (inputs, results, graphs, CSV) |
| `stub.py` | Stub column engine: section properties, effective widths, buckling, virtual test |
| `stiffness_page.py` | CBFEM Virtual Test page (inputs, results, curves, CSV) |
| `cbfem.py` | Formulae and the virtual test engine |
| `catalog.py` | "Select from list" sections and the IS 2062 : 2011 tables (add entries here) |
| `assets/` | Section drawings shown on the upright, beam and connector cards |
| `tests/` | Checks against hand calculations and textbook formulas |

## CBFEM Virtual Test
Fixed values: E = 210000 N/mm², G = 80769 N/mm², ν = 0.3. Rig: a = 400 mm (load point / D1 piston), l = 500 mm (beam length), D2 = 40 mm, D3 = 140 mm.

**Inputs (from the user):**
* Client name
* Sections, picked with **Select from list** or entered with **Customize**:
  * Upright: D, W, B, T
  * Beam: H, W, T, type
  * Hook connector: no. of lips, H, D, W, T
* Material: IS 2062 : 2011 grade and quality, with the mechanical and chemical tables shown
* Geometry for CBFEM, all entered by the user: H (= h), t_p, beam depth and H_t
* Component properties: I_b, L_b, I_h, L_h, A_h, I_u, L_u, b_l, t_l, L_l
* **P, the max load (kN)**. The test stops at this load; also used for δ_max.
* **C4:** F (kN) and θ_available (rad) for K4 = F / (θ_available × H_b)
* Load increment per step (kN), entered by the user

**Calculated by the virtual machine:** δ_max, D1 at the max load, the moment M = P × a, K4, S_j,ini and S_j.

**1 – Test stop at the max load, and max deflection**
```
δ_max = [P·a²·(3l − a)] / (6·E·I)      P = max load, a = 400 mm, l = 500 mm, I = I_b
```
The load rises from 0 kN in steps and the test **stops at the max load P**. δ_max is the beam deflection at the max load.

**2 – Component stiffness (all in N/mm)**
| | Component | Formula |
|---|---|---|
| C1 | Beam local deformation | `K1 = 3·E·I_b / L_b³` |
| C2 | Hook bending | `K2 = 3·E·I_h / L_h³` |
| C3 | Hook shear | `K3 = G·A_h / L_h` |
| C4 | Hook–upright bearing | `K4 = F / (θ_available × H_b)` in **N/mm**. F (kN) and θ_available (rad) are entered by the user; the bearing deflection is δ = θ_available × H_b (mm). |
| C5 | Upright local deformation | `K5 = 3·E·I_u / L_u³` |
| C6 | Upright lip deformation | `K6 = E·b_l·t_l³ / (4·L_l³)` |

Here `H_b = H − (H_t + beam depth)`.

**3 – Joint stiffness (as in the CBFEM formula sheet)**
```
S_j,ini = E·h² / (1/K1 + 1/K2 + 1/K3 + 1/K4 + 1/K5 + 1/K6)      h = total hook-connector height
S_j     = S_j,ini / 2
Check:    S_j,ini > 0.5·E·I_b / L_b
```

**4 – Virtual test and curves**
* M = P·a at each step.
* M–θ: the slope is S_j,ini up to ⅔·M_max (EN 1993-1-8). The curve then runs straight to the stop point, so the secant there is S_j.
* Sensors: D(x) = P·x²·(3a − x)/(6·E·I_b) + x·tan θ at D1 = 400 mm, D2 = 40 mm and D3 = 140 mm.
* The test stops when the load reaches the max load P.

**Outputs:**
* δ_max, D1 at the max load, moment M = P × a, K4, S_j,ini, S_j and the check, each with its formula and the numbers used
* Graphs: Load vs Displacement, Moment vs Rotation, Load vs Step
* Step-by-step working
* Sensor CSV (Load, Moment, D1, D2, D3) and a results CSV

## Stub Column Test (EN 15512 Annex A.2.1)
A virtual compression test of a short perforated upright (lipped channel; lip = 0 for a plain
channel). Method: **Effective Width Method** (EN 1993-1-3 / EN 1993-1-5 §4.4) for local
buckling and perforations, with EN 1993-1-1 §6.3.1 / EN 1993-1-3 §6.2.3 for buckling of the stub.

**Inputs (all from the user):**
* Specimen: W, D, t, lip length, length c
* Perforations: pitch, and the number and width of holes across the web and across each flange
* Cap and base plates: length, width and thickness
* f_y and γ_M0
* Test arrangement (Alternative 1 or 2), dial least count (mm/div), load increment (kN)

**Steps:**
1. Specimen checks: c ≥ 3 × greatest flat width, ≥ 5 pitches, pitch 50–70 mm, cap and base plates project ≥ 10 mm per side along the web ((plate length − W)/2), cap plate ≥ 30 mm.
2. Section properties: A_g, A_net, centroids, I, J, I_w and the shear centre (centreline model).
3. Effective widths: λ_p = (b/t)/(28.4·ε·√k_σ), with ρ = (λ_p − 0.22)/λ_p² for internal plates and (λ_p − 0.188)/λ_p² for outstands. Holes are removed where they overlap the effective strips.
4. Buckling: the lengths depend on the arrangement.
   * Alternative 1: L_F = b = c + 2(cap t + base t) and L_T = c/2.
   * Alternative 2: L_F = L_T = c/2.
   * Then λ̄ = √(A_eff·f_y/N_cr) and χ from curve b.
5. Failure load:
   * Alternative 1: N_u = 1/(1/(χ·A_eff·f_y) + |e|/(W_eff·f_y)). The load position is swept between the gross and net centroids for the maximum.
   * Alternative 2: N_u = χ·A_eff·f_y.
6. Load–dial curve: σ = N/A_eff(σ), δ = N·c/(E·A_eff(σ)), and dial = δ / least count. The proof load is the load at the first local buckling.
7. Results: R_k, A_eff = R_k/f_y (adjusted if λ̄ > 0.2), N_b,Rd = R_k/γ_M0, Q = A_eff/A_g, slopes 1–3, a readings table and CSV.
