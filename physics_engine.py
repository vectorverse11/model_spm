"""
Component-Method Physics Engine — Virtual Beam-End-Connector (Hook) Test SPM
===========================================================================

Virtual replica of the cantilever beam-end-connector test rig used for steel
storage racking (EN 15512 Annex A "beam end connector test"):

    * a short upright (e.g. 800 mm) is clamped in the frame,
    * a short beam stub with a welded hook connector is hooked into the
      upright slots,
    * a hydraulic actuator pushes the beam down at lever arm ``a`` (400 mm)
      from the upright face in small monotonic load steps,
    * three displacement sensors are recorded:
          D1 = piston (actuator) displacement sensor    (x = a  = 400 mm)
          D2 = LVDT on the beam, near the connector     (x = x2 =  40 mm)
          D3 = LVDT on the beam, further out            (x = x3 = 140 mm)
      and the connector rotation is  theta = (D3 - D2) / (x3 - x2).

The connection is decomposed into components following the EN 1993-1-8
component method (the same philosophy as bolted end-plate joints) but with
the bolt rows replaced by hook ("lip") rows:

    C1  beam flexure                     K1 = 3 E I_b / a^3          (whole beam)
    C2  hook (lip) bending               K2 = 3 E I_h / l_h^3        (per lip)
    C3  hook (lip) shear                 K3 = G A_h / L_h            (per lip)
    C4  hook-to-upright bearing          K4 = E b_brg t_u / L_brg    (per lip)
    C5  upright wall local deformation   K5 = E b_u t_u^3 / (4 L_u^3)(per lip)
    C6  connector lip (plate) bending    K6 = E b_l t_l^3 / (4 L_l^3)(per lip)

For every lip row r the springs C2..C6 act in series:
    k_eff,r = 1 / (1/K2 + 1/K3 + 1/K4 + 1/K5 + 1/K6)
    F_Rd,r  = min(F2,Rd ... F6,Rd)
Rows are assembled about the centre of compression (bottom of connector,
where the connector bears on the upright face) with lever arms z_r:
    S_j,ini = sum(k_eff,r * z_r^2)          (EN 1993-1-8 6.3 with k in N/mm)
    M_j,Rd  = sum(F_Rd,r * z_r)             (plastic row distribution)
Row non-linearity uses the EN 1993-1-8 6.3.1(6) stiffness ratio
    mu = (1.5 F / F_Rd)^psi   for 2/3 F_Rd < F <= F_Rd,
followed by linear strain hardening up to the ultimate row force
F_u,r = F_Rd,r * fu / fy, at which the row (and the test) fails.

All units: N, mm, MPa (N/mm^2), rad.
"""

from dataclasses import dataclass, field
from typing import Dict, List, Optional, Tuple

import numpy as np


# ============================================================
# 1. INPUT STRUCTURES
# ============================================================

@dataclass
class Material:
    name: str = "E250 Steel (IS 2062)"
    E: float = 210000.0          # N/mm^2
    nu: float = 0.3
    fy: float = 250.0            # N/mm^2
    fu: float = 410.0            # N/mm^2

    @property
    def G(self) -> float:
        return self.E / (2.0 * (1.0 + self.nu))


@dataclass
class BeamSection:
    """Beam stub welded to the connector."""
    section_type: str = "box"    # "box" | "solid_rect" | "custom"
    depth: float = 80.0          # h_b (mm)
    width: float = 50.0          # b (mm)
    thickness: float = 1.6       # wall thickness for box (mm)
    I_custom: float = 3.7e5      # mm^4, used when section_type == "custom"
    Wpl_custom: float = 1.1e4    # mm^3, used when section_type == "custom"
    length: float = 500.0        # physical stub length from upright face (mm)
    span_for_classification: float = 2700.0   # L_b of the real rack beam (mm)

    def properties(self) -> Dict[str, float]:
        h, b, t = self.depth, self.width, self.thickness
        if self.section_type == "box":
            hi, bi = h - 2 * t, b - 2 * t
            I = (b * h**3 - bi * hi**3) / 12.0
            Wpl = (b * h**2 - bi * hi**2) / 4.0
        elif self.section_type == "solid_rect":
            I = b * h**3 / 12.0
            Wpl = b * h**2 / 4.0
        elif self.section_type == "custom":
            I, Wpl = self.I_custom, self.Wpl_custom
        else:
            raise ValueError(f"Unknown beam section type: {self.section_type}")
        return {"I": I, "Wpl": Wpl}


