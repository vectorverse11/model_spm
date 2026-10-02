# Virtual SPM — Component-Method Beam Stiffness Tester

A software-only tool for the beam-end hook-connector joint used in steel storage
racking: **upright + beam + hook connector**. It follows the COP-style component
analysis. Each component's stiffness is calculated from its own formula, and the
components are then assembled into the joint stiffness.

The app is the **CBFEM Virtual Test**. It finds the max deflection, the load F
at which it is reached, K4 = F / t_p, the **initial stiffness S_j,ini** and the
**secant stiffness S_j**, and it generates the curves and CSV. It covers the
3-lip hook connector, and all dimensions are entered by the user. F and the max
deflection are **not** inputs: the test stops at the max deflection.

## Install / Run
```bash
pip install -r requirements.txt
python -m streamlit run app.py   # opens http://localhost:8501
python -m pytest -q tests        # checks (optional)
```

## Files
| File | Purpose |
|---|---|
| `app.py` | Entry point |
| `stiffness_page.py` | CBFEM Virtual Test page (inputs, results, curves, CSV) |
| `cbfem.py` | Formulae and the virtual test engine |
| `tests/test_cbfem.py` | Checks against hand calculations |
| `assets/` | Section drawings (upright, beam, connector) |

## CBFEM Virtual Test
Fixed values: E = 210000 N/mm², G = 80769 N/mm², ν = 0.3.

**Inputs (from the user):**
* Geometry: H (total connector height, also the lever arm h), H_t, beam depth, t_p
* Component properties: I_b, L_b, I_h, L_h, A_h, I_u, L_u, b_l, t_l, L_l
* Load increment: 0.01 or 0.02 kN

**Calculated by the virtual machine (not inputs):** the max deflection, the load F and K4.

**1 – Max deflection (stop condition)**
```
H_b             = H − (H_t + beam depth)
θ_available     = tan⁻¹(t_p / H_b)
D1 max          = 400 · tan θ_available
δ_bearing       = φ_avail × H_b = t_p
```

**2 – Component stiffness (N/mm)**
| | Component | Formula |
|---|---|---|
| C1 | Beam local deformation | `K1 = 3·E·I_b / L_b³` |
| C2 | Hook bending | `K2 = 3·E·I_h / L_h³` |
| C3 | Hook shear | `K3 = G·A_h / L_h` |
| C4 | Hook–upright bearing | `K4 = F / δ_bearing = F / t_p` (F from the test) |
| C5 | Upright local deformation | `K5 = 3·E·I_u / L_u³` |
| C6 | Upright lip deformation | `K6 = E·b_l·t_l³ / (4·L_l³)` |

**3 – Joint stiffness (all six components, EN 1993-1-8 §6.3.1)**
```
S_j,ini = E·h² / Σ(1/k_i),   k_i = K_i / E      ( = h² / Σ(1/K_i) )
S_j     = S_j,ini / 2
Check:    S_j,ini > 0.5·E·I_b / L_b
```

**4 – Virtual test**
* The load rises from 0 kN in steps; M = P·400.
* Up to ⅔·M_max the M–θ slope is S_j,ini. The curve then runs straight to the stop point (θ_available, M_max), so the secant from the origin to that point is S_j = S_j,ini / 2.
* Sensor readings: D(x) = x·tan θ at D1 = 400 mm, D2 = 40 mm and D3 = 140 mm.
* The test stops when θ reaches θ_available. The load at that moment is **F**, and K4 = F / t_p.

**How F is found.** K4 needs F, and F depends on K4, so the two are solved together:
```
θ_available = 2·F·a·(R + t_p/F) / h²   →   F = (θ_available·h²/(2a) − t_p) / R
```
Here R = Σ 1/K_i over every component except K4. The page also shows the same answer as a loop: run the test, note F, compute K4 = F / t_p, run again, and repeat until F stops changing.

**Outputs:**
* θ_available, D1 max, F, K4, S_j,ini, S_j and the check
* Graphs: Load vs Displacement, Moment vs Rotation (with the S_j,ini and S_j lines), Load vs Step
* Step-by-step working
* Sensor CSV (Load, D1, D2, D3) and a results CSV
