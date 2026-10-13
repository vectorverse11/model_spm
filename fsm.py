"""
Finite Strip Method (FSM) — elastic buckling of thin-walled sections
===================================================================
Same formulation as CUFSM (Schafer & Ádány 2006, "Buckling analysis of cold-formed
steel members using CUFSM"), single half-wave, simply supported (pinned, warping-free) ends.

Each strip (width b, thickness t) between two nodes has 4 DOF per node:
    u  in-plane across the strip     u(x, y) = [N1 u1 + N2 u2] sin(ky)
    v  longitudinal                  v(x, y) = [N1 v1 + N2 v2] cos(ky)
    w  out-of-plane (bending)        w(x, y) = [H1 w1 + H2 θ1 + H3 w2 + H4 θ2] sin(ky)
    θ  rotation about the member axis
with k = π / a (a = half-wavelength), N = linear, H = Hermite cubic shape functions.

    elastic stiffness   K  = ∫∫ (membrane plane-stress + Kirchhoff plate bending) energy
    geometric stiffness Kg = ∫∫ σ t [(∂u/∂y)² + (∂v/∂y)² + (∂w/∂y)²]   (σ = unit compression)
    buckling:           K φ = λ Kg φ   →   σ_cr(a) = smallest λ

The y-integrals are exact (∫sin² = ∫cos² = a/2); the x-integrals use Gauss quadrature.
Plotting σ_cr against a gives the signature curve: its first minimum is local buckling,
the next minimum (if any) is distortional buckling.
"""

from typing import Dict, List, Sequence, Tuple

import numpy as np

_GP, _GW = np.polynomial.legendre.leggauss(6)


def _strip_matrices(b: float, t: float, a: float, E: float, nu: float):
    """8×8 local K and Kg, DOF order [u1 v1 w1 θ1 u2 v2 w2 θ2]."""
    k = np.pi / a
    E1 = E / (1 - nu**2)
    D = E * t**3 / (12 * (1 - nu**2))
    G = E / (2 * (1 + nu))
    K = np.zeros((8, 8))
    Kg = np.zeros((8, 8))
    iu, iv, iw = [0, 4], [1, 5], [2, 3, 6, 7]
    for gp, gw in zip(_GP, _GW):
        x = 0.5 * b * (gp + 1)
        wq = 0.5 * b * gw * (a / 2)                       # x-weight × ∫ trig² dy
        xi = x / b
        N = np.array([1 - xi, xi])
        dN = np.array([-1 / b, 1 / b])
        H = np.array([1 - 3 * xi**2 + 2 * xi**3, b * (xi - 2 * xi**2 + xi**3),
                      3 * xi**2 - 2 * xi**3, b * (xi**3 - xi**2)])
        dH = np.array([(-6 * xi + 6 * xi**2) / b, 1 - 4 * xi + 3 * xi**2,
                       (6 * xi - 6 * xi**2) / b, 3 * xi**2 - 2 * xi])
        d2H = np.array([(-6 + 12 * xi) / b**2, (-4 + 6 * xi) / b,
                        (6 - 12 * xi) / b**2, (6 * xi - 2) / b])
        # membrane: ex = dN·u (sin), ey = -k N·v (sin), gxy = (k N·u + dN·v) (cos)
        Bs = np.zeros((2, 8))
        Bs[0, iu] = dN
        Bs[1, iv] = -k * N
        Bc = np.zeros((1, 8))
        Bc[0, iu] = k * N
        Bc[0, iv] = dN
        Dm = E1 * t * np.array([[1, nu], [nu, 1]])
        K += wq * (Bs.T @ Dm @ Bs + G * t * Bc.T @ Bc)
        # bending: kx = -H''·d (sin), ky = k² H·d (sin), kxy = 2k H'·d (cos)
        Cs = np.zeros((2, 8))
        Cs[0, iw] = -d2H
        Cs[1, iw] = k**2 * H
        Cc = np.zeros((1, 8))
        Cc[0, iw] = 2 * k * dH
        Db = D * np.array([[1, nu], [nu, 1]])
        K += wq * (Cs.T @ Db @ Cs + D * (1 - nu) / 2 * Cc.T @ Cc)
        # geometric (unit compressive stress): (du/dy)², (dv/dy)², (dw/dy)²
        Gu = np.zeros((1, 8)); Gu[0, iu] = k * N
        Gv = np.zeros((1, 8)); Gv[0, iv] = k * N
        Gw = np.zeros((1, 8)); Gw[0, iw] = k * H
        Kg += wq * t * (Gu.T @ Gu + Gv.T @ Gv + Gw.T @ Gw)
    return K, Kg


def _rotation(alpha: float) -> np.ndarray:
    """Local [u v w θ] = R · global [X Y Z Θ] for one node (strip at angle alpha)."""
    c, s = np.cos(alpha), np.sin(alpha)
    r = np.array([[c, 0, s, 0], [0, 1, 0, 0], [-s, 0, c, 0], [0, 0, 0, 1]])
    R = np.zeros((8, 8))
    R[:4, :4] = r
    R[4:, 4:] = r
    return R


def mesh(points: np.ndarray, max_strip: float) -> Tuple[np.ndarray, List[Tuple[int, int]]]:
    """Subdivide a polyline of centreline points into strips no wider than max_strip."""
    nodes = [points[0]]
    for p0, p1 in zip(points[:-1], points[1:]):
        n = max(1, int(np.ceil(np.hypot(*(p1 - p0)) / max_strip)))
        for i in range(1, n + 1):
            nodes.append(p0 + (p1 - p0) * i / n)
    nodes = np.array(nodes)
    return nodes, [(i, i + 1) for i in range(len(nodes) - 1)]


def sigma_cr(nodes: np.ndarray, strips: Sequence[Tuple[int, int]], t: float, a: float,
             E: float, nu: float, fixed: Sequence[int] = ()) -> Tuple[float, np.ndarray]:
    """Lowest buckling stress (compression) at half-wavelength a, and its mode shape."""
    n = 4 * len(nodes)
    K = np.zeros((n, n))
    Kg = np.zeros((n, n))
    for i, j in strips:
        d = nodes[j] - nodes[i]
        b = float(np.hypot(*d))
        k_l, kg_l = _strip_matrices(b, t, a, E, nu)
        R = _rotation(np.arctan2(d[1], d[0]))
        dofs = list(range(4 * i, 4 * i + 4)) + list(range(4 * j, 4 * j + 4))
        K[np.ix_(dofs, dofs)] += R.T @ k_l @ R
        Kg[np.ix_(dofs, dofs)] += R.T @ kg_l @ R
    free = [d for d in range(n) if d not in set(fixed)]
    K, Kg = K[np.ix_(free, free)], Kg[np.ix_(free, free)]
    L = np.linalg.cholesky(Kg)
    Li = np.linalg.inv(L)
    vals, vecs = np.linalg.eigh(Li @ K @ Li.T)
    i = int(np.argmin(np.where(vals > 0, vals, np.inf)))
    return float(vals[i]), Li.T @ vecs[:, i]


def signature_curve(nodes, strips, t, E, nu, lengths) -> np.ndarray:
    return np.array([sigma_cr(nodes, strips, t, a, E, nu)[0] for a in lengths])


def curve_minima(lengths: np.ndarray, sig: np.ndarray) -> List[Dict]:
    """Interior local minima of the signature curve, shortest half-wavelength first."""
    out = []
    for i in range(1, len(sig) - 1):
        if sig[i] < sig[i - 1] and sig[i] <= sig[i + 1]:
            out.append({"a": float(lengths[i]), "sigma": float(sig[i])})
    return out