@dataclass
class UprightSection:
    """Perforated open (lipped channel) upright, clamped in the rig."""
    face_width: float = 90.0     # slotted face width (mm)
    depth: float = 70.0          # side-wall depth (mm)
    lip: float = 20.0            # return lip (mm)
    thickness: float = 2.0       # t_u (mm)
    perforation_factor: float = 0.85   # I_net / I_gross
    I_custom: Optional[float] = None   # overrides computed I if given
    clamp_length: float = 800.0  # distance between rig clamps (mm)
    end_fixity: str = "fixed-fixed"    # "fixed-fixed" | "pinned-pinned" | "rigid"

    def I_bending(self) -> float:
        """Second moment about the axis parallel to the slotted face
        (bending in the plane of the beam), thin-walled segment model."""
        if self.I_custom:
            return self.I_custom
        B, D, c, t = self.face_width, self.depth, self.lip, self.thickness
        # Coordinate y measured perpendicular to the face (face at y = 0).
        segs = [  # (area, centroid y, own I about its centroid)
            (B * t, 0.0, B * t**3 / 12.0),                       # face
            (2 * D * t, D / 2.0, 2 * t * D**3 / 12.0),           # 2 side walls
            (2 * c * t, D, 2 * c * t**3 / 12.0),                 # 2 return lips
        ]
        A = sum(s[0] for s in segs)
        yc = sum(s[0] * s[1] for s in segs) / A
        I = sum(s[2] + s[0] * (s[1] - yc) ** 2 for s in segs)
        return I * self.perforation_factor


@dataclass
class HookConnector:
    """Hook connector ("lip") geometry.

    Connector height by number of lips (fixed product data):
        5 lips -> 245 mm, 4 lips -> 195 mm, 3 lips -> 145 mm
        width 44 mm, hole top-edge 10.3 mm from top, 34.7 mm bottom end
        distance, pitch 50 mm, first lip centre 25.1 mm from top.
    """
    n_lips: int = 5
    width: float = 44.0          # connector (lip plate) width (mm)
    plate_thickness: float = 4.0  # t_p (mm)
    pitch: float = 50.0
    top_end_distance: float = 10.3     # top edge -> first hole edge
    bottom_end_distance: float = 34.7  # last hole edge -> bottom edge
    first_lip_centre: float = 25.1     # top edge -> first lip centre

    @property
    def height(self) -> float:
        return (self.top_end_distance + (self.n_lips - 1) * self.pitch
                + self.bottom_end_distance)

    @property
    def lip_height(self) -> float:
        """Engaged lip height inferred from hole edge (10.3) and lip centre
        (25.1): 2 * (25.1 - 10.3) = 29.6 mm."""
        return 2.0 * (self.first_lip_centre - self.top_end_distance)

    def lip_centres_from_top(self) -> np.ndarray:
        return self.first_lip_centre + self.pitch * np.arange(self.n_lips)


