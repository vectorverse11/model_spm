"""
CBFEM — Initial and Secant Stiffness of the hook-connector joint
================================================================

Component-based method for the assembly UPRIGHT + BEAM + HOOK CONNECTOR
(3-lip hook connector). Every dimension is entered by the user.

Fixed values (steel): E = 210000 N/mm^2, G = 80769 N/mm^2, nu = 0.3

Component stiffnesses (N/mm):
    C1 Beam local deformation      K1 = 3 E I_b / L_b^3
    C2 Hook bending                K2 = 3 E I_h / L_h^3
    C3 Hook shear                  K3 = G A_h / L_h
    C4 Hook-upright bearing        K4 = F / delta_bearing,  delta_bearing = t_p
           (theta_available = t_p / H_b, H_b = H - (H_t + beam depth),
            so delta_bearing = theta_available * H_b = t_p)
    C5 Upright local deformation   K5 = 3 E I_u / L_u^3
    C6 Upright lip deformation     K6 = E b_l t_l^3 / (4 L_l^3)

Joint stiffness (EN 1993-1-8 6.3.1):
    S_j,ini = E h^2 / sum(1/k_i)      h = total hook-connector height
    with k_i = K_i / E the stiffness coefficients in mm (the K_i above
    already contain E), i.e. S_j,ini = h^2 / sum(1/K_i)  [N mm/rad]
    S_j     = S_j,ini / 2             secant stiffness
    Check:  S_j,ini > 0.5 E I_b / L_b
"""

from dataclasses import dataclass
from math import atan, degrees
from typing import Dict, List

E = 210000.0                    # N/mm^2
NU = 0.3
G = E / (2.0 * (1.0 + NU))      # 80769 N/mm^2
ETA = 2.0                       # S_j = S_j,ini / 2


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
    # C4 bearing
    F: float            # max load, N
    # C5 upright
    I_u: float          # upright moment of inertia (x-axis), mm^4
    L_u: float          # effective length of deforming upright portion, mm
    # C6 lip
    b_l: float          # effective lip width, mm
    t_l: float          # lip thickness, mm
    L_l: float          # effective lip length, mm


def H_b(inp: CBFEMInputs) -> float:
    return inp.H - (inp.H_t + inp.beam_depth)


def calculate(inp: CBFEMInputs) -> Dict:
    hb = H_b(inp)
    if hb <= 0:
        raise ValueError(
            f"H_b = H − (H_t + beam depth) = {inp.H:g} − ({inp.H_t:g} + "
            f"{inp.beam_depth:g}) = {hb:g} mm must be greater than 0.")
    theta = atan(inp.t_p / hb)                 # rad
    delta_bearing = inp.t_p                    # = theta_available * H_b

    comps: List[Dict] = [
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
         "Formula": "K4 = F / δ_bearing,  δ_bearing = θ_available·H_b = t_p",
         "Working": f"{inp.F:g} / {delta_bearing:g}",
         "K": inp.F / delta_bearing},
        {"C": "C5", "Component": "Upright local deformation",
         "Formula": "K5 = 3·E·I_u / L_u³",
         "Working": f"3 × {E:.0f} × {inp.I_u:g} / {inp.L_u:g}³",
         "K": 3.0 * E * inp.I_u / inp.L_u**3},
        {"C": "C6", "Component": "Upright lip deformation",
         "Formula": "K6 = E·b_l·t_l³ / (4·L_l³)",
         "Working": f"{E:.0f} × {inp.b_l:g} × {inp.t_l:g}³ / (4 × {inp.L_l:g}³)",
         "K": E * inp.b_l * inp.t_l**3 / (4.0 * inp.L_l**3)},
    ]
    for c in comps:
        c["k = K/E"] = c["K"] / E               # stiffness coefficient, mm
        c["1/k"] = 1.0 / c["k = K/E"]           # 1/mm

    sum_inv_k = sum(c["1/k"] for c in comps)
    h = inp.H
    S_j_ini = E * h**2 / sum_inv_k             # N mm/rad
    S_j = S_j_ini / ETA
    limit = 0.5 * E * inp.I_b / inp.L_b        # N mm/rad

    return {
        "components": comps,
        "H_b": hb,
        "theta_available_rad": theta,
        "theta_available_deg": degrees(theta),
        "delta_bearing": delta_bearing,
        "h": h,
        "sum_inv_k": sum_inv_k,
        "S_j_ini": S_j_ini,                     # N mm/rad
        "S_j": S_j,
        "check_limit": limit,
        "check_ok": S_j_ini > limit,
    }
