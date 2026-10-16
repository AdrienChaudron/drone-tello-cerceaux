"""
simulate_direct.py : simulation fermee de la guidance VISEE DIRECTE (tellovision/direct.py).

Drone virtuel : Y = puissance rc d'avance (vitesse = puissance / `rc_par_mps_reel`, retard 0,3 s), cap limite a 60 deg/s,
hauteur suivant la consigne Z a 0,3 m/s au plus (+ erreur statique de 4 cm, comme sa boucle Z), derive laterale (`derive_mps`, > 0 vers la droite ; vue en vol le 09/10 : ~6 cm/s).
Camera inclinee de 10 deg vers le bas, champ +-27 deg (horizontal), +-23 deg (vertical, vu en vol le 09/10) ; retard de 2 images, 10 % d'images
perdues, bruit. Cerceau : centre a 1,54 m, rayon 0,34 m. Succes : le drone franchit le plan du cerceau a moins de
0,20 m du centre (lateral et vertical).

Usage : python tools/simulate_direct.py
"""
import math
from types import SimpleNamespace

import numpy as np

from tellovision.direct import DirectGuidance, Telemetry
from tellovision.link import CommandTranslator

HFOV, VFOV, PITCH = math.radians(54.7), math.radians(42.5), math.radians(10.0)
HOOP_H, OK_RADIUS = 1.54, 0.20


def simulate(hoop_xy, hoop_yaw_deg, start_h=0.8, start_yaw_deg=0.0, rc_par_mps_reel=100.0, derive_mps=0.06, seed=0, T=90.0,
             latency_frames=2, drop=0.10):
    rng = np.random.default_rng(seed)
    H = np.array(hoop_xy, float)
    nh = np.array([math.cos(math.radians(hoop_yaw_deg)), math.sin(math.radians(hoop_yaw_deg))])
    pos, h, psi, v = np.zeros(2), start_h, math.radians(start_yaw_deg), 0.0
    g = DirectGuidance()
    tr = CommandTranslator(rc_par_mps=g.p["rc_par_mps"], rc_max=30)
    dt = 1 / 15
    out = {"X": 0.0, "Y": 0.0, "Z": 100 * start_h, "YAW": start_yaw_deg}
    hist, prev_side, phases = [], None, []
    for k in range(int(T / dt)):
        t = k * dt
        f, r = np.array([math.cos(psi), math.sin(psi)]), np.array([-math.sin(psi), math.cos(psi)])
        rel = H - pos
        c = np.array([rel @ f, rel @ r, HOOP_H - h])                # centre dans le repere drone (avant, droite, haut)
        elev = math.atan2(c[2], c[0]) + PITCH                       # angle vertical dans l'image (camera inclinee)
        visible = (c[0] > 0.6 and abs(math.atan2(c[1], c[0])) < HFOV / 2 - 0.04 and abs(elev) < math.radians(23))
        det = None
        if visible and rng.random() > drop:
            det = SimpleNamespace(present=True, p=0.97, center_drone=c * (1 + rng.normal(0, 0.03)) + rng.normal(0, 0.03, 3),
                                  distance_m=float(np.linalg.norm(c)))
        hist.append(det)
        d = hist[-1 - latency_frames] if len(hist) > latency_frames else None
        header = {"yaw": math.degrees(psi), "tof": 100 * h, "t": t}
        cmd = g.step(d, Telemetry(t=t, yaw_deg=math.degrees(psi), height_m=h), k)
        out = tr(cmd, header)
        if not phases or phases[-1][1] != g.phase:
            phases.append((round(t, 1), g.phase))
        if cmd.mode == "atterrir":
            break
        # dynamique du drone
        v += (out["Y"] / rc_par_mps_reel - v) * dt / 0.3
        pos = pos + v * dt * f + r * derive_mps * dt
        dpsi = math.radians((out["YAW"] - math.degrees(psi) + 180) % 360 - 180)
        psi += max(-math.radians(60) * dt, min(math.radians(60) * dt, 2.0 * dpsi * dt))
        z_err = out["Z"] / 100 - 0.04 - h
        h += max(-0.3 * dt, min(0.3 * dt, 1.5 * z_err * dt))
        side = float((pos - H) @ nh)
        if prev_side is not None and prev_side < 0 <= side:
            lat = float(abs((pos - H) @ np.array([-nh[1], nh[0]])))
            return (round(t, 1), lat, h - HOOP_H), phases
        prev_side = side
    return None, phases


if __name__ == "__main__":
    cases = [("en face, a 4 m, drone 70 cm trop bas", dict(hoop_xy=(4.0, 0.0), hoop_yaw_deg=0, start_h=0.8)),
             ("decale de 20 deg, axe de face", dict(hoop_xy=(3.5, 1.2), hoop_yaw_deg=0)),
             ("axe tourne de 30 deg", dict(hoop_xy=(3.5, 0.3), hoop_yaw_deg=30)),
             ("cerceau sur le cote (recherche)", dict(hoop_xy=(0.5, 3.0), hoop_yaw_deg=90)),
             ("proche (2 m), drone trop haut", dict(hoop_xy=(2.0, 0.0), hoop_yaw_deg=0, start_h=1.9)),
             ("drone 2 fois plus rapide que prevu", dict(hoop_xy=(4.0, 0.0), hoop_yaw_deg=0, rc_par_mps_reel=50.0)),
             ("derive vers la gauche 6 cm/s", dict(hoop_xy=(4.0, 0.0), hoop_yaw_deg=0, derive_mps=-0.06)),
             ("forte derive 10 cm/s", dict(hoop_xy=(4.0, 0.0), hoop_yaw_deg=0, derive_mps=0.10))]
    total = ok = 0
    for name, kw in cases:
        res = []
        for seed in range(20):
            cross, phases = simulate(**kw, seed=seed)
            success = cross is not None and math.hypot(cross[1], cross[2]) < OK_RADIUS
            res.append((success, cross))
            total += 1
            ok += success
            if seed == 0:
                print(f"\n{name} -> {phases}")
        offs = [math.hypot(c[1], c[2]) for _, c in res if c is not None]
        print(f"  {sum(s for s, _ in res)}/20 traversees reussies ; ecart au centre median "
              f"{np.median(offs) * 100 if offs else float('nan'):.0f} cm (max {max(offs) * 100 if offs else float('nan'):.0f}) ; "
              f"temps median {np.median([c[0] for _, c in res if c is not None]) if offs else float('nan'):.0f} s")
    print(f"\nTOTAL : {ok}/{total} traversees reussies")
