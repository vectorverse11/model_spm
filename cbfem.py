"""
CBFEM Virtual Test — hook-connector joint
=========================================

Component-based method for the assembly UPRIGHT + BEAM + HOOK CONNECTOR
(any hook connector — 3, 4 or 5 lips). Every dimension, and the max load P,
is entered by the user.

Fixed values (steel): E = 210000 N/mm^2, G = 80769 N/mm^2, nu = 0.3
Rig: a = 400 mm (load point / D1 piston), l = 500 mm (beam length),
     sensors D2 = 40 mm, D3 = 140 mm from the upright face.

1. Test stop and max deflection
   The load rises from 0 kN in steps of the user-entered increment and the test
   stops when the load reaches the MAX load P (user input).
       delta_max = P a^2 (3 l - a) / (6 E I_b)     beam deflection at the max load

2. Component stiffnesses (all in N/mm)
       K1 = 3 E I_b / L_b^3        beam local deformation
       K2 = 3 E I_h / L_h^3        hook bending
       K3 = G A_h / L_h            hook shear
       K4 = F / (theta_available * H_b)   hook-upright bearing, N/mm
            F (kN) and theta_available (rad) are entered by the user;
            the bearing deflection is delta = theta_available * H_b (mm),
            H_b = H - (H_t + beam depth).
       K5 = 3 E I_u / L_u^3        upright local deformation
       K6 = E b_l t_l^3 / (4 L_l^3) upright lip deformation

3. Joint stiffness (as given in the CBFEM formula sheet)
       S_j,ini = E h^2 / (1/K1 + 1/K2 + 1/K3 + 1/K4 + 1/K5 + 1/K6)
       S_j     = S_j,ini / 2          secant stiffness
       h = total hook-connector height
       Check:  S_j,ini > 0.5 E I_b / L_b

4. Curves (M = P a)
       M-theta: slope S_j,ini up to 2/3 M_max (EN 1993-1-8 6.3.1(4)), then
       straight to the stop point so that the secant there is S_j = S_j,ini/2.
       Sensors: D(x) = P x^2 (3a - x) / (6 E I_b) + x tan(theta)
       at D1 = 400 mm, D2 = 40 mm, D3 = 140 mm.
"""

from dataclasses import dataclass
from math import tan
from typing import Dict, List

E = 210000.0                    # N/mm^2
NU = 0.3
G = E / (2.0 * (1.0 + NU))      # 80769 N/mm^2
ETA = 2.0                       # S_j = S_j,ini / 2

# Test rig (fixed)
LOAD_ARM = 400.0                # a: D1 piston / load point, mm from upright face
BEAM_LENGTH = 500.0             # l: beam length, mm
X_D2 = 40.0
X_D3 = 140.0


@dataclass
class CBFEMInputs:
    # Geometry
    H: float            # total hook-connector height (= lever arm h), mm
    H_t: float          # connector above the beam top, mm
    beam_depth: float   # beam height/depth, mm
    t_p: float          # connector thickness, mm
    # C1 beam
    I_b: float          # beam moment of inertia (x-axis), mm^4
    L_b: float          # beam length, mm
    # C2 / C3 hook
    I_h: float          # hook-connector moment of inertia, mm^4
    L_h: float          # effective hook bending / deformation length, mm
    A_h: float          # effective hook shear area, mm^2
    # C5 upright
    I_u: float          # upright moment of inertia (x-axis), mm^4
    L_u: float          # effective length of deforming upright portion, mm
    # C6 lip
    b_l: float          # effective lip width, mm
    t_l: float          # lip thickness, mm
    L_l: float          # effective lip length, mm
    # Max deflection
    P_max_kN: float     # max load P used in delta_max, kN (user input)
    # C4 bearing
    F_kN: float         # force F for K4, kN (user input)
    theta_avail: float  # theta_available for K4, rad (user input)


def K4_N_per_mm(inp: "CBFEMInputs") -> float:
    """K4 = F / (theta_available * H_b), N/mm (F entered in kN)."""
    return inp.F_kN * 1000.0 / (inp.theta_avail * H_b(inp))


def deflection(P: float, I_b: float) -> float:
    """delta = P a^2 (3 l - a) / (6 E I_b)   (P in N, result in mm)."""
    a, l = LOAD_ARM, BEAM_LENGTH
    return P * a**2 * (3.0 * l - a) / (6.0 * E * I_b)


def H_b(inp: CBFEMInputs) -> float:
    return inp.H - (inp.H_t + inp.beam_depth)


