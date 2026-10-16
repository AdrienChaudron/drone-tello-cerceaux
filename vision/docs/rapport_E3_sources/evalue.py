"""
Evaluation complete d'un modele de segmentation (E3, et E2 pour comparaison) sur la validation stable,
avec les memes metriques que le rapport E2 : presence, localisation 2D, boites, pose 3D, temps de calcul,
plus la robustesse a la couleur (validation recoloree). Sortie : resultats.json + figures PNG.
Usage : venv/bin/python <ce fichier> <dossier de sortie>
"""
import json
import math
import os
import sys
import time

import cv2
import numpy as np
import torch
import yaml

sys.path.insert(0, os.getcwd())
from tellovision import data, seg                                     # noqa: E402
from tellovision.main import load_checkpoint                           # noqa: E402
from tellovision.pose import PoseEstimator, circle_poses, select_pose  # noqa: E402

OUT = sys.argv[1]
os.makedirs(OUT, exist_ok=True)
RUNS = {"E3": "logs/E3_segmentation480_couleur_0", "E2": "logs/E2_segmentation480_0"}
W, H = 960, 720
torch.set_num_threads(4)

cfg0 = yaml.safe_load(open("configs/E3_segmentation480_couleur.yaml"))
train_ds, valid_ds = data.get_datasets(cfg0)
VA = valid_ds.samples
TR = train_ds.samples
PE = PoseEstimator()


def lieu(s):
    return "couloir" if os.path.basename(s["file"]).split("_")[2].startswith("17905") else "cage"


# ------------------------------------------------------------------ geometrie
def ell_mask(e, pad=1500):
    """Disque elliptique plein sur une grande toile (partie hors image comprise)."""
    m = np.zeros((H + 2 * pad, W + 2 * pad), np.uint8)
    cx, cy, A, B, th = e
    cv2.ellipse(m, (int(round(cx + pad)), int(round(cy + pad))), (max(int(round(A)), 1), max(int(round(B)), 1)),
                th, 0, 360, 1, -1)
    return m


def iou_mask(a, b):
    i = np.logical_and(a, b).sum()
    u = np.logical_or(a, b).sum()
    return float(i / u) if u else 0.0


def box_iou(a, b):
    x1, y1 = max(a[0], b[0]), max(a[1], b[1])
    x2, y2 = min(a[2], b[2]), min(a[3], b[3])
    i = max(0, x2 - x1) * max(0, y2 - y1)
    u = (a[2] - a[0]) * (a[3] - a[1]) + (b[2] - b[0]) * (b[3] - b[1]) - i
    return float(i / u) if u > 0 else 0.0


def clip_box(b):
    return np.array([np.clip(b[0], 0, W), np.clip(b[1], 0, H), np.clip(b[2], 0, W), np.clip(b[3], 0, H)])


def angle_err(e, g):
    d = abs(e[4] - g[4]) % 180
    return min(d, 180 - d)


def average_precision(scores, labels):
    """Aire sous la courbe precision / rappel (interpolation par paliers, comme sklearn)."""
    o = np.argsort(-np.asarray(scores))
    lab = np.asarray(labels)[o]
    tp = np.cumsum(lab)
    fp = np.cumsum(1 - lab)
    rec = tp / max(lab.sum(), 1)
    prec = tp / np.maximum(tp + fp, 1)
    ap, r0 = 0.0, 0.0
    for r, p in zip(rec, prec):
        ap += (r - r0) * p
        r0 = r
    return float(ap), rec, prec


def pose_of(e):
    poses = circle_poses(e, PE.K, PE.radius, PE.dist)
    p, amb = select_pose(poses, None)
    return p, amb, poses


def project(X):
    px, _ = cv2.projectPoints(np.asarray(X, float).reshape(1, 3), np.zeros(3), np.zeros(3), PE.K, PE.dist)
    return px.reshape(2)


