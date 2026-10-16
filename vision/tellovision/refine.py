"""
refine.py : affinage geometrique de l'ellipse predite par le CNN, sur l'image pleine resolution.

Le CNN est bon pour dire "il y a un cerceau, a peu pres ici", moins pour le placer au pixel pres
(l'anneau ne fait que 1 a 2 px a la resolution du reseau). On repart donc de son ellipse et on la
reajuste sur les vrais pixels du tube, cherches dans une bande autour de l'ellipse predite :

    1) carte de "probabilite tube" par la couleur : histogramme Teinte-Saturation appris sur les pixels
       des ellipses annotees, compare au fond voisin (rapport de vraisemblance, comme un classifieur bayesien) ;
    2) RANSAC : on tire 5 points au hasard, cv2.fitEllipse, on compte les points proches de l'ellipse ;
       on garde la meilleure, puis on la reajuste sur tous ses points proches ;
    3) garde-fous : si trop peu de pixels, ou si l'ellipse change trop, on garde celle du CNN.
"""

import math

import cv2
import numpy as np

from tellovision import data

H_BINS, S_BINS = 36, 32


def normalized_radius(e, xs, ys):
    """Rayon normalise des points dans le repere de l'ellipse : 1 = sur l'ellipse, < 1 = a l'interieur."""
    cx, cy, A, B, th = e
    t = math.radians(th)
    dx, dy = xs - cx, ys - cy
    u = dx * math.cos(t) + dy * math.sin(t)
    v = -dx * math.sin(t) + dy * math.cos(t)
    return np.sqrt((u / max(A, 1e-6)) ** 2 + (v / max(B, 1e-6)) ** 2)


def _band(shape, e, inner, outer):
    h, w = shape[:2]
    x1, y1, x2, y2 = data.ellipse_bbox((e[0], e[1], e[2] * outer, e[3] * outer, e[4]))
    x1, y1 = max(int(x1), 0), max(int(y1), 0)
    x2, y2 = min(int(x2) + 1, w), min(int(y2) + 1, h)
    if x2 <= x1 or y2 <= y1:
        return None
    ys, xs = np.mgrid[y1:y2, x1:x2]
    r = normalized_radius(e, xs, ys)
    m = (r >= inner) & (r <= outer)
    return xs[m], ys[m], r[m]


