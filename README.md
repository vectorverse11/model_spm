# Virtual SPM — Component-Method Beam Stiffness Tester

A software-only tool for the beam-end hook-connector joint used in steel storage
racking: **upright + beam + hook connector**. It follows the COP-style component
analysis. Each component's stiffness is calculated from its own formula, and the
components are then assembled into the joint stiffness.

The app is the **CBFEM Virtual Test**. It calculates the max deflection δ_max
from the max load P, then raises the load until the D1 reading reaches δ_max.
It notes that load F, calculates K4 = F / t_p, the **initial stiffness S_j,ini**
and the **secant stiffness S_j**, and generates the curves and CSV. It covers the
3-lip hook connector, and all dimensions are entered by the user.

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
| `app.py` | Entry point |
| `stiffness_page.py` | CBFEM Virtual Test page (inputs, results, curves, CSV) |
| `cbfem.py` | Formulae and the virtual test engine |
| `tests/test_cbfem.py` | Checks against hand calculations |

## CBFEM Virtual Test
Fixed values: E = 210000 N/mm², G = 80769 N/mm², ν = 0.3. Rig: a = 400 mm (load point / D1 piston), l = 500 mm (beam length), D2 = 40 mm, D3 = 140 mm.

**Inputs (from the user):**
* Geometry: H (total connector height, also h), H_t, beam depth, t_p
* Component properties: I_b, L_b, I_h, L_h, A_h, I_u, L_u, b_l, t_l, L_l
* P, the max load (default 3.86 kN, editable). It is used only for δ_max.
* Load increment: 0.01 or 0.02 kN

**Calculated by the virtual machine:** δ_max, the stop load F, K4, S_j,ini and S_j.

**1 – Max deflection (stop condition)**
```
δ_max = [P·a²·(3l − a)] / (6·E·I)      P = max load, a = 400 mm, l = 500 mm, I = I_b
```
The load rises from 0 kN in steps. When the D1 piston reading reaches δ_max, the test stops and that load is noted as **F**.

**2 – Component stiffness (N/mm)**
| | Component | Formula |
|---|---|---|
| C1 | Beam local deformation | `K1 = 3·E·I_b / L_b³` |
| C2 | Hook bending | `K2 = 3·E·I_h / L_h³` |
| C3 | Hook shear | `K3 = G·A_h / L_h` |
| C4 | Hook–upright bearing | `K4 = F / δ_bearing = F / t_p`, with φ_avail = t_p / H_b and δ_bearing = φ_avail × H_b = t_p |
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
* F is the load at which D1 = δ_max. Because K4 = F / t_p changes S_j,ini, F is found so that the two agree.

**Outputs:**
* δ_max, F, K4, S_j,ini, S_j and the check
* Graphs: Load vs Displacement, Moment vs Rotation, Load vs Step
* Step-by-step working
* Sensor CSV (Load, D1, D2, D3) and a results CSV
