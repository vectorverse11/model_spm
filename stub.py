"""
Virtual stub column compression test (EN 15512 Annex A.2.1)
===========================================================

Section: lipped channel upright (lip = 0 gives a plain channel), perforated.
All dimensions, f_y and the test settings are entered by the user.
Fixed values (steel): E = 210000 N/mm^2, G = 80769 N/mm^2, nu = 0.3.

Method: Effective Width Method (EN 1993-1-3 / EN 1993-1-5 §4.4) for local
buckling + perforations, and EN 1993-1-1 §6.3.1 / EN 1993-1-3 §6.2.3 for
flexural and torsional-flexural buckling of the stub.

1. Section properties (centreline model, square corners)
       web b_w = W - t, flange b_f = D - t (D - t/2 without lip), lip b_l = d_l - t/2
       gross: A_g, centroid, I, J = sum b t^3 / 3, shear centre, warping constant I_w
       net (minimum): holes removed from the centre of the web and of each flange

2. Effective width at a compressive stress sigma (psi = 1, uniform compression)
       lambda_p = (b/t) / (28.4 eps sqrt(k_sigma)) * sqrt(sigma / f_y),  eps = sqrt(235/f_y)
       internal (web; flange with lip):   k_sigma = 4,    rho = (lambda_p - 0.22) / lambda_p^2 <= 1
       outstand (lip; flange w/o lip):    k_sigma = 0.43, rho = (lambda_p - 0.188) / lambda_p^2 <= 1
       internal: effective strips 0.5 rho b at both edges; outstand: rho b from the supported edge
       a central hole of width n*d removes only the part that falls inside the effective strips.

3. Failure load
       N_cr from flexural (L_F) and torsional / torsional-flexural (L_T) buckling
           Alternative 1: L_F = b (between bearings),  L_T = c/2
           Alternative 2: L_F = L_T = c (full cold-formed length; the c/2 rule is not used)
       lambda_bar = sqrt(A_eff f_y / N_cr),  chi from buckling curve b (alpha = 0.34),
       chi = 1 when lambda_bar <= 0.2
       Alternative 1 (ball bearings): load position between the gross and the net centroid;
           e = x_load - x_eff,  N_u = 1 / (1/(chi A_eff f_y) + |e| / (W_eff f_y)).
           The position is swept to give the maximum failure load.
       Alternative 2 (clamped platen): concentric, N_u = chi A_eff f_y.
       Alternative 3 (CUFSM + DSM): finite strip signature curve -> sigma_crl (and sigma_crd);
           Direct Strength Method (AISI S100) with net-section caps:
           P_ne (global, L = c), P_nl (local), P_nd (distortional, optional);
           P_n = P_nl  or  min(P_nl, P_nd).  Concentric load.

4. Load - shortening (load in steps from 0 kN up to the failure load)
       sigma = N / A_eff(sigma) (edge stress, iterated),  delta = N c / (E A_eff(sigma))
       dial reading = delta / least count
       proof load = load at which the first plate element starts to buckle locally (rho < 1)

5. Results as in EN 15512 A.2.1.4
       R_k = failure load,  A_eff = R_k / f_y  (if lambda_bar > 0.2: chi(A_eff) A_eff f_y = R_k)
       N_b,Rd = R_k / gamma_M0
"""

from dataclasses import dataclass
from math import pi, sqrt
from typing import Dict, List, Optional, Tuple

import numpy as np

import fsm

E = 210000.0                    # N/mm^2
NU = 0.3
G = E / (2.0 * (1.0 + NU))      # 80769 N/mm^2
ALPHA_B = 0.34                  # buckling curve b (EN 1993-1-3 Table 6.3, lipped channel)


