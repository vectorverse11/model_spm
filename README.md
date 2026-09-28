# Virtual SPM — Component-Method Beam Stiffness Tester

A software-only replica of the beam-end hook-connector test machine for steel
storage racking. It follows the COP-style component analysis. The assembly
**upright + beam + hook connector** is split into components, and each
component's stiffness is calculated from its own formula. The components are
then assembled into the joint's rotational stiffness and moment resistance, and
a virtual cantilever test is run.

## Install / Run
```bash
pip install -r requirements.txt
streamlit run app.py          # opens http://localhost:8501
python -m pytest -q tests     # engine checks (optional)
```

## Files
| File | Purpose |
|---|---|
| `app.py` | Streamlit interface |
| `physics_engine.py` | Component formulae, assembly and the virtual test |
| `catalog.py` | "Select from list" sections and the IS 2062 : 2011 tables — add more entries here |
| `assets/` | Optional drawings shown on the cards: `upright.png`, `beam.png`, `connector.png` |

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
