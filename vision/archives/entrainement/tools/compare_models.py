"""
compare_models.py
Compare plusieurs modeles (regression ou segmentation) sur la MEME validation stable, avec et sans
affinage geometrique (refine.py), avec exactement les memes calculs de metriques pour tous.

Usage :
    python tools/compare_models.py logs/E0_regression320_0 logs/E1_regression480_0 logs/E2_segmentation480_0
Sortie : tableau dans le terminal + logs/comparaison.csv
"""

import argparse
import csv
import math
import os

import cv2
import numpy as np
import yaml

from tellovision import data, refine
from tellovision.main import load_checkpoint, predict


def angle_err(e, g):
    d = abs(e[4] - g[4]) % 180
    return min(d, 180 - d)


def evaluate(model, cfg, samples, color_model=None):
    rows = []
    for s in samples:
        img = cv2.imread(s["path"])
        p, e = predict(model, cfg, img)
        if e is not None and color_model is not None:
            e, _ = refine.refine(img, e, color_model)
        rows.append((s, p, e))
    pred = np.array([p >= 0.5 for _, p, _ in rows])
    true = np.array([s["present"] == 1 for s, _, _ in rows])
    tp, fp, fn = int(np.sum(pred & true)), int(np.sum(pred & ~true)), int(np.sum(~pred & true))
    ce, me, re, ae = [], [], [], []
    for s, p, e in rows:
        g = s["ellipse"]
        if g is None or e is None:
            continue
        ce.append(math.hypot(e[0] - g[0], e[1] - g[1]))
        me.append(abs(e[2] - g[2]) / g[2])
        re.append(abs(e[3] / e[2] - g[3] / g[2]))
        if g[3] / g[2] < 0.85:
            ae.append(angle_err(e, g))
    ce, me = np.array(ce), np.array(me)
    return {
        "exactitude": float(np.mean(pred == true)), "precision": tp / max(tp + fp, 1), "rappel": tp / max(tp + fn, 1),
        "centre_moy": float(ce.mean()), "centre_med": float(np.median(ce)), "centre_>50px": int(np.sum(ce > 50)),
        "n_ellipses": len(ce), "grand_axe_moy": float(me.mean()), "grand_axe_med": float(np.median(me)),
        "BsurA_moy": float(np.mean(re)), "angle_moy": float(np.mean(ae)) if ae else float("nan"),
    }


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("runs", nargs="+")
    ap.add_argument("--config", default="configs/detect.yaml", help="donne la validation stable commune")
    args = ap.parse_args()

    cfg0 = yaml.safe_load(open(args.config))
    train_ds, valid_ds = data.get_datasets(cfg0)
    color_model = refine.RingColorModel().fit(train_ds.samples)       # appris sur l'entrainement seulement
    va = valid_ds.samples
    print(f"Validation : {len(va)} images ({sum(s['present'] for s in va)} cerceaux, "
          f"{sum(s['ellipse'] is not None for s in va)} ellipses annotees)\n")

    results = []
    for run in args.runs:
        model, cfg, ckpt = load_checkpoint(run)
        for name, cm in (("", None), (" + affinage", color_model)):
            r = evaluate(model, cfg, va, cm)
            r["modele"] = os.path.basename(run.rstrip("/")) + name
            r["epoque"] = ckpt["epoch"]
            results.append(r)

    head = (f"{'modele':34s} {'exact.':>6s} {'prec.':>6s} {'rappel':>6s} | {'centre moy':>10s} {'med':>6s} "
            f"{'>50px':>5s} | {'g.axe moy':>9s} {'med':>6s} | {'B/A':>5s} | {'angle':>6s}")
    print(head)
    print("-" * len(head))
    for r in results:
        print(f"{r['modele']:34s} {100*r['exactitude']:5.1f}% {100*r['precision']:5.1f}% {100*r['rappel']:5.1f}% | "
              f"{r['centre_moy']:8.1f}px {r['centre_med']:5.1f} {r['centre_>50px']:3d}/{r['n_ellipses']:<2d}| "
              f"{100*r['grand_axe_moy']:8.1f}% {100*r['grand_axe_med']:5.1f}% | {r['BsurA_moy']:.3f} | "
              f"{r['angle_moy']:5.1f}°")
    os.makedirs("logs", exist_ok=True)
    with open("logs/comparaison.csv", "w", newline="") as f:
        w = csv.DictWriter(f, fieldnames=list(results[0].keys()))
        w.writeheader()
        w.writerows(results)
    print("\nTableau enregistre : logs/comparaison.csv")


if __name__ == "__main__":
    main()