@dataclass
class ComponentParameters:
    """The 'unknowns' of the hand-written derivation (per lip row).
    Defaults are engineering estimates — calibrate against a real test."""
    # C2 hook bending:  K2 = 3 E I_h / l_h^3, I_h = b_h t_h^3 / 12
    hook_width_bh: Optional[float] = None   # None -> connector.lip_height
    hook_thickness_th: Optional[float] = None  # None -> connector.plate_thickness
    hook_bending_length_lh: float = 8.0
    # C3 hook shear:    K3 = G A_h / L_h, A_h = b_h t_h
    hook_shear_length_Lh: float = 8.0
    # C4 bearing:       K4 = E b_brg t_u / L_brg
    bearing_width: float = 12.0
    bearing_length: float = 10.0
    # C5 upright wall:  K5 = E b_u t_u^3 / (4 L_u^3)
    upright_eff_width_bu: float = 40.0
    upright_eff_length_Lu: float = 15.0
    # C6 connector lip: K6 = E b_l t_l^3 / (4 L_l^3)
    lip_eff_width_bl: Optional[float] = None   # None -> connector.pitch
    lip_thickness_tl: Optional[float] = None   # None -> connector.plate_thickness
    lip_eff_length_Ll: float = 20.0
    gamma_M0: float = 1.0        # partial factor applied to component resistances
    gamma_M2: float = 1.25       # bearing partial factor


@dataclass
class TestRig:
    load_arm_a: float = 400.0     # actuator distance from upright face
    x_D2: float = 40.0            # LVDT near the connector
    x_D3: float = 140.0           # LVDT further out
    load_train_stiffness: float = 2.0e5   # N/mm, actuator + load-cell (affects D1 only)
    sensor_noise_mm: float = 0.0  # 1-sigma LVDT noise
    seed: int = 1


@dataclass
class LoadSchedule:
    increment_kN: float = 0.01    # 0.01 or 0.02 kN per step
    max_load_N: float = 5000.0
    stop_at_failure: bool = True


@dataclass
class NonlinearOptions:
    looseness_rad: float = 0.004  # initial looseness rotation (EN 15512 A.2.5)
    looseness_moment: float = 5.0e4   # N*mm; looseness mostly closed by ~2x this
    psi: float = 2.7              # EN 1993-1-8 Table 6.8 shape factor
    hardening_ratio: float = 0.02  # post-F_Rd tangent / k_eff
    use_rotation_capacity: bool = False   # fail at theta = t_p / h_e


@dataclass
class Evaluation:
    gamma_M: float = 1.1          # EN 15512 partial factor for connections
    eta: float = 1.0              # design-moment reduction (<= 1)
    frame_braced: bool = False    # k_b = 8 braced, 25 unbraced (EN 1993-1-8 5.2.2.5)


# ============================================================
# 2. COMPONENTS
# ============================================================

@dataclass
class Component:
    code: str
    name: str
    k: float          # N/mm
    F_Rd: float       # N


@dataclass
class LipRow:
    index: int
    y_from_top: float
    z: float                      # lever arm to centre of compression
    components: List[Component]
    k_eff: float = 0.0
    F_Rd: float = 0.0
    F_u: float = 0.0
    governing: str = ""
    # tabulated force-deformation law
    _F: np.ndarray = field(default_factory=lambda: np.zeros(1), repr=False)
    _d: np.ndarray = field(default_factory=lambda: np.zeros(1), repr=False)

    def build_law(self, psi: float, hardening: float, fu_over_fy: float) -> None:
        inv = sum(1.0 / c.k for c in self.components)
        self.k_eff = 1.0 / inv
        gov = min(self.components, key=lambda c: c.F_Rd)
        self.F_Rd, self.governing = gov.F_Rd, f"{gov.code} {gov.name}"
        self.F_u = self.F_Rd * max(fu_over_fy, 1.0)

        F1 = np.linspace(0.0, self.F_Rd, 400)
        mu = np.where(F1 > 2.0 / 3.0 * self.F_Rd,
                      (1.5 * F1 / self.F_Rd) ** psi, 1.0)
        d1 = F1 * mu / self.k_eff
        F2 = np.linspace(self.F_Rd, self.F_u, 200)[1:]
        d2 = d1[-1] + (F2 - self.F_Rd) / (max(hardening, 1e-4) * self.k_eff)
        self._F = np.concatenate([F1, F2])
        self._d = np.concatenate([d1, d2])

    @property
    def d_u(self) -> float:
        return float(self._d[-1])

    def force(self, d: np.ndarray) -> np.ndarray:
        return np.interp(d, self._d, self._F)


