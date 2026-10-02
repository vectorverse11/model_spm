"""
CBFEM Virtual Test — hook-connector joint (3-lip)
=================================================

Component-based method for the assembly UPRIGHT + BEAM + HOOK CONNECTOR.
Every dimension is entered by the user. The virtual machine itself finds the
maximum deflection, the load at which it is reached (F), and from F the
bearing stiffness K4, then generates the curves.

Fixed values (steel): E = 210000 N/mm^2, G = 80769 N/mm^2, nu = 0.3

1. Stop condition and maximum deflection
       H_b             = H - (H_t + beam depth)
       theta_available = tan^-1(t_p / H_b)            (rad)  -> test stops here
       delta_max       = P a^2 (3 l - a) / (6 E I_b)  at the stop load P = F
                         (a = 400 mm, l = 500 mm, I_b = beam inertia, x-axis)

2. Component stiffnesses (N/mm)
       K1 = 3 E I_b / L_b^3        beam local deformation
       K2 = 3 E I_h / L_h^3        hook bending
       K3 = G A_h / L_h            hook shear
       K4 = F / delta_bearing      hook-upright bearing, delta_bearing = t_p
       K5 = 3 E I_u / L_u^3        upright local deformation
       K6 = E b_l t_l^3 / (4 L_l^3) upright lip deformation

3. Joint stiffness (EN 1993-1-8 6.3.1), all six components
       S_j,ini = E h^2 / sum(1/k_i),  k_i = K_i / E   (= h^2 / sum(1/K_i))
       S_j     = S_j,ini / 2          secant stiffness
       h = total hook-connector height

4. Moment-rotation curve used by the virtual machine (M = P a)
       slope S_j,ini            up to M = 2/3 M_max      (EN 1993-1-8 6.3.1(4))
       then straight to the stop point (theta_available, M_max), so that the
       secant from the origin to the stop point is exactly S_j = S_j,ini / 2:
       theta_available = M_max / S_j = 2 M_max / S_j,ini

5. F and K4 depend on each other (K4 = F / t_p and F is the load at the stop
   point, which depends on K4). With R = sum over i != 4 of 1/K_i:
       theta_available = 2 F a (R + t_p / F) / h^2
   =>  F = (theta_available h^2 / (2 a) - t_p) / R        (closed form)
   The same F is reached by repeating the test: run -> note F -> K4 = F/t_p
   -> run again, which the engine also reports step by step.

6. Virtual test: load from 0 kN in steps of 0.01 / 0.02 kN; at each step
   theta from the curve, sensors D(x) = x tan(theta) at D1 = a = 400 mm,
   D2 = 40 mm, D3 = 140 mm; the test stops when theta reaches theta_available.
"""

from dataclasses import dataclass
from math import atan, degrees, tan
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


def delta_max(P: float, I_b: float) -> float:
    """Max deflection of the beam (cantilever, load P at a, length l):
    delta_max = P a^2 (3 l - a) / (6 E I_b)."""
    a, l = LOAD_ARM, BEAM_LENGTH
    return P * a**2 * (3.0 * l - a) / (6.0 * E * I_b)


def H_b(inp: CBFEMInputs) -> float:
    return inp.H - (inp.H_t + inp.beam_depth)


def theta_available(inp: CBFEMInputs) -> float:
    return atan(inp.t_p / H_b(inp))


def fixed_components(inp: CBFEMInputs) -> List[Dict]:
    """C1, C2, C3, C5, C6 — they do not depend on the test result."""
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
        {"C": "C5", "Component": "Upright local deformation",
         "Formula": "K5 = 3·E·I_u / L_u³",
         "Working": f"3 × {E:.0f} × {inp.I_u:g} / {inp.L_u:g}³",
         "K": 3.0 * E * inp.I_u / inp.L_u**3},
        {"C": "C6", "Component": "Upright lip deformation",
         "Formula": "K6 = E·b_l·t_l³ / (4·L_l³)",
         "Working": f"{E:.0f} × {inp.b_l:g} × {inp.t_l:g}³ / (4 × {inp.L_l:g}³)",
         "K": E * inp.b_l * inp.t_l**3 / (4.0 * inp.L_l**3)},
    ]


def S_j_ini_for(R: float, t_p: float, F: float, h: float) -> float:
    """S_j,ini (N mm/rad) for a given stop load F: h^2 / (R + 1/K4)."""
    return h**2 / (R + t_p / F)