class RingColorModel:
    """Rapport de vraisemblance P(couleur | tube) / P(couleur | fond voisin) sur l'histogramme H-S."""

    def __init__(self, ratio=None):
        self.ratio = ratio

    def fit(self, samples, tube_px=3.0, max_images=200, seed=0):
        rng = np.random.default_rng(seed)
        hist_t = np.zeros((H_BINS, S_BINS))
        hist_b = np.zeros((H_BINS, S_BINS))
        pos = [s for s in samples if s["ellipse"] is not None]
        for s in rng.permutation(pos)[:max_images]:
            img = cv2.imread(s["path"])
            hsv = cv2.cvtColor(img, cv2.COLOR_BGR2HSV)
            e = s["ellipse"]
            d = tube_px / max(e[3], 1)                      # demi-epaisseur du tube en rayon normalise
            band = _band(img.shape, e, 1 - 4 * d - 0.1, 1 + 4 * d + 0.1)
            if band is None:
                continue
            xs, ys, r = band
            on = np.abs(r - 1) <= d
            px = hsv[ys, xs]
            hb = (px[:, 0].astype(int) * H_BINS // 180).clip(0, H_BINS - 1)
            sb = (px[:, 1].astype(int) * S_BINS // 256).clip(0, S_BINS - 1)
            np.add.at(hist_t, (hb[on], sb[on]), 1)
            np.add.at(hist_b, (hb[~on], sb[~on]), 1)
        p_t = (hist_t + 1) / (hist_t.sum() + hist_t.size)
        p_b = (hist_b + 1) / (hist_b.sum() + hist_b.size)
        self.ratio = (p_t / p_b).astype(np.float32)
        return self

    def save(self, path):
        np.save(path, self.ratio)

    @classmethod
    def load(cls, path):
        return cls(np.load(path))

    def score(self, hsv, xs, ys):
        px = hsv[ys, xs]
        hb = (px[:, 0].astype(int) * H_BINS // 180).clip(0, H_BINS - 1)
        sb = (px[:, 1].astype(int) * S_BINS // 256).clip(0, S_BINS - 1)
        return self.ratio[hb, sb]


def fit_ellipse_pts(pts):
    (cx, cy), (w, h), th = cv2.fitEllipse(pts.astype(np.float32))
    A, B = w / 2, h / 2
    if B > A:
        A, B, th = B, A, th + 90
    return float(cx), float(cy), float(A), float(B), th % 180


def refine_ellipse(img, e, color_model, band=(0.75, 1.3), min_ratio=3.0, min_points=40,
                   iters=150, tol=0.04, max_shift=0.5, max_scale=0.35, seed=0):
    """
    Renvoie (ellipse affinee, infos). En cas de doute, renvoie l'ellipse d'origine (infos["ok"] = False).
    tol : tolerance en rayon normalise pour compter un point comme "sur l'ellipse".
    """
    info = {"ok": False, "n_candidates": 0, "n_inliers": 0}
    b = _band(img.shape, e, *band)
    if b is None:
        return e, info
    xs, ys, _ = b
    hsv = cv2.cvtColor(img, cv2.COLOR_BGR2HSV)
    sc = color_model.score(hsv, xs, ys)
    keep = sc >= min_ratio
    xs, ys = xs[keep], ys[keep]
    info["n_candidates"] = int(len(xs))
    if len(xs) < min_points:
        return e, info
    pts = np.stack([xs, ys], 1).astype(np.float64)
    if len(pts) > 4000:                                   # sous-echantillonnage pour la vitesse
        pts = pts[np.random.default_rng(seed).choice(len(pts), 4000, replace=False)]
    rng = np.random.default_rng(seed)
    best, best_n = None, 0
    for _ in range(iters):
        sample = pts[rng.choice(len(pts), 5, replace=False)]
        try:
            cand = fit_ellipse_pts(sample)
        except cv2.error:
            continue
        if not np.all(np.isfinite(cand)) or cand[3] < 3:
            continue
        n = int(np.sum(np.abs(normalized_radius(cand, pts[:, 0], pts[:, 1]) - 1) < tol))
        if n > best_n:
            best, best_n = cand, n
    if best is None or best_n < min_points:
        return e, info
    inl = pts[np.abs(normalized_radius(best, pts[:, 0], pts[:, 1]) - 1) < tol]
    refined = fit_ellipse_pts(inl)
    info["n_inliers"] = int(len(inl))
    shift = math.hypot(refined[0] - e[0], refined[1] - e[1]) / max(e[2], 1)
    scale = abs(refined[2] / max(e[2], 1) - 1)
    if shift > max_shift or scale > max_scale:            # garde-fou : changement trop grand
        return e, info
    info["ok"] = True
    return refined, info


def refine(img, e, color_model):
    """
    Affinage en deux passes (reglages choisis sur la validation de HoopNet_3) :
      1) bande large (0.5 a 1.6 x l'ellipse du CNN) pour "accrocher" le tube meme si le CNN est loin ;
      2) bande fine (0.85 a 1.15) autour du resultat, pour la precision.
    Renvoie (ellipse, affinee_ou_non).
    """
    r1, i1 = refine_ellipse(img, e, color_model, band=(0.5, 1.6), tol=0.06, max_shift=0.8, max_scale=0.5)
    r2, i2 = refine_ellipse(img, r1, color_model, band=(0.85, 1.15), tol=0.03, max_shift=0.2, max_scale=0.15)
    return r2, bool(i1["ok"] or i2["ok"])

