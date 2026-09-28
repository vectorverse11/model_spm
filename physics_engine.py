"""
Component-Method Engine — Virtual Beam-End Hook Connector Test (SPM)
===================================================================

COP-style component analysis for the assembly  UPRIGHT + BEAM + HOOK CONNECTOR.
Each component gets its own stiffness from the handwritten formulae; the
components are then assembled into the joint's rotational stiffness and
moment resistance, and a virtual cantilever test is run.

Components (handwritten formulae, E = 210000, G = 80769 N/mm^2):
    C1 Beam local deformation      K1 = 3 E I_b / L^3          (L = 400 mm)
    C2 Hook bending                K2 = 3 E I_h / l_h^3
    C3 Hook shear                  K3 = G A_h / L_h
    C4 Hook-upright bearing        K4 = F / delta_bearing
    C5 Upright local deformation   K5 = 3 E I_u / L_u^3
    C6 Upright lip deformation     K6 = E b_l t_l^3 / (4 L_l^3)

Assembly (EN 1993-1-8 component method, as in COP):
    per lip:   k_lip = 1 / (1/K2 + 1/K3 + 1/K4 + 1/K5 + 1/K6)
               F_lip = min(F2,Rd ... F6,Rd)
    joint:     S_j,ini = sum(k_lip z^2)            elastic rotational stiffness
               S_j     = S_j,ini / eta  (eta = 2)  plastic rotational stiffness
               M_j,Rd  = sum(F_lip z)              plastic moment resistance
               M_j,el  = 2/3 M_j,Rd                elastic moment resistance
    z = lever arm of each lip to the connector bottom edge (downward load:
        top lips pull out, the connector bottom bears on the upright).

Virtual test (rig: beam 500 mm, piston D1 at 400 mm, D2 at 40 mm, D3 at
140 mm from the upright face). Load starts at 0 kN and increases by the
chosen increment until D1 reaches the maximum deflection:
    M = P a
    theta = M / S_j,ini                          for M <= M_j,el
          = theta_el + (M - M_j,el) / S_j         for M_j,el < M <= M_j,Rd
          then the load is held at P_Rd = M_j,Rd / a while theta grows
    D(x) = theta x + P x^2 (3a - x) / (6 E I_b)   (C1 beam bending)

Units: N, mm, N/mm^2, rad.
"""

from dataclasses import dataclass
from typing import Dict, List

import numpy as np

E = 210000.0                    # N/mm^2
NU = 0.3
G = E / (2.0 * (1.0 + NU))      # 80769 N/mm^2
ETA = 2.0                       # EN 1993-1-8 5.1.2: S_j = S_j,ini / eta
GAMMA_M0 = 1.0                  # EN 1993-1-8 partial factor on resistances

# Test rig (fixed)
BEAM_LENGTH = 500.0
LOAD_ARM = 400.0                # D1 piston
X_D2 = 40.0
X_D3 = 140.0

# Hook-connector lip layout (upright slot pitch)
LIP_PITCH = 50.0
FIRST_LIP_CENTRE = 25.1         # from connector top


# ============================================================
# INPUTS
# ============================================================

@dataclass
class Material:
    grade: str
    quality: str
    fy: float                   # N/mm^2 (IS 2062 ReH)
    fu: float                   # N/mm^2 (IS 2062 Rm)


@dataclass
class Upright:
    D: float
    W: float
    B: float
    T: float


@dataclass
class Beam:
    H: float
    W: float
    T: float
    beam_type: str = ""

    @property
    def W_pl(self) -> float:
        """Plastic modulus of the closed box section (bending about H)."""
        h, b, t = self.H, self.W, self.T
        return (b * h**2 - (b - 2 * t) * (h - 2 * t) ** 2) / 4.0

    @property
    def I_box(self) -> float:
        """Reference I of the box section, shown as a hint for I_b."""
        h, b, t = self.H, self.W, self.T
        return (b * h**3 - (b - 2 * t) * (h - 2 * t) ** 3) / 12.0


@dataclass
class Connector:
    n_lips: int
    H: float
    D: float
    W: float
    T: float

    def lip_centres(self) -> np.ndarray:
        return FIRST_LIP_CENTRE + LIP_PITCH * np.arange(self.n_lips)