def theta_of_M(M: float, S_ini: float, M_max: float) -> float:
    """Bilinear M-theta: S_j,ini up to 2/3 M_max, then to (theta_av, M_max)
    with secant S_j,ini / 2 at the stop point."""
    M_el = 2.0 / 3.0 * M_max
    if M <= M_el:
        return M / S_ini
    th_el = M_el / S_ini
    th_max = ETA * M_max / S_ini
    return th_el + (M - M_el) * (th_max - th_el) / (M_max - M_el)


def run(inp: CBFEMInputs, increment_kN: float) -> Dict:
    hb = H_b(inp)
    if hb <= 0:
        raise ValueError(
            f"H_b = H − (H_t + beam depth) = {inp.H:g} − ({inp.H_t:g} + "
            f"{inp.beam_depth:g}) = {hb:g} mm must be greater than 0.")
    th_av = theta_available(inp)
    h, a, t_p = inp.H, LOAD_ARM, inp.t_p

    fixed = fixed_components(inp)
    R = sum(1.0 / c["K"] for c in fixed)            # mm/N, all except K4
    A = th_av * h**2 / (ETA * a)                    # mm

    if A <= t_p:
        raise ValueError(
            "The joint cannot reach θ_available: θ_available·h²/(2·a) = "
            f"{A:.4g} mm is not greater than t_p = {t_p:g} mm, so no positive "
            "load F satisfies K4 = F / t_p at the stop point. Check H, H_t, "
            "beam depth and t_p.")

    # ---- F and K4: closed form, plus the run → note F → update K4 loop ----
    F = (A - t_p) / R
    # Run 1: K4 not known yet, bearing taken as rigid (K4 -> infinity)
    F_n = A / R
    iterations = [{"Run": 1, "F used for K4 (N)": None,
                   "K4 = F / t_p (N/mm)": None,
                   "S_j,ini (kN·m/rad)": h**2 / R / 1e6,
                   "Test stops at F (N)": F_n}]
    for n in range(2, 201):
        K4_n = F_n / t_p
        S_n = S_j_ini_for(R, t_p, F_n, h)
        F_next = th_av * S_n / (ETA * a)            # load at which this run stops
        iterations.append({"Run": n, "F used for K4 (N)": F_n,
                           "K4 = F / t_p (N/mm)": K4_n,
                           "S_j,ini (kN·m/rad)": S_n / 1e6,
                           "Test stops at F (N)": F_next})
        if abs(F_next - F_n) <= 1e-6 * F:
            break
        F_n = F_next

    K4 = F / t_p
    comps = fixed[:3] + [{
        "C": "C4", "Component": "Hook–upright bearing",
        "Formula": "K4 = F / δ_bearing,  δ_bearing = θ_available·H_b = t_p",
        "Working": f"{F:,.2f} / {t_p:g}", "K": K4}] + fixed[3:]
    for c in comps:
        c["k = K/E"] = c["K"] / E
        c["1/k"] = 1.0 / c["k = K/E"]
    sum_inv_k = sum(c["1/k"] for c in comps)
    S_ini = E * h**2 / sum_inv_k                     # N mm/rad
    S_j = S_ini / ETA
    M_max = F * a
    limit = 0.5 * E * inp.I_b / inp.L_b

    # ---- virtual test: load steps from 0 until theta_available ----
    inc = increment_kN * 1000.0

    def state(P):
        th = theta_of_M(P * a, S_ini, M_max)
        return {"P": P, "M": P * a, "theta": th,
                "D1": a * tan(th), "D2": X_D2 * tan(th), "D3": X_D3 * tan(th)}

    rows: List[Dict] = []
    P = 0.0
    while P < F:
        rows.append(state(P))
        P += inc
    rows.append(state(F))                            # stop point, exactly at theta_av

    rec = {k: [r[k] for r in rows] for k in ("P", "M", "theta", "D1", "D2", "D3")}
    rec["step"] = list(range(len(rows)))
    rec["theta_meas"] = [atan((r["D3"] - r["D2"]) / (X_D3 - X_D2)) for r in rows]

    return {
        "components": comps,
        "H_b": hb,
        "theta_available_rad": th_av,
        "theta_available_deg": degrees(th_av),
        "delta_max": delta_max(F, inp.I_b),          # mm, at the stop load F
        "delta_bearing": t_p,
        "h": h,
        "R_without_K4": R,
        "F": F,
        "K4": K4,
        "M_max": M_max,
        "iterations": iterations,
        "sum_inv_k": sum_inv_k,
        "S_j_ini": S_ini,
        "S_j": S_j,
        "M_el": 2.0 / 3.0 * M_max,
        "check_limit": limit,
        "check_ok": S_ini > limit,
        "record": rec,
        "steps": len(rows),
    }
