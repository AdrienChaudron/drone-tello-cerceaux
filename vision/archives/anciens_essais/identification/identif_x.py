"""
identif_x.py : identification de l'axe LATERAL X (puissance rc de roulis, non asservie chez le collegue).

Mesure : le cerceau sert de REPERE FIXE. Le drone le regarde (a ~2 m, de face) ; la camera donne la position du centre
dans le repere drone (avant a, droite b) et l'en-tete donne le cap psi. La position laterale du drone, dans le repere
du cap de depart psi0, est alors  y = -(a sin(psi - psi0) + b cos(psi - psi0))   (> 0 : drone deplace vers la DROITE).

Attente : sans --hauteur, AUCUNE commande n'est envoyee (le PC de controle place le drone face au cerceau) ;
avec --hauteur CM, le drone monte a CM cm (15 cm/s), cap tenu. L'essai demarre quand le cerceau est vu 1 s d'affilee
(et la hauteur atteinte) ; hauteur et cap de depart sont pris a cet instant.
Essai : Y = 0, Z et YAW figes a leur valeur de depart, X suit la sequence :
    repos X = 0 pendant --repos-initial s   (mesure de l'OFFSET : derive du drone sans commande)
    puis --cycles fois :  X = +A (--palier s), X = 0 (--repos s), X = -A (--palier s), X = 0 (--repos s)
Arret de securite (X = 0) : cerceau perdu plus de --perte-max s, ecart lateral > --ecart-max m, Ctrl+C.
IHM web : comme vision_node.py, l'image annotee et l'etat sont servis en HTTP (port 8080) et publies sur
tello/vision/view et tello/vision/state (phase = palier en cours). NE PAS lancer vision_node.py en meme temps.

Modeles ajustes (vitesse laterale v, commande u en rc, offset u0 en rc) :
    ordre 0 : v = K (u + u0)                                  (integrateur pur sur la position)
    ordre 1 : tau v' + v = K (u(t - r) + u0)                 (retard r)
    ordre 2 : v'' + 2 zeta w v' + w^2 v = w^2 K (u(t - r) + u0)
La figure montre la commande, la position et la vitesse mesurees avec les trois modeles, et les reponses a chaque
palier superposees (vitesse normalisee) pour reconnaitre l'ordre a l'oeil.

Usage :
    python tools/identif_x.py                              # essai (A = 15, paliers de 2 s), puis analyse et figure
    python tools/identif_x.py --hauteur 130                # monter d'abord a 1,30 m
    python tools/identif_x.py --amplitude 20 --palier 1.5 --cycles 3
    python tools/identif_x.py --analyse logs/identif/x_1791533000.csv     # rejouer l'analyse d'un essai
    python tools/identif_x.py --broker 127.0.0.1 --sans-commande          # test sans drone (simulate_hil.py)
"""

import argparse
import csv
import math
import os
import time

import numpy as np

BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
OUT_DIR = os.path.join(BASE_DIR, "logs", "identif")
COLS = ["t", "phase", "X", "a", "b", "c", "p", "yaw", "tof_cm", "y_m", "mesure_x"]


# ------------------------------------------------------------------ #
# Essai
# ------------------------------------------------------------------ #
def sequence(args):
    """Liste de (debut, fin, X, nom) relative au debut de l'essai."""
    seq, t = [], 0.0
    steps = [(args.repos_initial, 0.0, "offset")]
    for i in range(args.cycles):
        steps += [(args.palier, args.amplitude, f"+A{i + 1}"), (args.repos, 0.0, f"repos{2 * i + 1}"),
                  (args.palier, -args.amplitude, f"-A{i + 1}"), (args.repos, 0.0, f"repos{2 * i + 2}")]
    for dur, x, name in steps:
        seq.append((t, t + dur, x, name))
        t += dur
    return seq


