"""
mesure_retard.py : mesure EN VOL du retard de la camera du Tello par rapport a son cap (IMU), sans rien publier.

Principe : le cap "yaw" de l'en-tete des images est lu sur le drone au moment de l'envoi (quasi a jour) ; l'image,
elle, a traverse l'encodage H.264, le Wi-Fi et le decodage (djitellopy) : elle est plus vieille. Quand le drone
tourne (paliers de recherche), la scene se decale horizontalement dans l'image ; on mesure ce decalage d'une image a
la suivante (correlation de phase), on en deduit la vitesse de rotation "vue par la camera", et on la compare a la
vitesse de rotation du cap : le decalage temporel qui les fait coincider est le RETARD DE LA CAMERA.
Mesure aussi le transport : instant de reception - horodatage "t" de l'en-tete (horloges des deux PC supposees
synchronisees).

Usage :
    python tools/mesure_retard.py                    # ecoute (Ctrl+C pour finir), estimation toutes les 20 s
    python tools/mesure_retard.py --analyse logs/retard/retard_<horodatage>.npz
Il faut que le drone TOURNE pendant l'ecoute (une recherche par paliers suffit).
"""

import argparse
import json
import math
import os
import socket
import struct
import threading
import time

import cv2
import numpy as np
import paho.mqtt.client as mqtt
import yaml

BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
OUT_DIR = os.path.join(BASE_DIR, "logs", "retard")
FX_960 = 926.0                     # focale de la camera (pixels, image 960x720 : configs/camera.yaml)


def _vitesses(t, yaw, rot_img, pas):
    g = np.arange(t[0], t[-1], pas)
    k = max(1, int(0.2 / pas))                                  # lissage 0,2 s (bruit de la correlation de phase)
    noyau = np.ones(k) / k
    v_cap = np.convolve(np.gradient(np.interp(g, t, yaw), pas), noyau, "same")
    v_img = np.convolve(np.gradient(np.interp(g, t, rot_img), pas), noyau, "same")
    return g, v_cap, v_img


def estime(t, yaw, rot_img, lag_max=15.0, pas=0.033, calme_s=3.0):
    """
    t : instants des images (en-tete) ; yaw : cap de l'en-tete (deg, deroule) ; rot_img : rotation cumulee vue dans
    l'image (deg). Retard > 0 : image en retard sur le cap. Renvoie None (pas assez de rotation) ou un dict :
      depart  : retards mesures sur les DEPARTS de rotation precedes d'au moins calme_s s d'immobilite
                (non ambigu : un seul depart a apparier) ;
      pics    : retards candidats par correlation des vitesses (ambigu si les paliers sont periodiques :
                retard + k x periode donnent la meme correlation) ;
      actif   : part du temps ou le drone tourne.
    """
    if len(t) < 60:
        return None
    g, v_cap, v_img = _vitesses(t, yaw, rot_img, pas)
    actif = float(np.mean(np.abs(v_cap) > 5.0))
    if actif < 0.05:
        return None
    # 1) departs de rotation apres une longue immobilite
    depart = []
    bouge_cap, bouge_img = np.abs(v_cap) > 10.0, np.abs(v_img) > 10.0
    n_calme = int(calme_s / pas)
    for i in range(n_calme, len(g)):
        if bouge_cap[i] and not bouge_cap[i - n_calme:i].any():
            j = np.where(bouge_img[i:i + int(lag_max / pas)])[0]
            if len(j) and not bouge_img[max(0, i - n_calme):i].any():
                depart.append(round(float(j[0] * pas), 2))
    # 2) correlation des vitesses : tous les maxima locaux proches du meilleur
    cs = []
    for n in range(0, int(lag_max / pas)):
        a, b = v_cap[: len(v_cap) - n], v_img[n:]
        if len(a) < 30:
            break
        cs.append(np.corrcoef(a, b)[0, 1])
    cs = np.array(cs)
    pics = [(round(n * pas, 2), round(float(cs[n]), 2)) for n in range(1, len(cs) - 1)
            if cs[n] >= cs[n - 1] and cs[n] >= cs[n + 1] and cs[n] >= 0.8 * cs.max()]
    return {"depart": depart, "pics": pics, "actif": actif}