@dataclass
class ComponentInputs:
    I_b: float                  # C1 beam moment of inertia (mm^4)
    I_h: float                  # C2 hook moment of inertia (mm^4)
    l_h: float                  # C2 effective hook bending length (mm)
    A_h: float                  # C3 effective hook shear area (mm^2)
    L_h: float                  # C3 effective hook deformation length (mm)
    F_bearing: float            # C4 max load at hook-upright contact (N)
    delta_bearing: float        # C4 deflection at that load (mm)
    L_u: float                  # C5 effective length of deforming upright (mm)
    I_u: float                  # C5 second moment of effective upright strip (mm^4)
    b_u: float                  # C5 effective width of upright wall (mm)
    t_u: float                  # C5 upright thickness (mm)
    b_l: float                  # C6 effective lip width (mm)
    t_l: float                  # C6 lip thickness (mm)
    L_l: float                  # C6 effective lip length (mm)


@dataclass
class TestSetup:
    __test__ = False            # not a pytest test class
    increment_kN: float         # 0.01 or 0.02
    max_deflection: float       # D1 value at which the test stops (mm)


@dataclass
class Component:
    code: str
    name: str
    formula: str
    K: float                    # N/mm
    F_Rd: float                 # N
    F_Rd_basis: str


# ============================================================
# ENGINE
# ============================================================