# ------------------------------------------------------------------ inference
def infer(model, cfg, img):
    x = data.preprocess(img, cfg["data"]["input_size"])[None]
    t0 = time.perf_counter()
    with torch.no_grad():
        out = model(x)
    t1 = time.perf_counter()
    p = torch.sigmoid(out[0][0, 0]).item()
    prob = torch.sigmoid(out[1][0, 0]).numpy()
    e = seg.mask_to_ellipse(prob, img.shape[1], img.shape[0]) if p >= 0.5 else None
    t2 = time.perf_counter()
    return p, e, prob, (t1 - t0) * 1000, (t2 - t1) * 1000


def evaluate(name, run, transform=None, full=True):
    model, cfg, ckpt = load_checkpoint(run)
    rows = []
    t_cnn, t_ell, t_pose = [], [], []
    inter = union = 0.0
    th = cfg["seg"]["ring_thickness"]
    for s in VA:
        img = cv2.imread(s["path"])
        if transform is not None:
            img = transform(img)
        p, e, prob, a, b = infer(model, cfg, img)
        t_cnn.append(a)
        t_ell.append(b)
        if full:                                       # IoU du masque (meme cible que l'entrainement)
            g = s["ellipse"]
            mh, mw = prob.shape
            tgt = seg.ring_target(g, W, H, mw, mh, th) if g is not None else np.zeros((mh, mw), np.float32)
            pm, tm = prob >= 0.5, tgt > 0.5
            inter += float((pm & tm).sum())
            union += float((pm | tm).sum())
        pose = None
        if e is not None and full:
            t0 = time.perf_counter()
            pose = pose_of(e)
            t_pose.append((time.perf_counter() - t0) * 1000)
        rows.append({"s": s, "p": p, "e": e, "pose": pose})
    res = {"epoch": int(ckpt["epoch"]), "rows": rows, "t_cnn": float(np.median(t_cnn)),
           "t_ell": float(np.median(t_ell)), "t_pose": float(np.median(t_pose)) if t_pose else None,
           "mask_iou": inter / union if union else None}
    return res


def presence(rows):
    pred = np.array([r["p"] >= 0.5 for r in rows])
    true = np.array([r["s"]["present"] == 1 for r in rows])
    tp, fp = int(np.sum(pred & true)), int(np.sum(pred & ~true))
    fn, tn = int(np.sum(~pred & true)), int(np.sum(~pred & ~true))
    prec = tp / max(tp + fp, 1)
    rec = tp / max(tp + fn, 1)
    ap, rc, pc = average_precision([r["p"] for r in rows], true.astype(int))
    return {"VP": tp, "FN": fn, "FP": fp, "VN": tn, "exactitude": (tp + tn) / len(rows), "precision": prec,
            "rappel": rec, "specificite": tn / max(tn + fp, 1), "F1": 2 * prec * rec / max(prec + rec, 1e-9),
            "AP": ap, "pr_rec": rc.tolist(), "pr_prec": pc.tolist(),
            "seuil05": [rec, prec],
            "faux_negatifs": [r["s"]["file"] for r in rows if r["s"]["present"] == 1 and r["p"] < 0.5],
            "faux_positifs": [r["s"]["file"] for r in rows if r["s"]["present"] == 0 and r["p"] >= 0.5],
            "p_FN": [round(r["p"], 3) for r in rows if r["s"]["present"] == 1 and r["p"] < 0.5],
            "p_FP": [round(r["p"], 3) for r in rows if r["s"]["present"] == 0 and r["p"] >= 0.5]}


def localisation(rows):
    out = {}
    for zone in ("tout", "cage", "couloir"):
        ce, me, re, ae = [], [], [], []
        for r in rows:
            g, e = r["s"]["ellipse"], r["e"]
            if g is None or e is None or (zone != "tout" and lieu(r["s"]) != zone):
                continue
            ce.append(math.hypot(e[0] - g[0], e[1] - g[1]))
            me.append(abs(e[2] - g[2]) / g[2])
            re.append(abs(e[3] / e[2] - g[3] / g[2]))
            if g[3] / g[2] < 0.85:
                ae.append(angle_err(e, g))
        n_hoop = sum(1 for r in rows if r["s"]["ellipse"] is not None and (zone == "tout" or lieu(r["s"]) == zone))
        out[zone] = {"n": len(ce), "n_cerceaux": n_hoop,
                     "centre_med": float(np.median(ce)) if ce else None,
                     "centre_moy": float(np.mean(ce)) if ce else None,
                     "centre_sup50": int(np.sum(np.array(ce) > 50)) if ce else 0,
                     "grand_axe_med": float(np.median(me)) if me else None,
                     "grand_axe_moy": float(np.mean(me)) if me else None,
                     "BA_moy": float(np.mean(re)) if re else None,
                     "incl_med": float(np.median(ae)) if ae else None, "n_incl": len(ae)}
    return out