def run(args):
    os.environ.setdefault("QT_QPA_FONTDIR", "/usr/share/fonts/truetype/dejavu")
    import cv2
    from tellovision.detector import HoopDetector, draw_detection
    from tellovision.ihm_server import VisionWebServer
    from tellovision.link import VisionLink

    if abs(args.amplitude) > 30:
        raise SystemExit("amplitude limitee a 30 (securite)")
    os.makedirs(OUT_DIR, exist_ok=True)
    print("Chargement du reseau...")
    det = HoopDetector(args.run)
    link = VisionLink(args.reseau, broker_ip=args.broker, client_id="tello_identif_x")
    tof_facteur = float(link.cfg.get("tof_entete_facteur", 1.0))
    mesure_x = {"v": None}                       # derniere mesure de sa boucle X (angle de roulis ?)

    def on_archive_x(client, userdata, msg):
        try:
            import json
            mesure_x["v"] = json.loads(msg.payload).get("measure")
        except Exception:
            pass
    link.client.message_callback_add("tello/archive/X", on_archive_x)
    on_connect_video = link.client.on_connect

    def on_connect(client, userdata, flags, rc, props):
        on_connect_video(client, userdata, flags, rc, props)
        client.subscribe("tello/archive/X", qos=0)
    link.client.on_connect = on_connect
    link.start()
    web = None
    if not args.no_ihm:
        web = VisionWebServer(port=args.ihm_port)
        web.start()

    def ihm(img, d, header, phase, x, y, z, yaw_c):
        """Image annotee + etat pour l'IHM web (memes formats que vision_node.py)."""
        if web is None:
            return
        view = draw_detection(img, d)
        h, wd = view.shape[:2]
        txt = (f"[IDENTIF X] {phase}  X {x:+.0f}  Y 0  Z {z:.0f}  YAW {yaw_c:+.0f}"
               + ("" if y is None else f"   y {100 * y:+.0f} cm"))
        cv2.rectangle(view, (0, h - 26), (wd, h), (0, 0, 0), -1)
        cv2.putText(view, txt, (6, h - 8), cv2.FONT_HERSHEY_SIMPLEX, 0.5, (0, 255, 255), 1, cv2.LINE_AA)
        ok, jpg = cv2.imencode(".jpg", view, [cv2.IMWRITE_JPEG_QUALITY, 75])
        st = {"frame_id": header.get("frame_id"), "t": header.get("t"), "phase": phase, "mode": "identification",
              "present": bool(d.present), "p": round(float(d.p), 3), "ambigu": False, "distance_m": None,
              "centre": None, "axe": None, "commande": {"X": x, "Y": 0.0, "Z": round(float(z), 1),
                                                         "YAW": round(float(yaw_c), 1)},
              "calcul_ms": 0.0, "recues": link.received, "sautees": link.dropped, "test": "[IDENTIF X]"}
        if d.present and d.center_drone is not None:
            a, b, c = (round(float(v), 3) for v in d.center_drone)
            st["distance_m"] = round(float(d.distance_m), 3)
            st["centre"] = {"avant": a, "droite": b, "haut": c}
        if ok:
            web.publish_frame(jpg.tobytes())
            link.publish_view(jpg.tobytes())
        web.publish_state(st)
        link.publish_state(st)

    seq = sequence(args)
    total = seq[-1][1]
    print(f"Sequence ({total:.0f} s) : " + ", ".join(f"{n} X={x:+.0f} {e - s:.1f}s" for s, e, x, n in seq))
    path = os.path.join(OUT_DIR, f"x_{int(time.time())}.csv")
    f = open(path, "w", newline="")
    w = csv.writer(f)
    w.writerow(COLS)

    def send(x, z, yaw):
        if not args.sans_commande:
            link.send_command({"X": round(float(x), 1), "Y": 0.0, "Z": round(float(z), 1), "YAW": round(float(yaw), 1)})

    psi0 = z0 = t0 = None
    t_seen, y_ref, stable = None, None, 0
    raison = "sequence terminee"
    print("En attente du cerceau (de face, a ~2 m, bien visible)...")
    try:
        while True:
            got = link.get_frame(timeout=0.5)
            if got is None:
                continue
            header, img, _ = got
            if img is None:
                continue
            t = float(header["t"])
            yaw, tof = float(header["yaw"]), float(header["tof"]) / tof_facteur
            d = det(img, orig_size=(header.get("w", 960), header.get("h", 720)))
            seen = d.present and d.p >= args.min_p and d.center_drone is not None

            if t0 is None:                                   # attente : cerceau vu 1 s d'affilee (et hauteur atteinte)
                stable = stable + 1 if seen else 0
                if args.hauteur is None:                     # rien n'est envoye : le PC de controle garde la main
                    ihm(img, d, header, "ATTENTE cerceau (sans commande)", 0.0, None, tof, yaw)
                    ready = stable >= 15
                else:                                        # montee a --hauteur (15 cm/s), cap tenu
                    if psi0 is None:
                        psi0, z_cmd, t_z = yaw, tof, t
                    z_cmd += max(-1.0, min(1.0, args.hauteur - z_cmd)) * min(15.0 * (t - t_z), abs(args.hauteur - z_cmd))
                    t_z = t
                    send(0.0, z_cmd, psi0)
                    ihm(img, d, header, f"ATTENTE cerceau, montee a {args.hauteur:.0f} cm", 0.0, None, z_cmd, psi0)
                    ready = stable >= 15 and abs(tof - args.hauteur) < 10
                if ready:
                    t0, t_seen = t, t
                    psi0 = yaw if args.hauteur is None else psi0
                    z0 = tof if args.hauteur is None else args.hauteur
                    print(f"Depart : cap {psi0:.0f} deg, hauteur {z0:.0f} cm, cerceau a {d.distance_m:.2f} m")
                continue

            el = t - t0
            cur = next((s for s in seq if s[0] <= el < s[1]), None)
            if cur is None:
                break
            x, name = cur[2], cur[3]
            y = None
            if seen:
                a, b, c = (float(v) for v in d.center_drone)
                dpsi = math.radians(yaw - psi0)
                y = -(a * math.sin(dpsi) + b * math.cos(dpsi))
                if y_ref is None:
                    y_ref = y
                t_seen = t
            if t - t_seen > args.perte_max:
                raison = f"cerceau perdu depuis {t - t_seen:.1f} s"
                break
            if y is not None and abs(y - y_ref) > args.ecart_max:
                raison = f"ecart lateral {y - y_ref:+.2f} m > {args.ecart_max} m"
                break
            send(x, z0, psi0)
            ihm(img, d, header, name, x, None if y is None else y - y_ref, z0, psi0)
            row = [round(el, 3), name, x] + ([round(float(v), 4) for v in d.center_drone] if seen else ["", "", ""])
            row += [round(float(d.p), 3), yaw, round(tof, 1), round(y, 4) if y is not None else "", mesure_x["v"]]
            w.writerow(row)
            if int(el * 2) != int((el - 0.07) * 2):          # ~2 messages par seconde
                print(f"{el:5.1f} s {name:8s} X={x:+4.0f}  y={'' if y is None else f'{100 * (y - y_ref):+5.1f} cm'}"
                      f"  cap {yaw:+.0f}  h {tof:.0f} cm  mesure X {mesure_x['v']}")
    except KeyboardInterrupt:
        raison = "interrompu (Ctrl+C)"
    finally:
        for _ in range(10):                                 # on s'arrete franchement : X = 0
            if psi0 is not None and z0 is not None:
                send(0.0, z0, psi0)
            time.sleep(0.05)
        f.close()
        link.stop()
        if web is not None:
            web.stop()
    print(f"Fin : {raison}. Journal : {path}")
    return path