@dataclass
class StubInputs:
    W: float            # width of the upright (web), mm
    D: float            # depth of the upright (flanges), mm
    t: float            # thickness, mm
    lip: float          # lip length, mm (0 = no lip)
    pitch: float        # perforation pitch, mm
    n_web: int          # holes across the web in one perforation row
    d_web: float        # width of one web hole across the web, mm
    n_fl: int           # holes across each flange in one row
    d_fl: float         # width of one flange hole across the flange, mm
    c: float            # length of the cold-formed section, mm
    cap_L: float        # cap plate length, mm
    cap_W: float        # cap plate width, mm
    cap_t: float        # cap plate thickness, mm
    base_L: float       # base plate length, mm
    base_W: float       # base plate width, mm
    base_t: float       # base plate thickness, mm
    fy: float           # yield stress, N/mm^2
    gamma_M0: float     # partial factor
    alternative: int    # 1 = ball bearings, 2 = clamped platen, 3 = CUFSM + DSM
    least_count: float  # dial gauge, mm per division
    distortional: bool = False  # Alternative 3: include DSM distortional strength
    cg_x: Optional[float] = None  # user CG (mm from web centreline); None = standard formula


# ------------------------------------------------------------------ geometry

def widths(inp: StubInputs) -> Dict[str, float]:
    t = inp.t
    has_lip = inp.lip > 0
    return {"web": inp.W - t,
            "flange": inp.D - t if has_lip else inp.D - t / 2.0,
            "lip": inp.lip - t / 2.0 if has_lip else 0.0}


def nodes(inp: StubInputs) -> np.ndarray:
    """Centreline nodes: lip tip, flange corner, web corner, web corner, flange corner, lip tip.
    Web on x = 0, flanges towards +x, symmetric about y = 0."""
    b = widths(inp)
    h, bf, bl = b["web"] / 2.0, b["flange"], b["lip"]
    pts = [(0.0, -h), (0.0, h)]
    pts = [(bf, -h)] + pts + [(bf, h)]
    if bl > 0:
        pts = [(bf, -h + bl)] + pts + [(bf, h - bl)]
    return np.array(pts, dtype=float)


def buckling_length_b(inp: StubInputs) -> float:
    """b = distance between the bearings = c + 2 (cap plate t + base plate t)."""
    return inp.c + 2.0 * (inp.cap_t + inp.base_t)


def _seg_int(fi, fj, gi, gj, L, t):
    """Integral of the product of two linear functions over a segment."""
    return L * t * (2 * fi * gi + fi * gj + fj * gi + 2 * fj * gj) / 6.0


def gross_properties(inp: StubInputs) -> Dict[str, float]:
    """Thin-walled open-section properties (centreline, single branch)."""
    P, t = nodes(inp), inp.t
    segs = [(P[k], P[k + 1]) for k in range(len(P) - 1)]
    Ls = [float(np.hypot(*(b - a))) for a, b in segs]
    A = sum(Ls) * t
    xc = sum(L * t * (a[0] + b[0]) / 2 for (a, b), L in zip(segs, Ls)) / A
    yc = sum(L * t * (a[1] + b[1]) / 2 for (a, b), L in zip(segs, Ls)) / A
    Q = P - np.array([xc, yc])                        # centroidal coordinates
    Ix = sum(_seg_int(Q[k, 1], Q[k + 1, 1], Q[k, 1], Q[k + 1, 1], Ls[k], t) for k in range(len(Ls)))
    Iy = sum(_seg_int(Q[k, 0], Q[k + 1, 0], Q[k, 0], Q[k + 1, 0], Ls[k], t) for k in range(len(Ls)))
    J = sum(Ls) * t**3 / 3.0

    def omega(pole):
        w = [0.0]
        for k in range(len(Ls)):
            (xi, yi), (xj, yj) = Q[k] - pole, Q[k + 1] - pole
            w.append(w[-1] + xi * yj - xj * yi)
        return np.array(w)

    def integ(f, g):
        return sum(_seg_int(f[k], f[k + 1], g[k], g[k + 1], Ls[k], t) for k in range(len(Ls)))

    one = np.ones(len(P))
    w0, wx, wy = omega(np.zeros(2)), omega(np.array([1.0, 0])), omega(np.array([0, 1.0]))
    a_x, a_y = wx - w0, wy - w0                       # omega is linear in the pole position

    def centred(w):
        return w - integ(w, one) / A

    w0c, axc, ayc = centred(w0), centred(a_x), centred(a_y)
    X, Y = Q[:, 0], Q[:, 1]
    M = np.array([[integ(axc, X), integ(ayc, X)], [integ(axc, Y), integ(ayc, Y)]])
    rhs = -np.array([integ(w0c, X), integ(w0c, Y)])
    xs, ys = np.linalg.solve(M, rhs)                  # shear centre (centroidal coordinates)
    ws = w0c + xs * axc + ys * ayc
    Iw = integ(ws, ws)
    return {"A": A, "xc": xc, "yc": yc, "Ix": Ix, "Iy": Iy, "J": J,
            "xs": xs, "ys": ys, "Iw": Iw,
            "x0": xs, "y0": ys,                       # shear centre relative to centroid
            "i0_sq": (Ix + Iy) / A + xs**2 + ys**2}