def boites(rows):
    iv, ia, ie, det = [], [], [], []
    for r in rows:
        g, e = r["s"]["ellipse"], r["e"]
        if g is None:
            if r["e"] is not None:
                det.append((r["p"], 0.0, False))
            continue
        if e is None:
            iv.append(0.0); ia.append(0.0); ie.append(0.0)
            continue
        bg, be = data.ellipse_bbox(g), data.ellipse_bbox(e)
        v = box_iou(clip_box(bg), clip_box(be))
        iv.append(v)
        ia.append(box_iou(bg, be))
        ie.append(iou_mask(ell_mask(g), ell_mask(e)))
        det.append((r["p"], v, True))
    n_gt = sum(1 for r in rows if r["s"]["ellipse"] is not None)

    def ap_at(t):
        d = sorted(det, key=lambda x: -x[0])
        lab = [1 if (ok and v >= t) else 0 for _, v, ok in d]
        tp = np.cumsum(lab)
        fp = np.cumsum([1 - x for x in lab])
        rec = tp / n_gt
        prec = tp / np.maximum(tp + fp, 1)
        ap, r0 = 0.0, 0.0
        for rr, pp in zip(rec, prec):
            ap += (rr - r0) * pp
            r0 = rr
        return float(ap)

    f = lambda a: {"moy": float(np.mean(a)), "med": float(np.median(a)), "sup05": float(np.mean(np.array(a) >= 0.5)),
                   "sup075": float(np.mean(np.array(a) >= 0.75))}
    return {"visible": f(iv), "amodale": f(ia), "ellipse": f(ie), "AP50": ap_at(0.5), "AP75": ap_at(0.75),
            "iou_visible": iv, "iou_ellipse": ie}


def pose3d(rows):
    out = {}
    for zone in ("cage", "couloir"):
        dd, dc, dl, d2, dn, dist_gt, dctr = [], [], [], [], [], [], []
        for r in rows:
            g, e = r["s"]["ellipse"], r["e"]
            if g is None or e is None or lieu(r["s"]) != zone or r["pose"] is None:
                continue
            pg = pose_of(g)[0]
            pe = r["pose"][0]
            if pg is None or pe is None:
                continue
            dist_gt.append(pg.distance)
            dd.append(abs(pe.distance - pg.distance) / pg.distance)
            dc.append(float(np.linalg.norm(pe.center - pg.center)))
            dl.append(abs(pe.center[0] - pg.center[0]))
            d2.append(float(np.linalg.norm(project(pe.center) - project(pg.center))))
            dn.append(math.degrees(math.acos(np.clip(abs(pe.normal @ pg.normal), -1, 1))))
            dctr.append(float(np.linalg.norm(project(pg.center) - np.array(g[:2]))))
        if not dd:
            continue
        out[zone] = {"n": len(dd), "dist_min": float(np.min(dist_gt)), "dist_max": float(np.max(dist_gt)),
                     "dist_rel_med": float(np.median(dd)),
                     "dist_abs_med": float(np.median(np.array(dd) * np.array(dist_gt))),
                     "centre3d_med": float(np.median(dc)), "lateral_med": float(np.median(dl)),
                     "centre2d_med": float(np.median(d2)), "normale_med": float(np.median(dn)),
                     "normale_p90": float(np.percentile(dn, 90)),
                     "ecart_centre_ellipse_med": float(np.median(dctr)), "ecart_centre_ellipse_max": float(np.max(dctr))}
    return out