# ------------------------------------------------------------------ #
# Analyse
# ------------------------------------------------------------------ #
def load(path):
    T, U, Y, PH, MX = [], [], [], [], []
    with open(path) as f:
        for r in csv.DictReader(f):
            T.append(float(r["t"]))
            U.append(float(r["X"]))
            Y.append(float(r["y_m"]) if r["y_m"] != "" else np.nan)
            PH.append(r["phase"])
            MX.append(float(r["mesure_x"]) if r.get("mesure_x") not in ("", None, "None") else np.nan)
    return np.array(T), np.array(U), np.array(Y), PH, np.array(MX)


def _filt1(u, dt, tau):
    """Filtre du 1er ordre (gain 1) sur un signal echantillonne regulierement."""
    out, v, k = np.empty_like(u), 0.0, dt / max(tau, 1e-9)
    for i, ui in enumerate(u):
        v += (ui - v) * min(k, 1.0)
        out[i] = v
    return out


def _filt2(u, dt, w, z):
    """Filtre du 2e ordre (gain 1) : x'' + 2 z w x' + w^2 x = w^2 u (Euler semi-implicite)."""
    out, x, xd = np.empty_like(u), 0.0, 0.0
    for i, ui in enumerate(u):
        xd += (w * w * (ui - x) - 2 * z * w * xd) * dt
        x += xd * dt
        out[i] = x
    return out