def net_area(inp: StubInputs) -> Tuple[float, float, float]:
    """A_net, x of net centroid, hole area. Web holes at x = 0, flange holes at mid-flange."""
    g = gross_properties(inp)
    b = widths(inp)
    A_web_h = inp.n_web * inp.d_web * inp.t
    A_fl_h = 2 * inp.n_fl * inp.d_fl * inp.t
    A_net = g["A"] - A_web_h - A_fl_h
    x_net = (g["A"] * g["xc"] - A_web_h * 0.0 - A_fl_h * b["flange"] / 2.0) / A_net
    return A_net, x_net, A_web_h + A_fl_h


# ------------------------------------------------------- effective widths

def rho_of(b: float, t: float, k_sigma: float, internal: bool, sigma: float, fy: float):
    eps = sqrt(235.0 / fy)
    lam = (b / t) / (28.4 * eps * sqrt(k_sigma)) * sqrt(max(sigma, 1e-9) / fy)
    if internal:
        rho = 1.0 if lam <= 0.673 else (lam - 0.22) / lam**2
    else:
        rho = 1.0 if lam <= 0.748 else (lam - 0.188) / lam**2
    return min(rho, 1.0), lam


def elements(inp: StubInputs) -> List[Dict]:
    b = widths(inp)
    has_lip = inp.lip > 0
    el = [{"name": "Web", "b": b["web"], "internal": True, "k": 4.0,
           "hole": inp.n_web * inp.d_web, "count": 1},
          {"name": "Flange", "b": b["flange"], "internal": has_lip,
           "k": 4.0 if has_lip else 0.43, "hole": inp.n_fl * inp.d_fl, "count": 2}]
    if has_lip:
        el.append({"name": "Lip", "b": b["lip"], "internal": False, "k": 0.43,
                   "hole": 0.0, "count": 2})
    return el


def _strips(b: float, rho: float, internal: bool, hole: float) -> List[Tuple[float, float]]:
    """Effective parts of an element as (s_start, s_end) from its first edge; a central hole
    of width `hole` removes only the part that overlaps them."""
    if internal:
        parts = [(0.0, 0.5 * rho * b), (b - 0.5 * rho * b, b)]
    else:
        parts = [(0.0, rho * b)]                      # from the supported edge
    h0, h1 = (b - hole) / 2.0, (b + hole) / 2.0
    out = []
    for s0, s1 in parts:
        for a, z in ((s0, min(s1, h0)), (max(s0, h1), s1)):
            if z - a > 1e-12:
                out.append((a, z))
    return out


def effective_section(inp: StubInputs, sigma: float) -> Dict:
    """A_eff, x_eff (centroid on the symmetry axis), I_eff about the axis parallel to the web."""
    t, fy = inp.t, inp.fy
    b = widths(inp)
    h, bf, bl = b["web"] / 2.0, b["flange"], b["lip"]
    rows, pieces = [], []                             # pieces: (length, x_start, x_end)
    for e in elements(inp):
        rho, lam = rho_of(e["b"], t, e["k"], e["internal"], sigma, fy)
        st = _strips(e["b"], rho, e["internal"], e["hole"])
        beff = sum(z - a for a, z in st)
        rows.append({**e, "rho": rho, "lambda_p": lam, "b_eff": beff})
        for a, z in st:
            if e["name"] == "Web":                    # along y at x = 0
                pieces += [(z - a, 0.0, 0.0)]
            elif e["name"] == "Flange":               # from the web corner (x = 0) to x = bf
                pieces += [(z - a, a, z)] * 2
            else:                                     # lip, at x = bf
                pieces += [(z - a, bf, bf)] * 2
    A = sum(L * t for L, _, _ in pieces)
    x = sum(L * t * (x0 + x1) / 2 for L, x0, x1 in pieces) / A
    I = sum(L * t * (((x0 - x)**2 + (x0 - x) * (x1 - x) + (x1 - x)**2) / 3.0)
            for L, x0, x1 in pieces)
    c_max = max(x, bf - x)
    return {"A_eff": A, "x_eff": x, "I_eff": I, "W_eff": I / c_max, "elements": rows}


