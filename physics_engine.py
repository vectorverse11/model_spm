"""
Component-Method Physics Engine — Virtual Beam-End-Connector (Hook) Test SPM
===========================================================================

Virtual replica of the cantilever beam-end-connector test rig used for steel
storage racking (EN 15512 Annex A "beam end connector test"):

    * an 800 mm upright is clamped in the frame,
    * a 500 mm beam stub with a welded hook connector is hooked into the
      upright slots,
    * a hydraulic piston pushes the beam DOWN at a = 400 mm from the upright
      face in small load steps (0.01 / 0.02 kN) until the maximum deflection
      is reached,
    * three dial / displacement sensors are recorded from 0 kN:
          Dial 1 (D1) = piston displacement               (x = a  = 400 mm)
          Dial 2 (D2) = beam deflection near connector    (x = x2 =  40 mm)
          Dial 3 (D3) = beam deflection further out       (x = x3 = 140 mm)
      and the connector rotation is  theta = (D3 - D2) / (x3 - x2).

The connection is decomposed into components following the EN 1993-1-8
component method (as for bolted end-plate joints) with the bolt rows replaced
by hook ("lip") rows:

    C1  beam flexure                     K1 = 3 E I_b / a^3          (whole beam)
    C2  hook (lip) bending               K2 = 3 E I_h / l_h^3        (per lip)
    C3  hook (lip) shear                 K3 = G A_h / L_h            (per lip)
    C4  hook-to-upright bearing          K4 = E b_brg t_u / L_brg    (per lip)
    C5  upright wall local deformation   K5 = E b_u t_u^3 / (4 L_u^3)(per lip)
    C6  connector lip (plate) bending    K6 = E b_l t_l^3 / (4 L_l^3)(per lip)

For every lip row r in tension the springs C2..C6 act in series:
    k_eff,r = 1 / (1/K2 + 1/K3 + 1/K4 + 1/K5 + 1/K6)
    F_Rd,r  = min(F2,Rd ... F6,Rd)
Rows are assembled about the centre of compression, taken at the bottom
edge of the connector (downward load: the top lips pull out, the connector
bottom bears on the upright), with lever arms z_r = h_c - y_r:
    S_j,ini = sum(k_eff,r * z_r^2)          (EN 1993-1-8 6.3 with k in N/mm)
    M_j,Rd  = sum(F_Rd,r * z_r)             (plastic row distribution)
Row non-linearity uses the EN 1993-1-8 6.3.1(6) stiffness ratio
    mu = (1.5 F / F_Rd)^psi   for 2/3 F_Rd < F <= F_Rd,
followed by linear strain hardening up to F_u,r = F_Rd,r * fu / fy and a
plastic plateau beyond. Once the moment capacity is reached the load stays
at its peak while the deflection grows, until the maximum deflection stops
the test (as on the physical machine).

All units: N, mm, MPa (N/mm^2), rad.
"""

from dataclasses import dataclass, field
from typing import Dict, List, Optional

import numpy as np


# ============================================================
# 1. INPUT STRUCTURES
# ============================================================

@dataclass
class Material:
    """Steel. Only the elastic constants have defaults (E = 210000 N/mm^2,
    nu = 0.3 -> G = 80769 N/mm^2); fy and fu must be supplied by the user."""
    fy: float                    # N/mm^2, no default
    fu: float                    # N/mm^2, no default
    E: float = 210000.0          # N/mm^2
    nu: float = 0.3
    name: str = "Steel"

    @property
    def G(self) -> float:
        return self.E / (2.0 * (1.0 + self.nu))   # 80769 N/mm^2 for defaults