def fit(T, U, Y, dt=0.01):
    """Ajuste les trois modeles sur la POSITION (plus robuste que la vitesse derivee). Renvoie un dict par modele."""
    tg = np.arange(T[0], T[-1], dt)
    ug = U[np.clip(np.searchsorted(T, tg, side="right") - 1, 0, len(U) - 1)]   # commande bloquee entre images
    ok = ~np.isnan(Y)
    Ti, Yi = T[ok], Y[ok]

    def solve(vel_u, vel_1):
        """Position = K * int(vel_u) + K u0 * int(vel_1) + y0 : moindres carres lineaires en (K, K u0, y0)."""
        pu, p1 = np.cumsum(vel_u) * dt, np.cumsum(vel_1) * dt
        A = np.column_stack([np.interp(Ti, tg, pu), np.interp(Ti, tg, p1), np.ones_like(Ti)])
        coef, *_ = np.linalg.lstsq(A, Yi, rcond=None)
        rms = float(np.sqrt(np.mean((A @ coef - Yi) ** 2)))
        K, Ku0, y0 = coef
        return rms, K, (Ku0 / K if abs(K) > 1e-9 else 0.0), y0, pu, p1

    def shift(u, r):
        n = int(round(r / dt))
        return np.concatenate([np.zeros(n), u[:len(u) - n]]) if n else u

    res = {}
    rms, K, u0, y0, pu, p1 = solve(ug, np.ones_like(ug))
    res["ordre 0"] = dict(rms=rms, K=K, u0=u0, y0=y0, tau=0.0, r=0.0, pos=K * pu + K * u0 * p1 + y0, vel=K * (ug + u0))
    best = None
    for r in np.arange(0.0, 0.61, 0.05):
        us = shift(ug, r)
        for tau in np.concatenate([np.arange(0.05, 1.0, 0.05), np.arange(1.0, 3.01, 0.2)]):
            fu, f1 = _filt1(us, dt, tau), _filt1(np.ones_like(us), dt, tau)
            sol = solve(fu, f1)
            if best is None or sol[0] < best[0][0]:
                best = (sol, tau, r, fu, f1)
    (rms, K, u0, y0, pu, p1), tau, r, fu, f1 = best
    res["ordre 1"] = dict(rms=rms, K=K, u0=u0, y0=y0, tau=tau, r=r, pos=K * pu + K * u0 * p1 + y0, vel=K * (fu + u0 * f1))
    best = None
    for r in np.arange(0.0, 0.61, 0.1):
        us = shift(ug, r)
        for w in np.arange(1.0, 15.01, 1.0):
            for z in (0.3, 0.5, 0.7, 0.9, 1.2, 1.6):
                fu, f1 = _filt2(us, dt, w, z), _filt2(np.ones_like(us), dt, w, z)
                sol = solve(fu, f1)
                if best is None or sol[0] < best[0][0]:
                    best = (sol, w, z, r, fu, f1)
    (rms, K, u0, y0, pu, p1), w, z, r, fu, f1 = best
    res["ordre 2"] = dict(rms=rms, K=K, u0=u0, y0=y0, w=w, zeta=z, r=r, pos=K * pu + K * u0 * p1 + y0,
                          vel=K * (fu + u0 * f1))
    return tg, ug, res