# ============================================================
# 3. ENGINE
# ============================================================

class HookConnectorSPM:

    def __init__(self, material: Material, beam: BeamSection,
                 upright: UprightSection, connector: HookConnector,
                 comp: ComponentParameters, rig: TestRig,
                 load: LoadSchedule, nl: NonlinearOptions,
                 ev: Evaluation):
        self.mat, self.beam, self.up = material, beam, upright
        self.con, self.cp, self.rig = connector, comp, rig
        self.load, self.nl, self.ev = load, nl, ev

        bp = beam.properties()
        self.I_b, self.Wpl_b = bp["I"], bp["Wpl"]
        self.I_u = upright.I_bending()
        self.a = rig.load_arm_a

        self._build_rows()
        self._build_moment_rotation()

    # --------------------------------------------------------
    def _row_components(self) -> List[Component]:
        E, G, fy, fu = self.mat.E, self.mat.G, self.mat.fy, self.mat.fu
        cp, con, t_u = self.cp, self.con, self.up.thickness
        g0 = cp.gamma_M0

        b_h = cp.hook_width_bh or con.lip_height
        t_h = cp.hook_thickness_th or con.plate_thickness
        l_h = cp.hook_bending_length_lh
        I_h = b_h * t_h**3 / 12.0
        A_h = b_h * t_h
        b_l = cp.lip_eff_width_bl or con.pitch
        t_l = cp.lip_thickness_tl or con.plate_thickness

        return [
            Component("C2", "Hook bending",
                      3.0 * E * I_h / l_h**3,
                      fy * b_h * t_h**2 / 4.0 / l_h / g0),
            Component("C3", "Hook shear",
                      G * A_h / cp.hook_shear_length_Lh,
                      fy * A_h / np.sqrt(3.0) / g0),
            Component("C4", "Hook-upright bearing",
                      E * cp.bearing_width * t_u / cp.bearing_length,
                      2.5 * fu * cp.bearing_width * t_u / cp.gamma_M2),
            Component("C5", "Upright wall local",
                      E * cp.upright_eff_width_bu * t_u**3
                      / (4.0 * cp.upright_eff_length_Lu**3),
                      fy * cp.upright_eff_width_bu * t_u**2
                      / (4.0 * cp.upright_eff_length_Lu) / g0),
            Component("C6", "Connector lip bending",
                      E * b_l * t_l**3 / (4.0 * cp.lip_eff_length_Ll**3),
                      fy * b_l * t_l**2 / (4.0 * cp.lip_eff_length_Ll) / g0),
        ]

    def _build_rows(self) -> None:
        h_c = self.con.height
        self.rows: List[LipRow] = []
        for i, y in enumerate(self.con.lip_centres_from_top()):
            row = LipRow(index=i + 1, y_from_top=float(y), z=float(h_c - y),
                         components=self._row_components())
            row.build_law(self.nl.psi, self.nl.hardening_ratio,
                          self.mat.fu / self.mat.fy)
            self.rows.append(row)

        # C1 beam: whole-beam component (not a row spring)
        self.K1 = 3.0 * self.mat.E * self.I_b / self.a**3
        self.M_pl_beam = self.mat.fy * self.Wpl_b
        self.F1_Rd = self.M_pl_beam / self.a

        z = np.array([r.z for r in self.rows])
        k = np.array([r.k_eff for r in self.rows])
        F = np.array([r.F_Rd for r in self.rows])
        self.S_j_ini = float(np.sum(k * z**2))
        self.M_j_Rd = float(np.sum(F * z))
        self.z_eq = float(np.sum(k * z**2) / np.sum(k * z))
        self.k_eq = float(np.sum(k * z) / self.z_eq)

    # --------------------------------------------------------
    def _build_moment_rotation(self) -> None:
        """Tabulate M(theta) of the connection and find the failure point."""
        z = np.array([r.z for r in self.rows])
        theta_u_rows = min(r.d_u / r.z for r in self.rows)
        self.failure_mode = ("Row {} ({}) reached ultimate force".format(
            min(self.rows, key=lambda r: r.d_u / r.z).index,
            min(self.rows, key=lambda r: r.d_u / r.z).governing))
        self.theta_avail = self.con.plate_thickness / self.con.height
        theta_u = theta_u_rows
        if self.nl.use_rotation_capacity and self.theta_avail < theta_u:
            theta_u = self.theta_avail
            self.failure_mode = "Rotation capacity t_p / h_e exceeded"

        th = np.linspace(0.0, theta_u, 3000)
        M = np.zeros_like(th)
        for r in self.rows:
            M += r.z * r.force(r.z * th)
        self._th_tab, self._M_tab = th, M
        self.M_conn_u = float(M[-1])

        if self.M_pl_beam < self.M_conn_u:
            self.M_conn_u = self.M_pl_beam
            self.failure_mode = "Beam plastic moment reached"
        self.P_fail = self.M_conn_u / self.a

    def theta_connection(self, M: float) -> float:
        return float(np.interp(M, self._M_tab, self._th_tab))

    def theta_looseness(self, M: float) -> float:
        Ms = max(self.nl.looseness_moment, 1e-6)
        return self.nl.looseness_rad * (1.0 - np.exp(-(M / Ms) ** 2))

    def theta_upright(self, M: float) -> float:
        H, E, I = self.up.clamp_length, self.mat.E, self.I_u
        if self.up.end_fixity == "fixed-fixed":
            return M * H / (16.0 * E * I)
        if self.up.end_fixity == "pinned-pinned":
            return M * H / (12.0 * E * I)
        return 0.0

    def beam_deflection(self, P: float, x: float) -> float:
        """Elastic cantilever deflection at x (0 <= x) for load P at a."""
        E, I, a = self.mat.E, self.I_b, self.a
        if x <= a:
            return P * x**2 * (3.0 * a - x) / (6.0 * E * I)
        return P * a**2 * (3.0 * x - a) / (6.0 * E * I)

    # --------------------------------------------------------
    def run(self) -> Dict:
        inc = max(self.load.increment_kN * 1000.0, 1e-6)
        P_vals = np.arange(0.0, self.load.max_load_N + 0.5 * inc, inc)
        failed = False
        if self.load.stop_at_failure and self.P_fail < P_vals[-1]:
            P_vals = P_vals[P_vals < self.P_fail]
            P_vals = np.append(P_vals, self.P_fail)
            failed = True

        rng = np.random.default_rng(self.rig.seed)
        noise = self.rig.sensor_noise_mm
        x2, x3, a = self.rig.x_D2, self.rig.x_D3, self.a

        rec = {k: [] for k in (
            "step", "P", "M", "D1", "D2", "D3", "theta_meas", "theta_corr",
            "theta_conn", "theta_loose", "theta_up", "delta_beam_tip")}
        row_forces = {r.index: [] for r in self.rows}

        for i, P in enumerate(P_vals):
            M = P * a
            th_c = self.theta_connection(M)
            th_l = self.theta_looseness(M)
            th_u = self.theta_upright(M)
            th = th_c + th_l + th_u

            def disp(x):
                return th * x + self.beam_deflection(P, x)

            D1 = disp(a) + P / self.rig.load_train_stiffness
            D2, D3 = disp(x2), disp(x3)
            if noise > 0 and P > 0:
                D1 += rng.normal(0, noise)
                D2 += rng.normal(0, noise)
                D3 += rng.normal(0, noise)

            th_meas = (D3 - D2) / (x3 - x2)
            th_corr = th_meas - (self.beam_deflection(P, x3)
                                 - self.beam_deflection(P, x2)) / (x3 - x2)

            for k, v in zip(rec.keys(), (
                    i, P, M, D1, D2, D3, th_meas, th_corr,
                    th_c, th_l, th_u, self.beam_deflection(P, a))):
                rec[k].append(float(v))
            for r in self.rows:
                row_forces[r.index].append(float(r.force(r.z * th_c)))

        return self._summarize(rec, row_forces, failed)

    # --------------------------------------------------------
    @staticmethod
    def equal_area_stiffness(theta: np.ndarray, M: np.ndarray,
                             M_Rd: float) -> float:
        """EN 15512 style: slope k of a line through the origin that encloses
        equal areas with the M-theta curve up to M_Rd."""
        if M_Rd <= 0 or len(M) < 3:
            return float("nan")
        mask = M <= M_Rd
        th, m = theta[mask], M[mask]
        if len(th) < 2:
            return float("nan")
        th_d = float(np.interp(M_Rd, M, theta))
        th = np.append(th, th_d)
        m = np.append(m, M_Rd)
        area_curve = np.trapezoid(m, th) if hasattr(np, "trapezoid") \
            else np.trapz(m, th)
        # Equal areas between line and curve for 0 <= M <= M_Rd  <=>
        #   integral(theta_curve dM) = integral(M/k dM) = M_Rd^2 / (2k)
        # with integral(theta_curve dM) = M_Rd*th_d - integral(M dtheta).
        denom = 2.0 * (M_Rd * th_d - area_curve)
        return M_Rd**2 / denom if denom > 0 else float("nan")

    def _summarize(self, rec: Dict, row_forces: Dict, failed: bool) -> Dict:
        P = np.array(rec["P"])
        M = np.array(rec["M"])
        th = np.array(rec["theta_corr"])

        M_max = float(M.max())
        M_Rd = self.ev.eta * M_max / self.ev.gamma_M
        k_ti = self.equal_area_stiffness(th, M, M_Rd)

        # secant stiffness between 10 % and 40 % of M_max (drops looseness)
        lo, hi = 0.1 * M_max, 0.4 * M_max
        th_lo, th_hi = np.interp([lo, hi], M, th)
        k_secant = (hi - lo) / (th_hi - th_lo) if th_hi > th_lo else float("nan")

        EIb_Lb = self.mat.E * self.I_b / self.beam.span_for_classification
        kb = 8.0 if self.ev.frame_braced else 25.0
        S = self.S_j_ini
        if S <= 0.5 * EIb_Lb:
            cls = "Nominally pinned"
        elif S >= kb * EIb_Lb:
            cls = "Rigid"
        else:
            cls = "Semi-rigid"

        rows_table = []
        for r in self.rows:
            d = {"Lip": r.index, "y from top (mm)": r.y_from_top,
                 "z lever arm (mm)": r.z}
            for c in r.components:
                d[f"{c.code} k (N/mm)"] = c.k
            for c in r.components:
                d[f"{c.code} F_Rd (N)"] = c.F_Rd
            d["k_eff (N/mm)"] = r.k_eff
            d["F_Rd,row (N)"] = r.F_Rd
            d["Governing"] = r.governing
            rows_table.append(d)

        return {
            "record": rec,
            "row_forces": row_forces,
            "rows_table": rows_table,
            "failed": failed,
            "failure_mode": self.failure_mode,
            "P_fail_N": self.P_fail,
            "M_max_Nmm": M_max,
            "M_Rd_Nmm": M_Rd,
            "k_ti_Nmm_rad": k_ti,
            "k_secant_Nmm_rad": k_secant,
            "S_j_ini_Nmm_rad": self.S_j_ini,
            "M_j_Rd_Nmm": self.M_j_Rd,
            "z_eq_mm": self.z_eq,
            "k_eq_N_mm": self.k_eq,
            "K1_N_mm": self.K1,
            "F1_Rd_N": self.F1_Rd,
            "M_pl_beam_Nmm": self.M_pl_beam,
            "I_beam_mm4": self.I_b,
            "I_upright_mm4": self.I_u,
            "connector_height_mm": self.con.height,
            "lip_height_mm": self.con.lip_height,
            "theta_avail_rad": self.theta_avail,
            "classification": cls,
            "class_limits_Nmm_rad": (0.5 * EIb_Lb, kb * EIb_Lb),
            "total_steps": len(P),
        }
