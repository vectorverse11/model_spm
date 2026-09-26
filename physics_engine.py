"""
Component-Method Physics Engine for Virtual SPM
================================================
Cantilever SPM decomposed into Eurocode-3-style components.
Includes 3-sensor simulation:
  D1 = piston travel (actuator encoder)
  D2 = LVDT at configurable position along beam
  D3 = LVDT at beam root (machine compliance only)

Beam-only deflection is recovered as:  δ_beam = D2 − D3

Load is applied in gradual increments: 0.01 or 0.02 kN per step.
Number of steps = max_load / increment.
"""

import numpy as np
from dataclasses import dataclass
from typing import Optional, List, Dict, Tuple


# ============================================================
# 1. INPUT STRUCTURES
# ============================================================

@dataclass
class MaterialInput:
    name: str = "E250 Steel (IS 2062)"
    youngs_modulus_GPa: Optional[float] = 200.0
    yield_strength_MPa: Optional[float] = 250.0
    carbon_pct: Optional[float] = None


@dataclass
class BeamGeometry:
    length_mm: float = 400.0
    width_mm: float = 30.0
    height_mm: float = 60.0
    section_type: str = "rectangular"


@dataclass
class UprightGeometry:
    height_mm: float = 800.0
    width_mm: float = 300.0
    thickness_mm: float = 50.0
    youngs_modulus_GPa: float = 200.0
    yield_strength_MPa: float = 250.0
    base_fixity: str = "fixed"


@dataclass
class ConnectionProperties:
    rotational_stiffness_Nmm_per_rad: float = 5.0e8
    moment_resistance_Nmm: float = 1.5e6
    connection_type: str = "bolted_end_plate"
    post_yield_stiffness_ratio: float = 0.05


@dataclass
class HookConnector:
    length_mm: float = 100.0
    width_mm: float = 20.0
    thickness_mm: float = 10.0
    youngs_modulus_GPa: float = 200.0
    yield_strength_MPa: float = 250.0
    offset_from_tip_mm: float = 0.0


@dataclass
class LoadInput:
    max_load_N: float = 12000.0
    failure_load_N: Optional[float] = 15000.0
    apply_preload: bool = True
    preload_fraction: float = 0.10
    loadcell_stiffness_N_per_mm: float = 5.0e5
    actuator_stiffness_N_per_mm: float = 1.0e6
    # ---- Load increment per step (kN) ----
    load_increment_kN: float = 0.01          # 0.01 or 0.02 kN


@dataclass
class NonlinearOptions:
    enable_seating: bool = True
    seating_gap_mm: float = 0.15
    seating_slip_load_N: float = 200.0
    enable_beam_yield: bool = True
    beam_strain_hardening_ratio: float = 0.02
    enable_connection_yield: bool = True
    enable_upright_yield: bool = True
    enable_hook_yield: bool = True
    enable_geometric_nl: bool = False


# ============================================================
# 2. COMPONENT SPRING
# ============================================================

@dataclass
class ComponentSpring:
    name: str
    k_elastic: float
    F_Rd: float
    alpha: float = 0.02
    enabled: bool = True

    def deformation(self, P: float) -> float:
        if self.k_elastic <= 0:
            return 0.0
        P = abs(P)
        d_elastic = P / self.k_elastic
        if not self.enabled or P <= self.F_Rd or self.F_Rd == float("inf"):
            return d_elastic
        d_yield = self.F_Rd / self.k_elastic
        d_plastic = (P - self.F_Rd) / (max(self.alpha, 1e-6) * self.k_elastic)
        return d_yield + d_plastic

    def yielded_at(self, P: float) -> bool:
        return self.enabled and P > self.F_Rd


# ============================================================
# 3. SECTION PROPERTIES
# ============================================================

class SectionProperties:
    @staticmethod
    def compute(b: float, h: float, section_type: str) -> Dict:
        if section_type == "rectangular":
            I = b * h**3 / 12.0
            Z = b * h**2 / 6.0
            shape = 1.5
        elif section_type == "circular":
            d = h
            I = np.pi * d**4 / 64.0
            Z = np.pi * d**3 / 32.0
            shape = 1.7
        else:
            raise ValueError(section_type)
        return {"I": I, "Z": Z, "shape": shape}