# ------------------------------------------------------- global buckling

def chi_of(lam_bar: float) -> float:
    if lam_bar <= 0.2:
        return 1.0
    phi = 0.5 * (1 + ALPHA_B * (lam_bar - 0.2) + lam_bar**2)
    return min(1.0, 1.0 / (phi + sqrt(phi**2 - lam_bar**2)))


def critical_loads(inp: StubInputs) -> Dict[str, float]:
    g = gross_properties(inp)
    b = buckling_length_b(inp)
    L_F, L_T = (b, inp.c / 2.0) if inp.alternative == 1 else (inp.c, inp.c)   # Alt 2 and 3: c
    Nx = pi**2 * E * g["Ix"] / L_F**2                 # bending about x (symmetry axis)
    Ny = pi**2 * E * g["Iy"] / L_F**2                 # bending about y (parallel to web)
    NT = (G * g["J"] + pi**2 * E * g["Iw"] / L_T**2) / g["i0_sq"]
    x0, y0, r2 = g["x0"], g["y0"], g["i0_sq"]
    # r0^2 (N-Nx)(N-Ny)(N-NT) - N^2 y0^2 (N-Nx) - N^2 x0^2 (N-Ny) = 0
    p = np.poly1d([1, -Nx]) * np.poly1d([1, -Ny]) * np.poly1d([1, -NT]) * r2 \
        - np.poly1d([1, 0, 0]) * y0**2 * np.poly1d([1, -Nx]) \
        - np.poly1d([1, 0, 0]) * x0**2 * np.poly1d([1, -Ny])
    roots = [r.real for r in p.r if abs(r.imag) < 1e-6 * max(1.0, abs(r)) and r.real > 0]
    NTF = min(roots)
    return {"L_F": L_F, "L_T": L_T, "N_cr_x": float(Nx), "N_cr_y": float(Ny),
            "N_cr_T": float(NT), "N_cr_TF": float(NTF), "N_cr": float(min(Nx, Ny, NTF))}


# ------------------------------------------------------- virtual test

def specimen_checks(inp: StubInputs) -> List[Dict]:
    b = widths(inp)
    w_max = max(b.values())
    cap_p = (inp.cap_L - inp.W) / 2.0                 # along the web, per side
    base_p = (inp.base_L - inp.W) / 2.0
    return [
        {"Criterion": "Length ≥ 3 × greatest flat width",
         "Working": f"c = {inp.c:g} ≥ 3 × {w_max:g} = {3 * w_max:g} mm",
         "OK": inp.c >= 3 * w_max},
        {"Criterion": "At least 5 holes (pitches) in the specimen",
         "Working": f"c / pitch = {inp.c:g} / {inp.pitch:g} = {inp.c / inp.pitch:.2f} ≥ 5",
         "OK": inp.c / inp.pitch >= 5 - 1e-9},
        {"Criterion": "Hole pitch between 50 and 70 mm",
         "Working": f"pitch = {inp.pitch:g} mm", "OK": 50 <= inp.pitch <= 70},
        {"Criterion": "Plates project ≥ 10 mm beyond the upright edge (along the web)",
         "Working": f"cap: ({inp.cap_L:g} − {inp.W:g}) / 2 = {cap_p:g} mm · "
                    f"base: ({inp.base_L:g} − {inp.W:g}) / 2 = {base_p:g} mm",
         "OK": min(cap_p, base_p) >= 10},
        {"Criterion": "Cap plate thickness ≥ 30 mm",
         "Working": f"{inp.cap_t:g} mm", "OK": inp.cap_t >= 30},
    ]