def components(inp: CBFEMInputs) -> List[Dict]:
    """K1 ... K6, all in N/mm."""
    return [
        {"C": "C1", "Component": "Beam local deformation",
         "Formula": "K1 = 3·E·I_b / L_b³",
         "Working": f"3 × {E:.0f} × {inp.I_b:g} / {inp.L_b:g}³",
         "K": 3.0 * E * inp.I_b / inp.L_b**3},
        {"C": "C2", "Component": "Hook bending",
         "Formula": "K2 = 3·E·I_h / L_h³",
         "Working": f"3 × {E:.0f} × {inp.I_h:g} / {inp.L_h:g}³",
         "K": 3.0 * E * inp.I_h / inp.L_h**3},
        {"C": "C3", "Component": "Hook shear",
         "Formula": "K3 = G·A_h / L_h",
         "Working": f"{G:.0f} × {inp.A_h:g} / {inp.L_h:g}",
         "K": G * inp.A_h / inp.L_h},
        {"C": "C4", "Component": "Hook–upright bearing",
         "Formula": "K4 = F / (θ_available × H_b)",
         "Working": f"{inp.F_kN * 1000:g} / ({inp.theta_avail:g} × {H_b(inp):g})",
         "K": K4_N_per_mm(inp)},
        {"C": "C5", "Component": "Upright local deformation",
         "Formula": "K5 = 3·E·I_u / L_u³",
         "Working": f"3 × {E:.0f} × {inp.I_u:g} / {inp.L_u:g}³",
         "K": 3.0 * E * inp.I_u / inp.L_u**3},
        {"C": "C6", "Component": "Upright lip deformation",
         "Formula": "K6 = E·b_l·t_l³ / (4·L_l³)",
         "Working": f"{E:.0f} × {inp.b_l:g} × {inp.t_l:g}³ / (4 × {inp.L_l:g}³)",
         "K": E * inp.b_l * inp.t_l**3 / (4.0 * inp.L_l**3)},
    ]


def theta_of_M(M: float, S_ini: float, M_max: float) -> float:
    """S_j,ini up to 2/3 M_max, then straight to the stop point where the
    secant stiffness is S_j = S_j,ini / 2."""
    M_el = 2.0 / 3.0 * M_max
    if M <= M_el:
        return M / S_ini
    th_el = M_el / S_ini
    th_max = ETA * M_max / S_ini
    return th_el + (M - M_el) * (th_max - th_el) / (M_max - M_el)


def D_at(x: float, P: float, theta: float, I_b: float) -> float:
    """Sensor reading at x: beam bending under P (load at a) + connection rotation."""
    a = LOAD_ARM
    return P * x**2 * (3.0 * a - x) / (6.0 * E * I_b) + x * tan(theta)


def run(inp: CBFEMInputs, increment_kN: float) -> Dict:
    hb = H_b(inp)
    if hb <= 0:
        raise ValueError(
            f"H_b = H − (H_t + beam depth) = {inp.H:g} − ({inp.H_t:g} + "
            f"{inp.beam_depth:g}) = {hb:g} mm must be greater than 0.")
    if inp.F_kN <= 0 or inp.theta_avail <= 0:
        raise ValueError("F and θ_available for K4 must be greater than 0.")
    a, h, I_b = LOAD_ARM, inp.H, inp.I_b

    # ---- 1. max deflection from the MAX load P (not the step load) ----
    P_max = inp.P_max_kN * 1000.0                     # N
    d_max = deflection(P_max, I_b)                    # mm

    # ---- 2. components and joint stiffness (as in the formula sheet) ----
    comps = components(inp)
    for c in comps:
        c["1/K"] = 1.0 / c["K"]
    sum_inv_K = sum(c["1/K"] for c in comps)
    K_total = 1.0 / sum_inv_K
    S_ini = E * h**2 / sum_inv_K
    S_j = S_ini / ETA
    limit = 0.5 * E * I_b / inp.L_b

    # ---- 3. the test stops at the max load ----
    F = P_max                                         # P_stop

    # ---- 4. virtual test: load steps from 0 up to the max load ----
    M_max = F * a
    inc = increment_kN * 1000.0
    if inc <= 0 or F / inc > 200_000:
        raise ValueError(f"Load increment {increment_kN:g} kN gives too many steps "
                         f"(stop load {F / 1000:.3f} kN) — use a larger increment.")

    def state(P):
        th = theta_of_M(P * a, S_ini, M_max)
        return {"P": P, "M": P * a, "theta": th,
                "D1": D_at(a, P, th, I_b), "D2": D_at(X_D2, P, th, I_b),
                "D3": D_at(X_D3, P, th, I_b)}

    rows: List[Dict] = []
    i = 0
    while i * inc < F - 1e-9:                         # 0, inc, 2·inc, … below the max load
        rows.append(state(i * inc))
        i += 1
    rows.append(state(F))                             # stop: P = max load

    rec = {k: [r[k] for r in rows] for k in ("P", "M", "theta", "D1", "D2", "D3")}
    rec["step"] = list(range(len(rows)))

    return {
        "components": comps,
        "H_b": hb,
        "theta_available": inp.theta_avail,
        "F_K4_kN": inp.F_kN,
        "P_max": P_max,
        "delta_max": d_max,
        "P_stop": F,                                  # N, = max load (test stop)
        "K4": K4_N_per_mm(inp),                       # N/mm
        "delta_bearing": inp.theta_avail * hb,        # mm
        "h": h,
        "sum_inv_K": sum_inv_K,
        "K_total": K_total,
        "S_j_ini": S_ini,
        "S_j": S_j,
        "M_max": M_max,                               # N mm, moment at the stop: P_stop * a
        "M_el": 2.0 / 3.0 * M_max,
        "check_limit": limit,
        "check_ok": S_ini > limit,
        "record": rec,
        "steps": len(rows),
    }