# ============================================================
# 4. COMPONENT-METHOD SPM ENGINE
# ============================================================

class ComponentMethodSPM:

    def __init__(self,
                 material: MaterialInput,
                 beam: BeamGeometry,
                 upright: UprightGeometry,
                 connection: ConnectionProperties,
                 hook: HookConnector,
                 load: LoadInput,
                 nl: Optional[NonlinearOptions] = None,
                 d2_position_mm: Optional[float] = None):
        self.material = material
        self.beam = beam
        self.upright = upright
        self.connection = connection
        self.hook = hook
        self.load = load
        self.nl = nl or NonlinearOptions()

        self.D2_position_mm = (d2_position_mm
                               if d2_position_mm is not None
                               else beam.length_mm)

        # Elastic material & section properties
        self.E = (material.youngs_modulus_GPa or 200.0) * 1000.0
        self.fy = material.yield_strength_MPa or 250.0
        sec = SectionProperties.compute(beam.width_mm, beam.height_mm,
                                        beam.section_type)
        self.I_beam, self.Z_beam = sec["I"], sec["Z"]
        self.shape_factor = sec["shape"]

        self.E_up = upright.youngs_modulus_GPa * 1000.0
        self.fy_up = upright.yield_strength_MPa
        self.I_up = upright.width_mm * upright.thickness_mm**3 / 12.0
        self.Z_up = upright.width_mm * upright.thickness_mm**2 / 6.0

        self.E_h = hook.youngs_modulus_GPa * 1000.0
        self.fy_h = hook.yield_strength_MPa
        self.A_h = hook.width_mm * hook.thickness_mm

        self.L = beam.length_mm + hook.offset_from_tip_mm
        self.H = upright.height_mm

        self._build_components()
        self.reset()

    # --------------------------------------------------------
    def _build_components(self):
        L, H = self.L, self.H
        E, I, Z, fy = self.E, self.I_beam, self.Z_beam, self.fy

        # (1) BEAM FLEXURE
        self.spring_beam = ComponentSpring(
            name="Beam flexure",
            k_elastic=3.0 * E * I / L**3,
            F_Rd=fy * Z / L,
            alpha=self.nl.beam_strain_hardening_ratio,
            enabled=self.nl.enable_beam_yield,
        )

        # (2) CONNECTION
        Sj = self.connection.rotational_stiffness_Nmm_per_rad
        Mj = self.connection.moment_resistance_Nmm
        self.spring_conn = ComponentSpring(
            name="Connection",
            k_elastic=Sj / L**2,
            F_Rd=Mj / L,
            alpha=self.connection.post_yield_stiffness_ratio,
            enabled=self.nl.enable_connection_yield,
        )

        # (3) UPRIGHT FLEXURE
        E_up, I_up, Z_up, fy_up = self.E_up, self.I_up, self.Z_up, self.fy_up
        if self.upright.base_fixity == "fixed":
            k_up = E_up * I_up / (L**2 * H)
        else:
            k_up = 3.0 * E_up * I_up / (L**2 * H)
        F_up_yield = fy_up * Z_up / H if H > 0 else float("inf")
        self.spring_up = ComponentSpring(
            name="Upright flexure",
            k_elastic=k_up,
            F_Rd=F_up_yield,
            alpha=0.02,
            enabled=self.nl.enable_upright_yield,
        )

        # (4) HOOK AXIAL
        k_hook = self.A_h * self.E_h / self.hook.length_mm
        self.spring_hook = ComponentSpring(
            name="Hook axial",
            k_elastic=k_hook,
            F_Rd=self.fy_h * self.A_h,
            alpha=0.01,
            enabled=self.nl.enable_hook_yield,
        )

        self.springs = [self.spring_beam, self.spring_conn,
                        self.spring_up, self.spring_hook]

    # --------------------------------------------------------
    def delta_seating(self, P: float) -> float:
        if not self.nl.enable_seating or P <= 0:
            return 0.0
        s = max(self.nl.seating_slip_load_N, 1e-6)
        return self.nl.seating_gap_mm * (1.0 - np.exp(-(P / s) ** 2))

    # --------------------------------------------------------
    def total_deflection(self, P: float) -> Tuple[float, Dict[str, float]]:
        comps = {}
        d_sum = 0.0
        for s in self.springs:
            d = s.deformation(P)
            comps[s.name] = d
            d_sum += d
        d_seat = self.delta_seating(P)
        comps["Seating gap"] = d_seat
        return d_sum + d_seat, comps

    # --------------------------------------------------------
    def compute_sensors(self, P: float, comps: Dict[str, float]) -> Tuple[float, float, float]:
        """
        D1 = piston travel (total displacement of loading system)
        D2 = LVDT at position x2 along the beam
        D3 = LVDT at beam root (machine compliance only)
        """
        d_beam = comps.get("Beam flexure", 0.0)
        d_up   = comps.get("Upright flexure", 0.0)
        d_conn = comps.get("Connection", 0.0)
        d_seat = comps.get("Seating gap", 0.0)
        d_hook = comps.get("Hook axial", 0.0)

        d_loadcell = P / max(self.load.loadcell_stiffness_N_per_mm, 1e-6)
        d_actuator = P / max(self.load.actuator_stiffness_N_per_mm, 1e-6)

        machine = d_up + d_conn + d_seat

        x2 = min(max(self.D2_position_mm, 0.0), self.L)
        if self.L > 0:
            shape = (3.0 * self.L * x2**2 - x2**3) / (2.0 * self.L**3)
        else:
            shape = 0.0
        beam_at_x2 = d_beam * shape

        D1 = machine + d_beam + d_hook + d_loadcell + d_actuator
        D2 = machine + beam_at_x2
        D3 = machine
        return D1, D2, D3

    # --------------------------------------------------------
    def reset(self):
        self.loads: List[float] = []
        self.steps: List[int] = []
        self.deflections: List[float] = []
        self.moments: List[float] = []
        self.rotations: List[float] = []
        self.stresses: List[float] = []
        self.D1: List[float] = []
        self.D2: List[float] = []
        self.D3: List[float] = []
        self.beam_only: List[float] = []
        self.components: Dict[str, List[float]] = {}
        self._preload_end = 0

    # --------------------------------------------------------
    def run(self) -> Dict:
        self.reset()

        # ---- Load schedule: gradual increment in kN ----
        increment_N = max(self.load.load_increment_kN * 1000.0, 1e-6)
        P_vals = np.arange(0.0,
                           self.load.max_load_N + increment_N * 0.5,
                           increment_N)
        if P_vals[-1] < self.load.max_load_N:
            P_vals = np.append(P_vals, self.load.max_load_N)

        # Preload index
        if self.load.apply_preload and self.load.failure_load_N:
            preload_N = self.load.preload_fraction * self.load.failure_load_N
            self._preload_end = int(np.searchsorted(P_vals, preload_N))
        else:
            self._preload_end = 0

        for step_idx, P in enumerate(P_vals):
            delta, comps = self.total_deflection(P)
            M = P * self.L
            theta = delta / self.L if self.L > 0 else 0.0
            sigma = M / self.Z_beam

            D1, D2, D3 = self.compute_sensors(P, comps)
            beam_deflection = D2 - D3

            self.steps.append(step_idx)
            self.loads.append(P)
            self.deflections.append(delta)
            self.moments.append(M)
            self.rotations.append(theta)
            self.stresses.append(sigma)
            self.D1.append(D1)
            self.D2.append(D2)
            self.D3.append(D3)
            self.beam_only.append(beam_deflection)

            for k, val in comps.items():
                self.components.setdefault(k, []).append(val)

        return self._summarize()

    # --------------------------------------------------------
    def _summarize(self) -> Dict:
        P = np.array(self.loads, dtype=float)
        d = np.array(self.deflections, dtype=float)
        M = np.array(self.moments, dtype=float)
        th = np.array(self.rotations, dtype=float)

        start = self._preload_end if self._preload_end < len(P) - 1 else 0
        P_l, d_l = P[start:], d[start:]
        if len(P_l) >= 3:
            k_lin = (P_l[-1] - P_l[0]) / max(d_l[-1] - d_l[0], 1e-12)
        else:
            k_lin = P[-1] / d[-1] if d[-1] > 0 else float("inf")

        beam_arr = np.array(self.beam_only, dtype=float)
        b_l = beam_arr[start:]
        if len(P_l) >= 3 and (b_l[-1] - b_l[0]) > 1e-12:
            k_corrected = (P_l[-1] - P_l[0]) / (b_l[-1] - b_l[0])
        else:
            k_corrected = float("inf")

        k_beam_ideal = self.spring_beam.k_elastic
        k_rot = (M[-1] / th[-1]) if th[-1] > 0 else float("inf")

        P_max = P[-1]
        yielded_flags = {s.name: s.yielded_at(P_max) for s in self.springs}
        yield_table = {
            s.name: {
                "F_Rd_N": s.F_Rd,
                "k_N_per_mm": s.k_elastic,
                "yielded": s.yielded_at(P_max),
            }
            for s in self.springs
        }

        stress_arr = np.asarray(self.stresses, dtype=float)
        max_stress = float(np.max(stress_arr))
        yielded = bool(max_stress > self.fy)
        P_yield = None
        if yielded:
            yield_indices = np.where(stress_arr > self.fy)[0]
            if len(yield_indices) > 0:
                P_yield = float(self.loads[int(yield_indices[0])])

        comp_max = {k: v[-1] for k, v in self.components.items()}
        parasitic = (comp_max.get("Upright flexure", 0)
                     + comp_max.get("Connection", 0)
                     + comp_max.get("Hook axial", 0))
        total_defl = max(self.deflections[-1], 1e-9)
        rigidity = parasitic / total_defl

        d_loadcell_max = P_max / max(self.load.loadcell_stiffness_N_per_mm, 1e-6)
        d_actuator_max = P_max / max(self.load.actuator_stiffness_N_per_mm, 1e-6)
        d_hook_max = comp_max.get("Hook axial", 0.0)
        load_train = d_loadcell_max + d_actuator_max + d_hook_max

        return {
            "E_MPa": self.E, "fy_MPa": self.fy,
            "I_beam_mm4": self.I_beam, "Z_beam_mm3": self.Z_beam,
            "I_upright_mm4": self.I_up,
            "L_eff_mm": self.L,
            "D2_position_mm": self.D2_position_mm,
            "load_increment_kN": self.load.load_increment_kN,
            "total_steps": len(P),
            "preload_N": float(P[self._preload_end - 1]) if self._preload_end > 0 else 0.0,
            "k_linear_N_per_mm": float(k_lin),
            "k_corrected_N_per_mm": float(k_corrected),
            "k_beam_ideal_N_per_mm": float(k_beam_ideal),
            "k_rot_Nmm_per_rad": float(k_rot),
            "stiffness_loss_pct": float(100.0 * (k_beam_ideal - k_lin) / k_beam_ideal)
                if k_beam_ideal > 0 else 0.0,
            "max_stress_MPa": max_stress,
            "yielded": yielded, "P_yield_N": P_yield,
            "yield_table": yield_table,
            "yielded_flags": yielded_flags,
            "components_max_mm": comp_max,
            "parasitic_deflection_mm": parasitic,
            "rigidity_ratio": rigidity,
            "load_train_deflection_mm": load_train,
            "loads": self.loads,
            "steps": self.steps,
            "deflections": self.deflections,
            "moments": self.moments,
            "rotations": self.rotations,
            "stresses": self.stresses,
            "D1": self.D1, "D2": self.D2, "D3": self.D3,
            "beam_only": self.beam_only,
            "components": self.components,
            "preload_end_index": self._preload_end,
            "springs": self.springs,
        }