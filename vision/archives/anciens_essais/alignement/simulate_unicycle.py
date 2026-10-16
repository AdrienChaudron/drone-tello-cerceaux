"""
simulate_unicycle.py : simulation fermee de la guidance NON HOLONOME (tellovision/unicycle.py).

Drone virtuel "unicycle" : il avance (selon son cap) et tourne, jamais de cote (+ une petite derive), avec un modele
volontairement imparfait : il avance a 75 % de la vitesse commandee (Y = puissance rc), avec un retard du 1er ordre
(constante de temps 0,3 s). Camera simulee : champ
+-27 x +-21 deg, retard de 2 images, 10 % d'images perdues + des rafales de pertes, bruit, ambiguite de l'axe de loin.
Succes : le drone franchit le plan du cerceau a moins de 0,20 m du centre (cerceau 0,34 m de rayon, drone ~0,09 m).

Usage : python tools/simulate_unicycle.py
"""
import math
from types import SimpleNamespace

import numpy as np

from tellovision.guidance import Telemetry
from tellovision.unicycle import UnicycleGuidance

HFOV, VFOV = math.radians(54.7), math.radians(42.5)
OK_RADIUS = 0.20
TAU = 0.3


def fr(psi):
    return np.array([math.cos(psi), math.sin(psi)]), np.array([-math.sin(psi), math.cos(psi)])


def simulate(hoop_xy, hoop_yaw_deg, start_xy=(0.0, 0.0), start_yaw_deg=0.0, speed_factor=0.75, seed=0, T=90.0,
             latency_frames=2, drop=0.10, verbose=False):
    rng = np.random.default_rng(seed)
    H = np.array(hoop_xy, float)
    nh = np.array([math.cos(math.radians(hoop_yaw_deg)), math.sin(math.radians(hoop_yaw_deg))])
    pos, psi = np.array(start_xy, float), math.radians(start_yaw_deg)
    g = UnicycleGuidance()
    dt, tau = 1 / 15, TAU
    v_target, v, psi_target = 0.0, 0.0, psi      # vitesse d'avance visee et reelle (m/s), cap vise du drone
    hist, cross, prev_side, burst = [], None, None, 0
    n_mem = n_seen = 0
    log = []
    for k in range(int(T / dt)):
        t = k * dt
        f, r = fr(psi)
        rel = H - pos
        c = np.array([rel @ f, rel @ r, 0.4])                      # centre dans le repere drone (cerceau 40 cm plus haut)
        visible = (c[0] > 0.7 and abs(math.atan2(c[1], c[0])) < HFOV / 2 - 0.04
                   and abs(math.atan2(c[2], c[0])) < VFOV / 2 - 0.04)
        if burst > 0:
            burst -= 1
            visible = False
        elif rng.random() < 0.01:
            burst = int(rng.integers(5, 20))                        # rafale de pertes (0,3 a 1,3 s)
        det = None
        if visible and rng.random() > drop:
            n_d = np.array([nh @ f, nh @ r, 0.0])
            dist = float(np.linalg.norm(c))
            amb = dist > 2.5
            if amb and rng.random() < 0.4:                           # de loin : parfois l'autre solution de l'axe
                yaw_n, los = math.atan2(n_d[1], n_d[0]), math.atan2(c[1], c[0])
                m2 = 2 * los - yaw_n
                n_d = np.array([math.cos(m2), math.sin(m2), 0.0])
            a = rng.normal(0, math.radians(4))
            n_d = np.array([math.cos(a) * n_d[0] - math.sin(a) * n_d[1], math.sin(a) * n_d[0] + math.cos(a) * n_d[1], 0])
            c_meas = c * (1 + rng.normal(0, 0.02)) + rng.normal(0, 0.02, 3)
            det = SimpleNamespace(present=True, p=0.97, center_drone=c_meas, normal_drone=n_d, ambiguous=amb)
        hist.append(det)
        d = hist[-1 - latency_frames] if len(hist) > latency_frames else None   # la vision arrive en retard
        cmd = g.step(d, Telemetry(t=t, yaw_deg=math.degrees(psi), height_m=1.0), k)
        if cmd.mode == "cible":
            v_target = cmd.vitesse_avant_mps * speed_factor
            psi_target = psi + math.radians(cmd.lacet_deg)
        elif cmd.mode == "atterrir":
            break
        else:
            v_target = 0.0                                          # maintien : Y = 0
        n_mem += g.phase == "MEMOIRE"
        n_seen += g.phase == "SUIVI"
        # dynamique du drone : avance selon son cap (jamais de cote), cap limite a 60 deg/s
        v += (v_target - v) * dt / tau
        step = v * dt
        pos = pos + step * f + r * 0.01 * dt                       # derive laterale 1 cm/s
        dpsi = (psi_target - psi + math.pi) % (2 * math.pi) - math.pi
        psi += max(-math.radians(60) * dt, min(math.radians(60) * dt, 2.0 * dpsi * dt))
        side = float((pos - H) @ nh)
        if prev_side is not None and prev_side < 0 <= side and cross is None:
            cross = (round(t, 1), float(abs((pos - H) @ np.array([-nh[1], nh[0]]))))
        prev_side = side
        if verbose and (not log or log[-1][1] != g.phase):
            log.append((round(t, 1), g.phase))
    return cross, g.phase, n_seen, n_mem, log


if __name__ == "__main__":
    cases = [("cerceau en face, de face", dict(hoop_xy=(3.0, 0.0), hoop_yaw_deg=0)),
             ("en face, axe tourne de 30 deg", dict(hoop_xy=(3.5, 0.3), hoop_yaw_deg=30)),
             ("decale a droite, axe tourne de 45 deg", dict(hoop_xy=(3.0, 1.2), hoop_yaw_deg=45)),
             ("decale a gauche, axe tourne de -40 deg", dict(hoop_xy=(3.5, -1.5), hoop_yaw_deg=-40)),
             ("tres de biais : axe tourne de 60 deg", dict(hoop_xy=(3.0, 0.5), hoop_yaw_deg=60)),
             ("cerceau sur le cote (recherche)", dict(hoop_xy=(0.5, 3.0), hoop_yaw_deg=90)),
             ("proche et de biais (recul)", dict(hoop_xy=(1.3, 0.4), hoop_yaw_deg=40))]
    total = ok = 0
    for name, kw in cases:
        res = []
        for seed in range(20):
            cross, phase, n_seen, n_mem, log = simulate(**kw, seed=seed, verbose=(seed == 0))
            success = cross is not None and cross[1] < OK_RADIUS
            res.append((success, cross, n_mem / max(1, n_seen + n_mem)))
            total += 1
            ok += success
            if seed == 0:
                print(f"\n{name} -> phases : {log}")
        offs = [c[1] for s, c, _ in res if c is not None]
        print(f"  {sum(s for s, _, _ in res)}/20 traversees reussies ; ecart au centre median "
              f"{np.median(offs) * 100 if offs else float('nan'):.0f} cm (max {max(offs) * 100 if offs else float('nan'):.0f}) ; "
              f"part du suivi sur memoire {np.mean([m for _, _, m in res]) * 100:.0f} %")
    print(f"\nTOTAL : {ok}/{total} traversees reussies")