class VirtualSPM:

    def __init__(self, material: Material, upright: Upright, beam: Beam,
                 connector: Connector, comp: ComponentInputs, test: TestSetup):
        self.mat, self.up, self.beam = material, upright, beam
        self.con, self.c, self.test = connector, comp, test
        self.a = LOAD_ARM
        self._validate()
        self._components()
        self._assemble()

    # --------------------------------------------------------
    def _validate(self) -> None:
        last = FIRST_LIP_CENTRE + LIP_PITCH * (self.con.n_lips - 1)
        if last >= self.con.H:
            raise ValueError(
                f"{self.con.n_lips} lips at {LIP_PITCH:g} mm pitch (last lip centre "
                f"{last:g} mm) do not fit in a {self.con.H:g} mm connector.")

    def _components(self) -> None:
        c, fy = self.c, self.mat.fy
        L = self.a
        t_h = self.con.T
        self.C1 = Component(
            "C1", "Beam local deformation", "3·E·I_b / L³",
            3.0 * E * c.I_b / L**3,
            fy * self.beam.W_pl / L / GAMMA_M0, "fy·W_pl,b / L")
        self.lip_components = [
            Component("C2", "Hook bending", "3·E·I_h / l_h³",
                      3.0 * E * c.I_h / c.l_h**3,
                      fy * (3.0 * c.I_h / t_h) / c.l_h / GAMMA_M0,
                      "fy·W_pl,h / l_h, W_pl,h = 3·I_h / t"),
            Component("C3", "Hook shear", "G·A_h / L_h",
                      G * c.A_h / c.L_h,
                      fy * c.A_h / np.sqrt(3.0) / GAMMA_M0, "fy·A_h / √3"),
            Component("C4", "Hook-upright bearing", "F / δ_bearing",
                      c.F_bearing / c.delta_bearing,
                      c.F_bearing, "F (max load at contact)"),
            Component("C5", "Upright local deformation", "3·E·I_u / L_u³",
                      3.0 * E * c.I_u / c.L_u**3,
                      fy * c.b_u * c.t_u**2 / (4.0 * c.L_u) / GAMMA_M0,
                      "fy·b_u·t_u² / (4·L_u)"),
            Component("C6", "Upright lip deformation", "E·b_l·t_l³ / (4·L_l³)",
                      E * c.b_l * c.t_l**3 / (4.0 * c.L_l**3),
                      fy * c.b_l * c.t_l**2 / (4.0 * c.L_l) / GAMMA_M0,
                      "fy·b_l·t_l² / (4·L_l)"),
        ]

    def _assemble(self) -> None:
        comps = self.lip_components
        self.k_lip = 1.0 / sum(1.0 / x.K for x in comps)
        gov = min(comps, key=lambda x: x.F_Rd)
        self.F_lip, self.governing = gov.F_Rd, f"{gov.code} {gov.name}"

        self.z = self.con.H - self.con.lip_centres()     # lever arms
        self.S_j_ini = float(np.sum(self.k_lip * self.z**2))
        self.S_j = self.S_j_ini / ETA
        M_conn = float(np.sum(self.F_lip * self.z))
        M_beam = self.C1.F_Rd * self.a                   # beam plastic moment
        self.M_j_Rd = min(M_conn, M_beam)
        self.M_governed_by = ("connection (" + self.governing + ")"
                              if M_conn <= M_beam else "C1 beam plastic moment")
        self.M_j_el = 2.0 / 3.0 * self.M_j_Rd
        self.theta_el = self.M_j_el / self.S_j_ini
        self.theta_Rd = self.theta_el + (self.M_j_Rd - self.M_j_el) / self.S_j
        self.P_el = self.M_j_el / self.a
        self.P_Rd = self.M_j_Rd / self.a

    # --------------------------------------------------------
    def theta(self, M: float) -> float:
        if M <= self.M_j_el:
            return M / self.S_j_ini
        return self.theta_el + (min(M, self.M_j_Rd) - self.M_j_el) / self.S_j

    def beam_deflection(self, P: float, x: float) -> float:
        a = self.a
        if x <= a:
            return P * x**2 * (3.0 * a - x) / (6.0 * E * self.c.I_b)
        return P * a**2 * (3.0 * x - a) / (6.0 * E * self.c.I_b)

    def _sensors(self, P: float, theta: float) -> Dict[str, float]:
        def d(x):
            return theta * x + self.beam_deflection(P, x)
        return {"P": P, "M": P * self.a, "theta": theta,
                "D1": d(self.a), "D2": d(X_D2), "D3": d(X_D3)}

    def run(self) -> Dict:
        inc = self.test.increment_kN * 1000.0
        d_max = self.test.max_deflection
        rows: List[Dict[str, float]] = []

        def state(P):
            return self._sensors(P, self.theta(P * self.a))

        # Phase 1: load from 0 in increments up to P_Rd
        P, reached_max = 0.0, False
        while True:
            P_i = min(P, self.P_Rd)
            s = state(P_i)
            if s["D1"] >= d_max:
                lo, hi = (rows[-1]["P"] if rows else 0.0), P_i
                for _ in range(60):
                    mid = 0.5 * (lo + hi)
                    lo, hi = (mid, hi) if state(mid)["D1"] < d_max else (lo, mid)
                rows.append(state(hi))
                reached_max = True
                break
            rows.append(s)
            if P_i >= self.P_Rd:
                break
            P += inc

        # Phase 2: M_j,Rd reached — load held, rotation grows to max deflection
        plastic_plateau = not reached_max
        if plastic_plateau:
            s = rows[-1]
            step = 0.01                                  # mm of D1 per record
            th = s["theta"]
            while s["D1"] < d_max and len(rows) < 50000:
                th += step / self.a
                s = self._sensors(self.P_Rd, th)
                if s["D1"] > d_max:
                    th -= (s["D1"] - d_max) / self.a
                    s = self._sensors(self.P_Rd, th)
                rows.append(s)

        return self._summary(rows, plastic_plateau)

    # --------------------------------------------------------
    def _summary(self, rows: List[Dict[str, float]], plastic_plateau: bool) -> Dict:
        rec = {k: [r[k] for r in rows] for k in ("P", "M", "theta", "D1", "D2", "D3")}
        rec["step"] = list(range(len(rows)))
        rec["theta_meas"] = [(r["D3"] - r["D2"]) / (X_D3 - X_D2) for r in rows]

        P_pk, M_pk = rec["P"][-1], rec["M"][-1]
        # Lip forces: plastic distribution scaled by M / M_j,Rd
        F_lip_pk = self.F_lip * min(M_pk / self.M_j_Rd, 1.0)
        comp_table = [{
            "Component": f"{self.C1.code} {self.C1.name}",
            "Formula": self.C1.formula,
            "Stiffness K (N/mm)": self.C1.K,
            "Resistance F_Rd (N)": self.C1.F_Rd,
            "Deformation δ (mm)": P_pk / self.C1.K,
        }]
        for x in self.lip_components:
            comp_table.append({
                "Component": f"{x.code} {x.name}",
                "Formula": x.formula,
                "Stiffness K (N/mm)": x.K,
                "Resistance F_Rd (N)": x.F_Rd,
                "Deformation δ (mm)": F_lip_pk / x.K,
            })

        lips = [{"Lip": i + 1, "Centre from top (mm)": float(y),
                 "Lever arm z (mm)": float(z),
                 "k_lip (N/mm)": self.k_lip, "F_lip,Rd (N)": self.F_lip,
                 "k_lip·z² (kN·m/rad)": self.k_lip * z**2 / 1e6,
                 "F_lip·z (kN·m)": self.F_lip * z / 1e6}
                for i, (y, z) in enumerate(zip(self.con.lip_centres(), self.z))]

        return {
            "record": rec,
            "components": comp_table,
            "lips": lips,
            "S_j_ini": self.S_j_ini, "S_j": self.S_j,
            "M_j_el": self.M_j_el, "M_j_Rd": self.M_j_Rd,
            "theta_el": self.theta_el, "theta_Rd": self.theta_Rd,
            "P_el": self.P_el, "P_Rd": self.P_Rd,
            "k_lip": self.k_lip, "governing": self.governing,
            "M_governed_by": self.M_governed_by,
            "plastic_plateau": plastic_plateau,
            "P_peak": P_pk, "steps": len(rows),
        }
