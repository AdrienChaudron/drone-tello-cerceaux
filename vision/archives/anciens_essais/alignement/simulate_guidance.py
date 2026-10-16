"""Simulation fermee de l algorithme (tellovision/guidance.py) : drone virtuel au modele volontairement imparfait, camera simulee (champ 55x42 deg, bruit, ambiguite de la normale). Usage : python tools/simulate_guidance.py"""
import math, sys, numpy as np
from types import SimpleNamespace
from tellovision.guidance import HoopGuidance, Telemetry
HFOV, VFOV, R_HOOP = math.radians(54.7), math.radians(42.5), 0.34

def fr(psi):  # vecteurs avant / droite du drone dans le monde (lacet horaire)
    return np.array([math.cos(psi), math.sin(psi)]), np.array([-math.sin(psi), math.cos(psi)])

def simulate(hoop_xy, hoop_yaw_deg, start_xy=(0, 0), start_yaw_deg=0, gain=0.65, noise=0.02, seed=0, T=60, verbose=False):
    rng = np.random.default_rng(seed)
    H = np.array([*hoop_xy, 1.54]); nh = np.array([math.cos(math.radians(hoop_yaw_deg)), math.sin(math.radians(hoop_yaw_deg)), 0.0])
    pos = np.array([*start_xy, 1.1]); psi = math.radians(start_yaw_deg)
    g = HoopGuidance(); dt = 1 / 15; target = None; target_psi = psi; log = []; cross = None; prev_side = None
    for k in range(int(T / dt)):
        t = k * dt
        f, r = fr(psi); rel = H - pos
        c = np.array([rel[:2] @ f, rel[:2] @ r, rel[2]])                       # centre, repere drone (avant, droite, haut)
        dist = np.linalg.norm(c)
        visible = c[0] > 0.9 and abs(math.atan2(c[1], c[0])) < HFOV / 2 - 0.05 and abs(math.atan2(c[2], c[0])) < VFOV / 2 - 0.05
        d = None
        if visible:
            n_d = np.array([nh[:2] @ f, nh[:2] @ r, 0.0])
            if n_d[0] < 0: n_d = -n_d                                            # orientee dans le sens de la traversee
            amb = dist > 2.5
            if amb and rng.random() < 0.5:                                       # de loin : parfois la mauvaise des deux normales
                yaw_n = math.atan2(n_d[1], n_d[0]); los = math.atan2(c[1], c[0]); m = 2 * los - yaw_n
                n_d = np.array([math.cos(m), math.sin(m), 0.0])
            ang = rng.normal(0, math.radians(4)); ca, sa = math.cos(ang), math.sin(ang)
            n_d = np.array([ca * n_d[0] - sa * n_d[1], sa * n_d[0] + ca * n_d[1], 0.0])
            c_meas = c * (1 + rng.normal(0, noise)) + rng.normal(0, noise * 0.5, 3)
            d = SimpleNamespace(present=True, p=0.98, center_drone=c_meas, normal_drone=n_d, distance_m=float(np.linalg.norm(c_meas)), ambiguous=amb)
        cmd = g.step(d, Telemetry(t=t, yaw_deg=math.degrees(psi)), k)
        if cmd.mode == "cible":                                                  # cible relative -> monde, a la pose de l'image
            target = pos + np.array([*(cmd.avant_m * f + cmd.droite_m * r), cmd.haut_m]); target_psi = psi + math.radians(cmd.lacet_deg)
        elif cmd.mode == "atterrir":
            break
        if target is not None:                                                   # modele approximatif : gain < 1 + derive
            v = gain * 1.5 * (target - pos); sp = np.linalg.norm(v[:2])
            if sp > 0.5: v[:2] *= 0.5 / sp
            pos = pos + v * dt + np.array([0.01, -0.008, 0.0]) * dt
        psi += max(-math.radians(60) * dt, min(math.radians(60) * dt, gain * 2 * (target_psi - psi) * dt))
        side = float((pos - H) @ nh)
        if prev_side is not None and prev_side < 0 <= side and cross is None:
            off = (pos - H) - side * nh; cross = (t, float(np.linalg.norm(off[:2])), float(off[2]))
        prev_side = side
        if verbose and (not log or log[-1][1] != cmd.phase): log.append((round(t, 1), cmd.phase))
    return cross, g.phase, g.hoops_done, log

if __name__ == "__main__":
    cases = [("cerceau devant, tourne de 30 deg", dict(hoop_xy=(3.5, 0.4), hoop_yaw_deg=30)),
             ("cerceau a droite, tourne de -35 deg", dict(hoop_xy=(2.5, 2.0), hoop_yaw_deg=-35)),
             ("cerceau DERRIERE le drone (recherche)", dict(hoop_xy=(-3.0, 0.5), hoop_yaw_deg=170)),
             ("cerceau de cote a 1.6 m", dict(hoop_xy=(1.2, -1.2), hoop_yaw_deg=-60))]
    ok = 0; total = 0
    for name, kw in cases:
        res = []
        for seed in range(10):
            cross, phase, done, log = simulate(**kw, seed=seed, verbose=(seed == 0))
            total += 1
            good = cross is not None and cross[1] < R_HOOP - 0.12 and abs(cross[2]) < R_HOOP - 0.12
            ok += good; res.append(cross)
            if seed == 0: print(f"\n{name}\n  phases : {log}")
        lat = [c[1] for c in res if c]; ver = [abs(c[2]) for c in res if c]; tt = [c[0] for c in res if c]
        print(f"  10 essais : traverse {len(lat)}/10, dans le cerceau sans toucher {sum(1 for c in res if c and c[1] < R_HOOP-0.12 and abs(c[2]) < R_HOOP-0.12)}/10 "
              f"| ecart lateral au passage moy {100*np.mean(lat):.0f} cm max {100*np.max(lat):.0f} cm | vertical max {100*np.max(ver):.0f} cm | temps moy {np.mean(tt):.0f} s" if lat else "  aucune traversee")
    print(f"\nTOTAL : {ok}/{total} passages reussis")
