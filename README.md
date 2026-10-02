# Virtual SPM — Component-Method Beam Stiffness Tester

A software-only tool for the beam-end hook-connector joint used in steel storage
racking: **upright + beam + hook connector**. It follows the COP-style component
analysis. Each component's stiffness is calculated from its own formula, and the
components are then assembled into the joint stiffness.

The app has two pages, chosen in the sidebar:

| Page | What it does |
|---|---|
| **📐 CBFEM Virtual Test** (default) | Finds the max deflection, the load F when it is reached, K4 = F / t_p, the **initial stiffness S_j,ini** and **secant stiffness S_j**, and generates the curves and CSV. 3-lip hook connector; all dimensions are entered by the user. |
| **🧪 Earlier model** | The previous virtual test model, kept for reference. |

## Install / Run
```bash
pip install -r requirements.txt
python -m streamlit run app.py   # opens http://localhost:8501
python -m pytest -q tests        # checks (optional)
```

## Files
| File | Purpose |
|---|---|
| `app.py` | Entry point: page navigation |
| `stiffness_page.py`, `cbfem.py` | CBFEM Virtual Test page and its engine |
| `virtual_test_page.py`, `physics_engine.py`, `catalog.py` | Earlier model page, its engine, and the list sections plus IS 2062 tables |
| `assets/` | Section drawings shown on the earlier-model cards |

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

# Earlier model page

## Interface flow
1. **Client name.**
2. **Sections:** choose "Select from list" or "Customize" for three cards:
   * Upright: D, W, B, T
   * Beam: H, W, T, type
   * Hook connector: no. of lips, H, D, W, T
3. **Material, IS 2062 : 2011:** pick the grade and quality.
   * The mechanical and chemical property tables are shown.
   * fy comes from the thickness band of the thickest part; fu = Rm.
   * E = 210000, G = 80769 N/mm², ν = 0.3.
4. **Component stiffness inputs.** Each card shows its K live.
5. **Load schedule:** an increment of 0.01 or 0.02 kN, and the maximum deflection → **Run Virtual Test**.

## Components (handwritten formulae)
| | Component | Inputs | Stiffness | Resistance |
|---|---|---|---|---|
| C1 | Beam local deformation | I_b | `K1 = 3EI_b/L³`, L = 400 | `fy·W_pl,b / L` |
| C2 | Hook bending | I_h, l_h | `K2 = 3EI_h/l_h³` | `fy·(3I_h/t)/l_h` |
| C3 | Hook shear | A_h, L_h | `K3 = G·A_h/L_h` | `fy·A_h/√3` |
| C4 | Hook–upright bearing | F, δ_bearing | `K4 = F/δ_bearing` | `F` |
| C5 | Upright local deformation | L_u, I_u, b_u, t_u | `K5 = 3EI_u/L_u³` | `fy·b_u·t_u²/(4L_u)` |
| C6 | Upright lip deformation | b_l, t_l, L_l | `K6 = E·b_l·t_l³/(4L_l³)` | `fy·b_l·t_l²/(4L_l)` |

The resistances are not in the handwritten notes. They are the plastic capacities of the same parts, using the same inputs.

## Assembly (EN 1993-1-8, as in COP)
* **Per lip:** C2 to C6 act in series.
  * Stiffness: `k_lip = 1/(1/K2+1/K3+1/K4+1/K5+1/K6)`
  * Resistance: `F_lip = min(F2…F6)`
* **Lever arms:** the load is downward, so the top lips pull out and the connector bottom bears on the upright. Each lip's lever arm is measured to the connector bottom: `z = H − (25.1 + 50·i)`.
* **The four outputs:**

  | Output | Formula |
  |---|---|
  | Rotational stiffness, elastic | `S_j,ini = Σ k_lip z²` |
  | Rotational stiffness, plastic | `S_j = S_j,ini / 2` (EN 1993-1-8 §5.1.2) |
  | Moment resistance, plastic | `M_j,Rd = Σ F_lip z` (capped by the beam's plastic moment) |
  | Moment resistance, elastic | `M_j,el = 2/3 M_j,Rd` |

## Virtual test
* **Rig:** beam 500 mm; D1 piston at 400 mm, D2 at 40 mm, D3 at 140 mm from the upright face.
* **Loading:** the load starts at 0 kN and rises by the increment each step. At each step, `M = P·400`.
* **Rotation from moment (`θ`):**
  * `θ = M/S_j,ini` up to `M_j,el`
  * then `θ = θ_el + (M − M_j,el)/S_j` up to `M_j,Rd`
* **Sensor readings:** `D(x) = θ·x + P·x²(3·400 − x)/(6·E·I_b)`.
* **Stop condition:** the test stops when D1 reaches the maximum deflection. If `M_j,Rd` is reached first, the load is held while the deflection grows to the limit.

## Outputs
* The four stiffness and resistance values.
* Graphs: Load vs Displacement (D1, D2, D3), Moment vs Rotation, Load vs Step.
* Component table: stiffness, resistance and deformation for C1–C6.
* **Sensor CSV:** `Load (kN), D1 piston (mm), D2 (mm), D3 (mm)`.
* **Results summary CSV.**