def texte(r):
    if r is None:
        return "pas assez de rotation pour estimer le retard"
    d = (f"RETARD CAMERA (departs apres immobilite) = {np.median(r['depart']):.2f} s {r['depart']}"
         if r["depart"] else "aucun depart apres immobilite (>= 3 s) dans la fenetre")
    return d + f" ; candidats par correlation : {r['pics']} ; rotation {100 * r['actif']:.0f} % du temps"


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--reseau", default="configs/reseau.yaml")
    ap.add_argument("--broker", default=None)
    ap.add_argument("--fenetre", type=float, default=60.0, help="duree analysee a chaque estimation (s)")
    ap.add_argument("--periode", type=float, default=20.0, help="estimation toutes les N s")
    ap.add_argument("--analyse", metavar="NPZ", help="analyser un enregistrement existant")
    args = ap.parse_args()
    os.chdir(BASE_DIR)

    if args.analyse:
        z = np.load(args.analyse)
        r = estime(z["t"], z["yaw"], z["rot"])
        print(f"{len(z['t'])} images ; transport median {1000 * np.median(z['transport']):.0f} ms")
        print(texte(r))
        return

    cfg = yaml.safe_load(open(args.reseau))
    if args.broker:
        cfg["broker_ip"] = args.broker
    os.makedirs(OUT_DIR, exist_ok=True)
    path = os.path.join(OUT_DIR, f"retard_{int(time.time())}.npz")
    lock = threading.Lock()
    dern = {"msg": None}
    data = {"t": [], "yaw": [], "rot": [], "transport": []}

    def on_msg(c, u, m):
        with lock:
            dern["msg"] = (time.time(), m.payload)           # on ne garde que la derniere (le calcul suit)

    cl = mqtt.Client(mqtt.CallbackAPIVersion.VERSION2,
                     client_id=f"tello_mesure_retard_{socket.gethostname()}_{os.getpid()}")
    if cfg.get("username"):
        cl.username_pw_set(cfg["username"], cfg.get("password"))
    cl.on_message = on_msg
    cl.on_connect = lambda c, u, f, rc, p: c.subscribe(cfg["topic_video"], qos=0)
    cl.connect(cfg["broker_ip"], cfg["port"], 30)
    cl.loop_start()
    print(f"Ecoute de {cfg['topic_video']} sur {cfg['broker_ip']} ; enregistrement : {path}", flush=True)

    prev, rot, yaw_unwrap, yaw_prev = None, 0.0, None, None
    t_est = time.time()
    try:
        while True:
            with lock:
                got, dern["msg"] = dern["msg"], None
            if got is None:
                time.sleep(0.005)
                continue
            t_rx, payload = got
            n = struct.unpack(">I", payload[:4])[0]
            h = json.loads(payload[4:4 + n])
            img = cv2.imdecode(np.frombuffer(payload[4 + n:], np.uint8), cv2.IMREAD_GRAYSCALE)
            if img is None:
                continue
            small = cv2.resize(img, (320, int(320 * img.shape[0] / img.shape[1]))).astype(np.float32)
            if prev is not None and small.shape == prev.shape:
                (dx, _), _ = cv2.phaseCorrelate(prev, small, cv2.createHanningWindow(small.shape[::-1], cv2.CV_32F))
                fx = FX_960 * small.shape[1] / 960.0
                rot += -math.degrees(math.atan2(dx, fx))           # scene vers la gauche = drone tourne a droite
            prev = small
            y = float(h["yaw"])
            if yaw_unwrap is None:
                yaw_unwrap = y
            else:
                yaw_unwrap += (y - yaw_prev + 180.0) % 360.0 - 180.0
            yaw_prev = y
            data["t"].append(float(h["t"])); data["yaw"].append(yaw_unwrap); data["rot"].append(rot)
            data["transport"].append(t_rx - float(h["t"]))
            if time.time() - t_est >= args.periode:
                t_est = time.time()
                t = np.array(data["t"]); m = t >= t[-1] - args.fenetre
                r = estime(t[m], np.array(data["yaw"])[m], np.array(data["rot"])[m])
                tr = 1000 * np.median(np.array(data["transport"])[m])
                print(time.strftime("%H:%M:%S ") + f"{m.sum()} images, transport {tr:.0f} ms ; " + texte(r),
                      flush=True)
                np.savez(path, **{k: np.array(v) for k, v in data.items()})
    except KeyboardInterrupt:
        pass
    finally:
        cl.loop_stop()
        cl.disconnect()
        np.savez(path, **{k: np.array(v) for k, v in data.items()})
        print(f"Enregistrement : {path}")


if __name__ == "__main__":
    main()