@dataclass
class BeamSection:
    """Beam stub welded to the connector. Section data has no defaults."""
    section_type: str            # "box" | "solid_rect" | "custom"
    depth: float                 # h_b (mm)
    width: Optional[float] = None       # b (mm), box / solid_rect
    thickness: Optional[float] = None   # wall thickness, box only (mm)
    I_custom: Optional[float] = None    # mm^4, custom only
    Wpl_custom: Optional[float] = None  # mm^3, custom only
    length: float = 500.0        # stub length from upright face (mm)
    span_for_classification: Optional[float] = None   # rack beam span L_b

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
    """Perforated open (lipped channel) upright. Section data has no defaults."""
    face_width: float            # slotted face width (mm)
    depth: float                 # side-wall depth (mm)
    lip: float                   # return lip (mm)
    thickness: float             # t_u (mm)
    perforation_factor: float = 1.0    # I_net / I_gross (1.0 = gross section)
    I_custom: Optional[float] = None   # overrides computed I if given
    clamp_length: float = 800.0  # full upright length in the rig (mm)
    # Global upright bending is not part of the handwritten C1-C6 method:
    # "rigid" (default) ignores it; "fixed-fixed" / "pinned-pinned" add it.
    end_fixity: str = "rigid"

    def I_bending(self) -> float:
        """Second moment about the axis parallel to the slotted face
        (bending in the plane of the beam), thin-walled segment model."""
        if self.I_custom:
            return self.I_custom
        B, D, c, t = self.face_width, self.depth, self.lip, self.thickness
        # y measured perpendicular to the face (face at y = 0)
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
    """Hook connector ("lip") geometry — fixed product data.

        5 lips -> 245 mm, 4 lips -> 195 mm, 3 lips -> 145 mm
        width 44 mm, hole top-edge 10.3 mm from top, 34.7 mm bottom end
        distance, pitch 50 mm, first lip centre 25.1 mm from top,
        plate thickness t_p = 4 mm.
    """
    n_lips: int = 5
    width: float = 44.0
    plate_thickness: float = 4.0  # t_p (mm)
    pitch: float = 50.0
    top_end_distance: float = 10.3
    bottom_end_distance: float = 34.7
    first_lip_centre: float = 25.1

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
    """Effective lengths/widths of the hand-written derivation (per lip row).
    These cannot be measured directly; they are estimates to be calibrated
    against a physical test of the same connector."""
    # C2 hook bending:  K2 = 3 E I_h / l_h^3, I_h = b_h t_h^3 / 12
    hook_width_bh: Optional[float] = None      # None -> connector.lip_height
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
    gamma_M0: float = 1.0        # partial factor on component resistances
    gamma_M2: float = 1.25       # bearing partial factor


@dataclass
class TestRig:
    __test__ = False   # not a pytest test class
    max_deflection_mm: float                 # test stops when reached (required)
    stop_sensor: str = "D1"                  # sensor checked against the limit
    load_arm_a: float = 400.0                # piston distance from upright face
    x_D2: float = 40.0
    x_D3: float = 140.0
    load_train_stiffness: float = float("inf")  # N/mm, piston compliance (D1 only); off
    sensor_noise_mm: float = 0.0
    seed: int = 1


@dataclass
class LoadSchedule:
    increment_kN: float = 0.01    # 0.01 or 0.02 kN per step
    time_per_step_s: float = 0.02
    dial_resolution_mm: float = 0.01


@dataclass
class NonlinearOptions:
    looseness_rad: float = 0.0    # extra, not in C1-C6 method (EN 15512 A.2.5)
    looseness_moment: float = 5.0e4   # N*mm; looseness mostly closed by ~2x this
    psi: float = 2.7              # EN 1993-1-8 Table 6.8 shape factor
    hardening_ratio: float = 0.02  # post-F_Rd tangent / k_eff


