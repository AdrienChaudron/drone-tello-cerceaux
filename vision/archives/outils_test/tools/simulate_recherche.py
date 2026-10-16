"""
simulate_recherche.py : simulation fermee de la RECHERCHE et de la MISE EN AXE (tellovision/ordres.py), sans CNN.

Le cerceau est projete dans l'image avec la vraie calibration (configs/camera.yaml) et l'inclinaison de la camera
(configs/drone.yaml) ; detection perdue au-dela du champ, 10 % d'images perdues, bruit de 3 px, retard de 2 images.
Le drone simule joue le role du PC de controle : il asservit son cap sur r_yaw (au plus 60 deg/s), sa hauteur sur r_z
pendant la recherche (au plus 30 cm/s) et sur delta_z quand le cerceau est vu ; il n'avance pas (etat 3 = collegue).
Succes : cerceau centre (|delta_x| <= 40 px et |delta_z| <= 10 cm pendant 0,5 s) : le PC de controle peut avancer.

Usage : python tools/simulate_recherche.py
"""
import math
import os
from types import SimpleNamespace

import cv2
import numpy as np

from tellovision.frames import CameraToDrone
from tellovision.ordres import OrdreVision, wrap180
from tellovision.pose import load_camera

BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


def simulate(bearing_deg, dist_m, hoop_h_cm=154.0, start_h_cm=70.0, start_yaw=0.0, seed=0, T=120.0, present=True):
    rng = np.random.default_rng(seed)
    K, dist = load_camera(os.path.join(BASE_DIR, "configs/camera.yaml"))
    to_drone = CameraToDrone.from_yaml(os.path.join(BASE_DIR, "configs/drone.yaml"))
    o = OrdreVision(K, dist, to_drone)
    hb = math.radians(bearing_deg)
    hoop = np.array([dist_m * math.cos(hb), dist_m * math.sin(hb)])     # (x avant initial, y droite initial)
    yaw, h, dt = start_yaw, start_h_cm, 1 / 15
    hist, etats, t_ok = [], [], None
    for k in range(int(T / dt)):
        t = k * dt
        psi = math.radians(yaw)
        a = hoop @ np.array([math.cos(psi), math.sin(psi)])                # repere drone
        b = hoop @ np.array([-math.sin(psi), math.cos(psi)])
        c = (hoop_h_cm - h) / 100.0
        det = SimpleNamespace(present=False, p=0.02, center_px=None, yaw_drone_deg=None, ambiguous=True,
                              distance_m=None)
        X_cam = to_drone.R.T @ np.array([a, b, c])
        if present and X_cam[2] > 0.3 and rng.random() > 0.10:
            px, _ = cv2.projectPoints(X_cam.reshape(1, 3), np.zeros(3), np.zeros(3), K, dist)
            u, v = px.reshape(2) + rng.normal(0, 3, 2)
            if 20 < u < 940 and 20 < v < 700:                               # cerceau (presque) entier dans l'image
                cd = np.array([a, b, c]) * (1 + rng.normal(0, 0.03)) + rng.normal(0, 0.02, 3)   # pose 3D bruitee
                det = SimpleNamespace(present=True, p=0.97, center_px=(u, v), center_drone=cd, yaw_drone_deg=None,
                                      ambiguous=True,
                                      distance_m=float(np.linalg.norm([a, b, c])))
        hist.append(det)
        d = hist[-3] if len(hist) > 2 else hist[0]
        r = o.step(d, t, yaw, h)
        if not etats or etats[-1][1] != r["etat"]:
            etats.append((round(t, 1), r["etat"]))
        centre = (r["present"] and r["delta_x"] is not None and r["delta_z"] is not None
                  and abs(r["delta_x"]) <= 40 and abs(r["delta_z"]) <= 0.10)     # delta_x en px, delta_z en m
        t_ok = (t_ok if t_ok is not None else t) if centre else None
        if t_ok is not None and t - t_ok >= 0.5:
            return True, t, etats, h
        if r["etat"] == "ECHEC":
            return False, t, etats, h
        # PC de controle simule : cap sur r_yaw, hauteur sur r_z (recherche) ou delta_z (cerceau vu)
        e = wrap180(r["r_yaw"] - yaw)
        yaw = wrap180(yaw + max(-60 * dt, min(60 * dt, 2.0 * e * dt)))
        if r["present"] and r["delta_z"] is not None:
            dz_cm = 100.0 * r["delta_z"]
            h += max(-30 * dt, min(30 * dt, 1.5 * dz_cm * dt))
        elif r["r_z"] is not None:
            h += max(-30 * dt, min(30 * dt, 1.5 * (r["r_z"] - h) * dt))
    return False, T, etats, h


if __name__ == "__main__":
    cases = [("cerceau en face a 3 m", dict(bearing_deg=5, dist_m=3.0)),
             ("cerceau sur le cote (90 deg) a 3 m", dict(bearing_deg=90, dist_m=3.0)),
             ("cerceau derriere (180 deg) a 4 m", dict(bearing_deg=180, dist_m=4.0)),
             ("cerceau a gauche (-120 deg) a 2,5 m", dict(bearing_deg=-120, dist_m=2.5)),
             ("loin (5 m) et drone bas (50 cm) : il faut monter", dict(bearing_deg=60, dist_m=5.0, start_h_cm=50)),
             ("cerceau haut (2 m) a 2 m, drone a 70 cm", dict(bearing_deg=150, dist_m=2.0, hoop_h_cm=200)),
             ("aucun cerceau (doit finir en ECHEC)", dict(bearing_deg=0, dist_m=3.0, present=False))]
    for name, kw in cases:
        res = [simulate(**kw, seed=s) for s in range(10)]
        ok = sum(r[0] for r in res)
        times = [r[1] for r in res if r[0]]
        print(f"\n{name} -> {res[0][2]}")
        print(f"  cerceau centre {ok}/10" + (f" en {np.median(times):.0f} s (max {max(times):.0f} s)" if times else "")
              + f" ; hauteur finale {np.median([r[3] for r in res]):.0f} cm")