# ------------------------------------------------------------------ robustesse a la couleur
def hue_shift(k):
    def f(img):
        hsv = cv2.cvtColor(img, cv2.COLOR_BGR2HSV)
        hsv[..., 0] = ((hsv[..., 0].astype(np.int16) + k) % 180).astype(np.uint8)
        return cv2.cvtColor(hsv, cv2.COLOR_HSV2BGR)
    return f


def gray(img):
    return cv2.cvtColor(cv2.cvtColor(img, cv2.COLOR_BGR2GRAY), cv2.COLOR_GRAY2BGR)


def hoop_hue():
    """Teinte mediane (OpenCV, 0-180) des pixels de l'anneau dans la validation."""
    hs = []
    for s in VA:
        if s["ellipse"] is None:
            continue
        img = cv2.imread(s["path"])
        m = data.ring_mask(img.shape, s["ellipse"], 0.02) > 0
        hsv = cv2.cvtColor(img, cv2.COLOR_BGR2HSV)
        sel = hsv[m]
        sel = sel[sel[:, 1] > 40]                     # pixels assez colores
        if len(sel):
            hs.append(np.median(sel[:, 0]))
    return float(np.median(hs))


# ------------------------------------------------------------------ main
if __name__ == "__main__":
    R = {}
    for name, run in RUNS.items():
        print("evaluation", name, flush=True)
        ev = evaluate(name, run)
        R[name] = {"epoch": ev["epoch"], "t_cnn": ev["t_cnn"], "t_ell": ev["t_ell"], "t_pose": ev["t_pose"],
                   "mask_iou_recalcule": ev["mask_iou"], "presence": presence(ev["rows"]),
                   "localisation": localisation(ev["rows"]), "boites": boites(ev["rows"]),
                   "pose3d": pose3d(ev["rows"])}
        R[name]["_rows"] = ev["rows"]
    # robustesse couleur
    h0 = hoop_hue()
    green = 60
    k_green = int(round((green - h0) % 180))
    tests = [("origine", None), ("teinte +60°", hue_shift(30)), ("teinte +120°", hue_shift(60)),
             ("teinte +180°", hue_shift(90)), ("teinte +240°", hue_shift(120)), ("teinte +300°", hue_shift(150)),
             (f"cerceau vert (+{2*k_green}°)", hue_shift(k_green)), ("niveaux de gris", gray),
             ("canaux BGR->RGB", lambda im: np.ascontiguousarray(im[..., ::-1]))]
    coul = {"teinte_cerceau": h0, "decalage_vert": k_green, "tests": []}
    for lab, tf in tests:
        line = {"test": lab}
        for name, run in RUNS.items():
            if tf is None:
                rows = R[name]["_rows"]
            else:
                rows = evaluate(name, run, tf, full=False)["rows"]
            pr = presence(rows)
            lo = localisation(rows)["tout"]
            line[name] = {"rappel": pr["rappel"], "precision": pr["precision"], "FP": pr["FP"],
                          "centre_med": lo["centre_med"], "grand_axe_med": lo["grand_axe_med"]}
        coul["tests"].append(line)
        print(lab, line, flush=True)
    R["couleur"] = coul
    # donnees
    R["donnees"] = {"train": len(TR), "train_cerceaux": sum(s["present"] for s in TR),
                    "valid": len(VA), "valid_cerceaux": sum(s["present"] for s in VA),
                    "valid_cage": sum(1 for s in VA if s["ellipse"] is not None and lieu(s) == "cage"),
                    "valid_couloir": sum(1 for s in VA if s["ellipse"] is not None and lieu(s) == "couloir")}
    # figures : on garde les lignes pour les figures
    import pickle
    pickle.dump({k: R[k]["_rows"] for k in RUNS}, open(os.path.join(OUT, "rows.pkl"), "wb"))
    for k in RUNS:
        R[k].pop("_rows")
    json.dump(R, open(os.path.join(OUT, "resultats.json"), "w"), indent=1, default=float)
    print("ok")