@dataclass
class Evaluation:
    gamma_M: float = 1.1          # EN 15512 partial factor for connections
    eta: float = 1.0              # design-moment reduction (<= 1)
    frame_braced: bool = False    # k_b = 8 braced, 25 unbraced (EN 1993-1-8 5.2.2.5)
    stiffness_modification: float = 2.0  # eta: S_j = S_j,ini / eta (EN 1993-1-8 5.1.2)


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
    _F: np.ndarray = field(default_factory=lambda: np.zeros(1), repr=False)
    _d: np.ndarray = field(default_factory=lambda: np.zeros(1), repr=False)

    @property
    def in_tension(self) -> bool:
        return self.z > 0.0

    def build_law(self, psi: float, hardening: float, fu_over_fy: float) -> None:
        self.k_eff = 1.0 / sum(1.0 / c.k for c in self.components)
        gov = min(self.components, key=lambda c: c.F_Rd)
        self.F_Rd, self.governing = gov.F_Rd, f"{gov.code} {gov.name}"
        self.F_u = self.F_Rd * max(fu_over_fy, 1.0)

        F1 = np.linspace(0.0, self.F_Rd, 400)
        mu = np.where(F1 > 2.0 / 3.0 * self.F_Rd,
                      (1.5 * F1 / self.F_Rd) ** psi, 1.0)
        d1 = F1 * mu / self.k_eff
        F2 = np.linspace(self.F_Rd, self.F_u, 200)[1:]
        d2 = d1[-1] + (F2 - self.F_Rd) / (max(hardening, 1e-4) * self.k_eff)
        # np.interp clamps beyond the last point -> plastic plateau at F_u
        self._F = np.concatenate([F1, F2])
        self._d = np.concatenate([d1, d2])

    @property
    def d_u(self) -> float:
        return float(self._d[-1])

    def force(self, d):
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

    @property
    def compression_centre_from_top(self) -> float:
        """Downward load: top lips pull out and the connector bottom edge
        bears on the upright, so rotation is about the connector bottom."""
        return self.con.height

    def _build_rows(self) -> None:
        y_c = self.compression_centre_from_top
        self.rows: List[LipRow] = []
        for i, y in enumerate(self.con.lip_centres_from_top()):
            row = LipRow(index=i + 1, y_from_top=float(y), z=float(y_c - y),
                         components=self._row_components())
            row.build_law(self.nl.psi, self.nl.hardening_ratio,
                          self.mat.fu / self.mat.fy)
            self.rows.append(row)
        self.t_rows = [r for r in self.rows if r.in_tension]
        if not self.t_rows:
            raise ValueError("No lip row lies above the centre of compression.")

        # C1 beam: whole-beam component (not a row spring)
        self.K1 = 3.0 * self.mat.E * self.I_b / self.a**3
        self.M_pl_beam = self.mat.fy * self.Wpl_b
        self.F1_Rd = self.M_pl_beam / self.a

        z = np.array([r.z for r in self.t_rows])
        k = np.array([r.k_eff for r in self.t_rows])
        F = np.array([r.F_Rd for r in self.t_rows])
        self.S_j_ini = float(np.sum(k * z**2))
        self.M_j_Rd = float(np.sum(F * z))
        self.z_eq = float(np.sum(k * z**2) / np.sum(k * z))
        self.k_eq = float(np.sum(k * z) / self.z_eq)

    # --------------------------------------------------------
    def _build_moment_rotation(self) -> None:
        """Tabulate M(theta) up to the rotation at which every tension row has
        reached F_u, i.e. the connection moment capacity."""
        theta_all = max(r.d_u / r.z for r in self.t_rows)
        th = np.linspace(0.0, theta_all, 4000)
        M = np.zeros_like(th)
        for r in self.t_rows:
            M += r.z * r.force(r.z * th)
        self._th_tab, self._M_tab = th, M
        self.M_conn_u = float(M[-1])

        first = min(self.t_rows, key=lambda r: r.d_u / r.z)
        self.theta_first_row_u = first.d_u / first.z
        self.first_row_msg = f"Lip {first.index} ({first.governing})"

        if self.M_pl_beam < self.M_conn_u:
            self.M_cap = self.M_pl_beam
            self.cap_mode = "Beam plastic moment M_pl reached"
            self.cap_in_connection = False
        else:
            self.M_cap = self.M_conn_u
            self.cap_mode = "Connection capacity reached (all tension lips at F_u)"
            self.cap_in_connection = True
        self.P_cap = self.M_cap / self.a
        self.theta_avail = self.con.plate_thickness / self.con.height

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
        """Elastic cantilever deflection at x for load P at a."""
        E, I, a = self.mat.E, self.I_b, self.a
        if x <= a:
            return P * x**2 * (3.0 * a - x) / (6.0 * E * I)
        return P * a**2 * (3.0 * x - a) / (6.0 * E * I)

    # --------------------------------------------------------
    def _state(self, P: float, extra_theta: float = 0.0) -> Dict[str, float]:
        """Absolute (un-zeroed) response at load P. ``extra_theta`` is the
        additional plastic rotation at constant load after the peak."""
        M = P * self.a
        th_c = self.theta_connection(M)
        if self.cap_in_connection:
            th_c += extra_theta
        th_hinge = 0.0 if self.cap_in_connection else extra_theta
        th = th_c + th_hinge + self.theta_looseness(M) + self.theta_upright(M)

        def disp(x):
            return th * x + self.beam_deflection(P, x)

        return {"P": P, "M": M, "theta_conn": th_c,
                "D1": disp(self.a) + P / self.rig.load_train_stiffness,
                "D2": disp(self.rig.x_D2), "D3": disp(self.rig.x_D3)}

    def run(self) -> Dict:
        inc = max(self.load.increment_kN * 1000.0, 1e-6)
        d_max = self.rig.max_deflection_mm
        key = self.rig.stop_sensor
        x_stop = {"D1": self.a, "D2": self.rig.x_D2, "D3": self.rig.x_D3}[key]

        def reading(s):
            return s[key]

        states: List[Dict[str, float]] = []
        stop_reason = None

        def stop_between(lo, hi):
            """Load in (lo, hi] at which the stop sensor reads exactly d_max."""
            for _ in range(60):
                mid = 0.5 * (lo + hi)
                lo, hi = (mid, hi) if reading(self._state(mid)) < d_max else (lo, mid)
            return self._state(hi)

        # ---- Phase 1: load-controlled increments from 0 kN up to the peak ----
        P = 0.0
        while True:
            P_step = min(P, self.P_cap)
            s = self._state(P_step)
            if reading(s) >= d_max:
                lo = states[-1]["P"] if states else 0.0
                states.append(stop_between(lo, P_step) if P_step > lo else s)
                stop_reason = f"Maximum deflection {d_max:g} mm reached on {key}"
                break
            if P_step >= self.P_cap:
                break
            states.append(s)
            P += inc
        self.peak_reached = stop_reason is None

        # ---- Phase 2: load held at peak, deflection runs to the limit ----
        if self.peak_reached:
            s = self._state(self.P_cap)
            states.append(s)
            step = max(self.load.dial_resolution_mm, 1e-4)
            n_needed = max(0.0, d_max - reading(s)) / step
            n_steps = int(np.ceil(min(n_needed, 20000)))
            d_theta = step / x_stop
            for n in range(1, n_steps + 1):
                s = self._state(self.P_cap, n * d_theta)
                if reading(s) >= d_max:
                    extra = (n - 1) * d_theta + (d_max - reading(states[-1])) / x_stop
                    s = self._state(self.P_cap, extra)
                    states.append(s)
                    break
                states.append(s)
            stop_reason = (f"{self.cap_mode}; load held at peak until maximum "
                           f"deflection {d_max:g} mm reached on {key}")

        return self._summarize(states, stop_reason)

    # --------------------------------------------------------
    @staticmethod
    def equal_area_stiffness(theta: np.ndarray, M: np.ndarray,
                             M_Rd: float) -> float:
        """EN 15512 style: slope k of a line through the origin that encloses
        equal areas with the M-theta curve up to M_Rd."""
        if M_Rd <= 0 or len(M) < 3 or M.max() < M_Rd:
            return float("nan")
        i_end = int(np.argmax(M >= M_Rd))
        th = np.append(theta[:i_end], np.interp(M_Rd, M[:i_end + 1], theta[:i_end + 1]))
        m = np.append(M[:i_end], M_Rd)
        trapz = np.trapezoid if hasattr(np, "trapezoid") else np.trapz
        area_curve = trapz(m, th)
        # Equal areas between line and curve for 0 <= M <= M_Rd  <=>
        #   integral(theta_curve dM) = integral(M/k dM) = M_Rd^2 / (2k)
        # with integral(theta_curve dM) = M_Rd*th_end - integral(M dtheta).
        denom = 2.0 * (M_Rd * th[-1] - area_curve)
        return M_Rd**2 / denom if denom > 0 else float("nan")

    def _summarize(self, states: List[Dict[str, float]], stop_reason: str) -> Dict:
        rng = np.random.default_rng(self.rig.seed)
        noise = self.rig.sensor_noise_mm
        x2, x3 = self.rig.x_D2, self.rig.x_D3

        rec = {k: [] for k in ("step", "time_s", "P", "M", "D1", "D2", "D3",
                               "theta_meas", "theta_corr", "theta_conn")}
        row_forces = {r.index: [] for r in self.rows}
        for i, s in enumerate(states):
            D = {k: s[k] for k in ("D1", "D2", "D3")}
            if noise > 0 and i > 0:
                D = {k: v + rng.normal(0, noise) for k, v in D.items()}
            th_meas = (D["D3"] - D["D2"]) / (x3 - x2)
            th_corr = th_meas - (self.beam_deflection(s["P"], x3)
                                 - self.beam_deflection(s["P"], x2)) / (x3 - x2)
            for k, v in (("step", i), ("time_s", i * self.load.time_per_step_s),
                         ("P", s["P"]), ("M", s["M"]), ("D1", D["D1"]),
                         ("D2", D["D2"]), ("D3", D["D3"]),
                         ("theta_meas", th_meas), ("theta_corr", th_corr),
                         ("theta_conn", s["theta_conn"])):
                rec[k].append(float(v))
            for r in self.rows:
                f = float(r.force(r.z * s["theta_conn"])) if r.in_tension else 0.0
                row_forces[r.index].append(f)

        M = np.array(rec["M"])
        th = np.array(rec["theta_corr"])

        M_max = float(M.max())
        M_Rd = self.ev.eta * M_max / self.ev.gamma_M
        k_ti = self.equal_area_stiffness(th, M, M_Rd)

        lo, hi = 0.1 * M_max, 0.4 * M_max
        i_pk = int(np.argmax(M))
        th_lo, th_hi = np.interp([lo, hi], M[:i_pk + 1], th[:i_pk + 1])
        k_secant = (hi - lo) / (th_hi - th_lo) if th_hi > th_lo else float("nan")

        cls, class_limits = "— (enter rack beam span L_b)", None
        if self.beam.span_for_classification:
            EIb_Lb = self.mat.E * self.I_b / self.beam.span_for_classification
            kb = 8.0 if self.ev.frame_braced else 25.0
            class_limits = (0.5 * EIb_Lb, kb * EIb_Lb)
            if self.S_j_ini <= class_limits[0]:
                cls = "Nominally pinned"
            elif self.S_j_ini >= class_limits[1]:
                cls = "Rigid"
            else:
                cls = "Semi-rigid"

        ratio = self.M_j_Rd / self.M_pl_beam
        if ratio <= 0.25:
            cls_strength = "Nominally pinned"
        elif ratio >= 1.0:
            cls_strength = "Full-strength"
        else:
            cls_strength = "Partial-strength"

        rows_table = []
        for r in self.rows:
            d = {"Lip": r.index, "y from top (mm)": r.y_from_top,
                 "z lever arm (mm)": r.z,
                 "State": "tension" if r.in_tension else "compression zone"}
            for c in r.components:
                d[f"{c.code} k (N/mm)"] = c.k
            for c in r.components:
                d[f"{c.code} F_Rd (N)"] = c.F_Rd
            d["k_eff (N/mm)"] = r.k_eff
            d["F_Rd,row (N)"] = r.F_Rd
            d["Governing"] = r.governing
            rows_table.append(d)

        # ---- Component table (Stiffness | Resistance | Deformation), as in the
        # hand-written table. C2..C6 are reported for the most loaded (top) lip:
        # all springs in a row carry the same force F, elastic deformation of
        # each is F / K_i and any plastic part is assigned to the governing one.
        P_pk = float(max(rec["P"]))
        top = max(self.t_rows, key=lambda r: r.z)
        F_top = row_forces[top.index][-1]
        d_row = top.z * rec["theta_conn"][-1]
        d_el = {c.code: F_top / c.k for c in top.components}
        d_pl = max(0.0, d_row - sum(d_el.values()))
        gov_code = top.governing.split()[0]
        component_table = [{
            "Component": "C1 Beam flexure", "Stiffness K (N/mm)": self.K1,
            "Resistance F_Rd (N)": self.F1_Rd, "Force at peak (N)": P_pk,
            "Deformation δ at peak (mm)": P_pk / self.K1,
            "Yielded?": P_pk > self.F1_Rd}]
        for c in top.components:
            component_table.append({
                "Component": f"{c.code} {c.name} (lip {top.index})",
                "Stiffness K (N/mm)": c.k, "Resistance F_Rd (N)": c.F_Rd,
                "Force at peak (N)": F_top,
                "Deformation δ at peak (mm)": d_el[c.code]
                + (d_pl if c.code == gov_code else 0.0),
                "Yielded?": F_top > c.F_Rd})

        theta_max = float(np.max(rec["theta_corr"]))
        return {
            "record": rec,
            "row_forces": row_forces,
            "rows_table": rows_table,
            "component_table": component_table,
            "stop_reason": stop_reason,
            "peak_reached": self.peak_reached,
            "P_cap_N": self.P_cap,
            "P_max_N": float(max(rec["P"])),
            "first_row_ultimate": self.first_row_msg,
            "M_max_Nmm": M_max,
            "M_Rd_Nmm": M_Rd,
            "k_ti_Nmm_rad": k_ti,
            "k_secant_Nmm_rad": k_secant,
            "S_j_ini_Nmm_rad": self.S_j_ini,
            "S_j_ideal_Nmm_rad": self.S_j_ini / self.ev.stiffness_modification,
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
            "compression_centre_mm": self.compression_centre_from_top,
            "theta_avail_rad": self.theta_avail,
            "theta_max_rad": theta_max,
            "rotation_capacity_exceeded": theta_max > self.theta_avail,
            "classification": cls,
            "strength_classification": cls_strength,
            "class_limits_Nmm_rad": class_limits,
            "total_steps": len(rec["P"]),
        }