# ------------------------------------------------- Alternative 3: CUFSM + DSM

def dsm_ratio(sigma: float, sigma_crl: float) -> float:
    """DSM local curve used as an effective-area ratio at stress sigma (A_eff / A_g)."""
    lam = sqrt(max(sigma, 1e-9) / sigma_crl)
    if lam <= 0.776:
        return 1.0
    r = (sigma_crl / sigma) ** 0.4
    return (1 - 0.15 * r) * r


def dsm_analysis(inp: StubInputs, cr: Dict, g: Dict, A_net: float) -> Dict:
    """Finite strip signature curve + Direct Strength Method (AISI S100, members with holes)."""
    b = widths(inp)
    nodes_, strips = fsm.mesh(nodes(inp), max_strip=min(5.0, max(b.values()) / 4))
    lengths = np.logspace(np.log10(max(5.0, 2 * inp.t)), np.log10(max(3000.0, 10 * inp.c)), 70)
    sig = fsm.signature_curve(nodes_, strips, inp.t, E, NU, lengths)
    mins = fsm.curve_minima(lengths, sig)
    if mins:
        local = mins[0]
    else:                                               # no clear minimum: lowest short wave
        bmax = max(b.values())
        k = int(np.argmin(np.where(lengths <= 2 * bmax, sig, np.inf)))
        local = {"a": float(lengths[k]), "sigma": float(sig[k])}
    dist = mins[1] if len(mins) > 1 else None

    A, fy = g["A"], inp.fy
    P_y, P_ynet = A * fy, A_net * fy
    # global (flexural / torsional / torsional-flexural, L = c)
    P_cre = cr["N_cr"]
    lam_c = sqrt(P_y / P_cre)
    P_ne = (0.658 ** (lam_c**2) if lam_c <= 1.5 else 0.877 / lam_c**2) * P_y
    P_ne = min(P_ne, P_ynet)
    # local
    P_crl = local["sigma"] * A
    lam_l = sqrt(P_ne / P_crl)
    if lam_l <= 0.776:
        P_nl = P_ne
    else:
        r = (P_crl / P_ne) ** 0.4
        P_nl = (1 - 0.15 * r) * r * P_ne
    P_nl = min(P_nl, P_ynet)
    # distortional (net-section modification for holes)
    P_crd = dist["sigma"] * A if dist else None
    P_nd = lam_d = None
    if P_crd:
        lam_d = sqrt(P_y / P_crd)
        lam_d1 = 0.561 * (P_ynet / P_y)
        lam_d2 = 0.561 * (14 * (P_y / P_ynet) ** 0.4 - 13)
        if lam_d <= lam_d1:
            P_nd = P_ynet
        elif lam_d <= lam_d2:
            P_d2 = (1 - 0.25 * (1 / lam_d2) ** 1.2) * (1 / lam_d2) ** 1.2 * P_y
            P_nd = P_ynet - (P_ynet - P_d2) / (lam_d2 - lam_d1) * (lam_d - lam_d1)
        else:
            r = (P_crd / P_y) ** 0.6
            P_nd = (1 - 0.25 * r) * r * P_y
    use_d = inp.distortional and P_nd is not None
    P_n = min(P_nl, P_nd) if use_d else P_nl
    return {"lengths": lengths, "sigma": sig, "local": local, "dist": dist,
            "n_nodes": len(nodes_), "n_strips": len(strips),
            "P_y": P_y, "P_ynet": P_ynet, "P_cre": P_cre, "lam_c": lam_c, "P_ne": P_ne,
            "P_crl": P_crl, "lam_l": lam_l, "P_nl": P_nl,
            "P_crd": P_crd, "lam_d": lam_d, "P_nd": P_nd, "distortional_used": use_d,
            "P_n": P_n, "governs": "distortional" if use_d and P_nd < P_nl else "local"}