def velocity(T, Y, win=0.4):
    """Vitesse mesuree : pente d'une droite ajustee sur +-win/2 s (lisse le bruit de la vision)."""
    v = np.full_like(Y, np.nan)
    ok = ~np.isnan(Y)
    for i in np.where(ok)[0]:
        m = ok & (np.abs(T - T[i]) <= win / 2)
        if m.sum() >= 4:
            v[i] = np.polyfit(T[m], Y[m], 1)[0]
    return v


def analyse(path, show=True):
    import matplotlib
    if not show:
        matplotlib.use("Agg")
    import matplotlib.pyplot as plt

    T, U, Y, PH, MX = load(path)
    if np.sum(~np.isnan(Y)) < 20:
        raise SystemExit("pas assez de mesures du cerceau dans ce journal")
    Y = Y - np.nanmean(Y[:10])
    tg, ug, res = fit(T, U, Y)
    V = velocity(T, Y)

    print(f"\nAnalyse de {os.path.basename(path)} ({len(T)} images, {np.sum(~np.isnan(Y))} avec le cerceau)")
    off = [p for p in PH if p == "offset"]
    if off:
        m = (np.array(PH) == "offset") & ~np.isnan(Y)
        if m.sum() > 5:
            drift = np.polyfit(T[m], Y[m], 1)[0]
            print(f"  derive pendant le repos initial (X = 0) : {100 * drift:+.1f} cm/s  (> 0 : vers la droite)")
    for name, r in res.items():
        extra = (f"tau = {r['tau']:.2f} s, retard = {r['r']:.2f} s" if name == "ordre 1" else
                 f"w = {r['w']:.1f} rad/s, zeta = {r['zeta']:.1f}, retard = {r['r']:.2f} s" if name == "ordre 2" else "")
        print(f"  {name} : K = {100 * r['K']:.2f} cm/s par point de rc ; offset u0 = {r['u0']:+.1f} rc "
              f"(derive {100 * r['K'] * r['u0']:+.1f} cm/s) ; {extra} ; erreur RMS {100 * r['rms']:.1f} cm")
    print(f"  -> pour annuler la derive : X = {-res['ordre 1']['u0']:+.1f} rc (modele d'ordre 1)")

    colors = {"ordre 0": "tab:gray", "ordre 1": "tab:green", "ordre 2": "tab:red"}
    fig, ax = plt.subplots(4, 1, figsize=(11, 12), sharex=False)
    fig.suptitle(f"Identification de l'axe X : {os.path.basename(path)}")
    ax[0].step(T, U, where="post", color="tab:blue")
    ax[0].set_ylabel("commande X (rc)")
    ax[0].grid(alpha=0.3)
    ax[1].plot(T, 100 * Y, ".", ms=3, color="k", label="mesure (vision)")
    for name, r in res.items():
        ax[1].plot(tg, 100 * r["pos"], color=colors[name], label=f"{name} (RMS {100 * r['rms']:.1f} cm)")
    ax[1].set_ylabel("position laterale (cm)")
    ax[1].legend(fontsize=8)
    ax[1].grid(alpha=0.3)
    ax[2].plot(T, 100 * V, ".", ms=3, color="k", label="mesure (pente sur 0,4 s)")
    for name, r in res.items():
        ax[2].plot(tg, 100 * r["vel"], color=colors[name], label=name)
    ax[2].set_ylabel("vitesse laterale (cm/s)")
    ax[2].legend(fontsize=8)
    ax[2].grid(alpha=0.3)
    for a in ax[:3]:
        a.set_xlim(T[0], T[-1])
    ax[2].set_xlabel("temps (s)")
    # reponses aux paliers superposees : vitesse / (K A), a partir du debut de chaque palier
    ph = np.array(PH)
    for name in [p for p in dict.fromkeys(PH) if p.startswith(("+A", "-A"))]:
        idx = np.where(ph == name)[0]
        ts = T[idx[0]]
        m = (T >= ts - 0.5) & (T <= ts + 2.5)
        A = U[idx[0]]
        norm = res["ordre 1"]["K"] * A
        if abs(norm) > 1e-9:
            ax[3].plot(T[m] - ts, (V[m] - res["ordre 1"]["K"] * res["ordre 1"]["u0"]) / norm, ".-", ms=3, lw=0.8,
                       label=name)
    tt = np.linspace(0, 2.5, 200)
    r1 = res["ordre 1"]
    ax[3].plot(tt, np.where(tt > r1["r"], 1 - np.exp(-(tt - r1["r"]) / r1["tau"]), 0), "g--", lw=2, label="ordre 1")
    ax[3].axhline(1, color="k", lw=0.5)
    ax[3].axvline(0, color="k", lw=0.5)
    ax[3].set_xlabel("temps depuis le debut du palier (s)")
    ax[3].set_ylabel("vitesse / (K x A)")
    ax[3].set_title("Reponses aux paliers superposees (1 = vitesse finale du modele)", fontsize=10)
    ax[3].legend(fontsize=8, ncol=3)
    ax[3].grid(alpha=0.3)
    fig.tight_layout()
    png = os.path.splitext(path)[0] + ".png"
    fig.savefig(png, dpi=110)
    print(f"  figure : {png}")
    if show:
        plt.show()
    return res


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--analyse", metavar="CSV", help="analyser un journal existant (pas d'essai)")
    ap.add_argument("--hauteur", type=float, default=None, metavar="CM",
                    help="monter d'abord a cette hauteur (cm) ; sans cette option, rien n'est envoye pendant l'attente")
    ap.add_argument("--amplitude", type=float, default=15.0, help="puissance X des paliers (rc, <= 30)")
    ap.add_argument("--palier", type=float, default=2.0, help="duree de chaque palier X = +-A (s)")
    ap.add_argument("--repos", type=float, default=2.5, help="duree X = 0 entre les paliers (s)")
    ap.add_argument("--repos-initial", type=float, default=5.0, help="duree X = 0 au debut : mesure de l'offset (s)")
    ap.add_argument("--cycles", type=int, default=2)
    ap.add_argument("--ecart-max", type=float, default=0.8, help="arret si le drone s'ecarte de plus de 0,8 m")
    ap.add_argument("--perte-max", type=float, default=1.0, help="arret si le cerceau est perdu plus de 1 s")
    ap.add_argument("--min-p", type=float, default=0.6)
    ap.add_argument("--run", default=os.path.join(BASE_DIR, "logs", "E2_segmentation480_0"))
    ap.add_argument("--reseau", default="configs/reseau.yaml")
    ap.add_argument("--broker", default=None)
    ap.add_argument("--sans-commande", action="store_true", help="n'envoie aucune commande (test de la mesure)")
    ap.add_argument("--no-show", action="store_true", help="enregistrer la figure sans l'afficher")
    ap.add_argument("--no-ihm", action="store_true", help="ne rien publier pour l'IHM web")
    ap.add_argument("--ihm-port", type=int, default=8080, help="port HTTP de la video et de l'etat pour l'IHM web")
    args = ap.parse_args()
    os.chdir(BASE_DIR)
    path = args.analyse or run(args)
    analyse(path, show=not args.no_show)


if __name__ == "__main__":
    main()