def failure_load(inp: StubInputs) -> Dict:
    eff = effective_section(inp, inp.fy)
    cr = critical_loads(inp)
    lam_bar = sqrt(eff["A_eff"] * inp.fy / cr["N_cr"])
    chi = chi_of(lam_bar)
    N_c = chi * eff["A_eff"] * inp.fy
    g = gross_properties(inp)
    A_net, x_net, _ = net_area(inp)
    x_cg = g["xc"] if inp.cg_x is None else inp.cg_x  # CG used for the load position
    dsm = None
    if inp.alternative == 3:
        dsm = dsm_analysis(inp, cr, g, A_net)
        N_u = N_c = dsm["P_n"]
        lam_bar, chi = dsm["lam_c"], dsm["P_ne"] / dsm["P_y"]
        f, x_load, e = None, x_cg, 0.0
    elif inp.alternative == 1:
        best = None
        for f in np.linspace(0.0, 1.0, 101):          # gross CG (0) ... net CG (1)
            x_load = x_cg + f * (x_net - x_cg)
            e = x_load - eff["x_eff"]
            N_u = 1.0 / (1.0 / N_c + abs(e) / (eff["W_eff"] * inp.fy))
            if best is None or N_u > best[0]:
                best = (N_u, f, x_load, e)
        N_u, f, x_load, e = best
    else:
        N_u, f, x_load, e = N_c, None, x_cg, 0.0
    return {"N_u": N_u, "N_c": N_c, "chi": chi, "lambda_bar": lam_bar, "eff": eff,
            "cr": cr, "load_fraction": f, "x_load": x_load, "e": e,
            "x_gross": g["xc"], "x_cg": x_cg, "cg_custom": inp.cg_x is not None,
            "x_net": x_net, "A_net": A_net, "gross": g, "dsm": dsm}


def proof_stress(inp: StubInputs) -> float:
    """Stress at which the first element starts to buckle locally (rho < 1)."""
    s = []
    for e in elements(inp):
        lim = 0.673 if e["internal"] else 0.748
        lam_fy = (e["b"] / inp.t) / (28.4 * sqrt(235.0 / inp.fy) * sqrt(e["k"]))
        s.append(inp.fy * (lim / lam_fy) ** 2)
    return min(s)


def _A_eff_at_load(inp: StubInputs, N: float, dsm: Dict = None) -> float:
    A = net_area(inp)[0]
    for _ in range(100):
        sigma = min(N / A, inp.fy)
        if dsm is not None:                           # Alternative 3: DSM local curve
            A_new = min(dsm_ratio(sigma, dsm["local"]["sigma"]) * gross_properties(inp)["A"],
                        net_area(inp)[0])
        else:
            A_new = effective_section(inp, sigma)["A_eff"]
        if abs(A_new - A) < 1e-9:
            break
        A = A_new
    return A


def a_eff_from_test(inp: StubInputs, R_k: float, N_cr: float) -> Tuple[float, float]:
    """EN 15512 A.2.1.4: A_eff = R_k / f_y, or chi(A_eff) A_eff f_y = R_k if lambda_bar > 0.2."""
    A = R_k / inp.fy
    lam = sqrt(A * inp.fy / N_cr)
    if lam <= 0.2:
        return A, lam
    lo, hi = A, A * 10
    for _ in range(200):
        mid = 0.5 * (lo + hi)
        if chi_of(sqrt(mid * inp.fy / N_cr)) * mid * inp.fy < R_k:
            lo = mid
        else:
            hi = mid
    return hi, sqrt(hi * inp.fy / N_cr)


def run(inp: StubInputs, increment_kN: float) -> Dict:
    for k in ("W", "D", "t", "pitch", "c", "fy", "gamma_M0", "least_count"):
        if getattr(inp, k) <= 0:
            raise ValueError(f"{k} must be greater than 0.")
    b = widths(inp)
    if min(b["web"], b["flange"]) <= 0 or (inp.lip > 0 and b["lip"] <= 0):
        raise ValueError("Section dimensions are too small for the thickness.")
    if inp.n_web * inp.d_web >= b["web"] or inp.n_fl * inp.d_fl >= b["flange"]:
        raise ValueError("Holes are wider than the plate they are in.")

    fl = failure_load(inp)
    N_u = fl["N_u"]
    inc = increment_kN * 1000.0
    if inc <= 0 or N_u / inc > 200_000:
        raise ValueError("Load increment gives too many steps — use a larger increment.")

    loads = [i * inc for i in range(int(N_u / inc - 1e-9) + 1)] + [N_u]
    if len(loads) > 1 and abs(loads[-1] - loads[-2]) < 1e-9:
        loads.pop()
    rows = []
    for N in loads:
        A = _A_eff_at_load(inp, N, fl["dsm"])
        delta = N * inp.c / (E * A)                   # strain = edge stress / E
        rows.append({"N": N, "A_eff": A, "sigma": N / A, "delta": delta,
                     "dial": delta / inp.least_count})

    A_net = fl["A_net"]
    if fl["dsm"] is not None:                         # DSM local curve leaves 1 at λ_l = 0.776
        s_pr = min(0.776**2 * fl["dsm"]["local"]["sigma"], inp.fy)
    else:
        s_pr = proof_stress(inp)
    N_pr = min(s_pr * A_net, N_u)
    d_pr = next(r["dial"] for r in rows if r["N"] >= N_pr - 1e-9)
    d_u = rows[-1]["dial"]
    slopes = {"Slope1": N_pr / 1000 / d_pr if d_pr else float("nan"),
              "Slope2": (N_u - N_pr) / 1000 / (d_u - d_pr) if d_u > d_pr else float("nan"),
              "Slope3": N_u / 1000 / d_u}
    A_eff_test, lam_test = a_eff_from_test(inp, N_u, fl["cr"]["N_cr"])
    return {**fl, "rows": rows, "N_proof": N_pr, "dial_proof": d_pr, "slopes": slopes,
            "R_k": N_u, "A_eff_test": A_eff_test, "lambda_test": lam_test,
            "N_b_Rd": N_u / inp.gamma_M0, "b": buckling_length_b(inp),
            "checks": specimen_checks(inp), "widths": b,
            "Q": (N_u / inp.fy if fl["dsm"] is not None else fl["eff"]["A_eff"]) / fl["gross"]["A"]}


# ------------------------------------------------- eccentric load (secant formula)

def eccentric_test(inp: StubInputs, res: Dict, e: float, increment_kN: float) -> Dict:
    """Load applied at eccentricity e (mm) from the CG along the symmetry axis.

    Mid-height lateral deflection (pin-ended, secant formula):
        w = e · [sec(π/2 · √(N / N_cr)) − 1],   N_cr = π²·E·I / L_F²  (bending about the axis
        parallel to the web)
    Failure when  N / N_c + N·e·sec(π/2·√(N/N_cr)) / (W_eff·f_y) = 1   (N_c from the chosen
    alternative, W_eff from the effective section).
    """
    e = abs(e)
    N_c, N_cr = res["N_c"], res["cr"]["N_cr_y"]
    W, fy = res["eff"]["W_eff"], inp.fy

    def amp(N):
        return 1.0 / np.cos(pi / 2 * sqrt(N / N_cr))

    def U(N):
        return N / N_c + N * e * amp(N) / (W * fy)

    lo, hi = 0.0, min(N_c, 0.999 * N_cr)
    if U(hi) <= 1:
        N_ue = hi
    else:
        for _ in range(200):
            mid = 0.5 * (lo + hi)
            lo, hi = (mid, hi) if U(mid) < 1 else (lo, mid)
        N_ue = lo
    inc = increment_kN * 1000.0
    loads = [i * inc for i in range(int(N_ue / inc - 1e-9) + 1)] + [N_ue]
    if len(loads) > 1 and abs(loads[-1] - loads[-2]) < 1e-9:
        loads.pop()
    rows = []
    for N in loads:
        A = _A_eff_at_load(inp, N, res.get("dsm"))
        rows.append({"N": N, "w": e * (amp(N) - 1.0), "delta": N * inp.c / (E * A),
                     "M": N * e * amp(N)})
    return {"e": e, "N_ue": N_ue, "N_c": N_c, "N_cr": N_cr, "W_eff": W, "rows": rows,
            "ratio": N_ue / res["N_u"]}
