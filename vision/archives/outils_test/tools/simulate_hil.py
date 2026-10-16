"""
simulate_hil.py : remplace le PC du collegue pour tester vision_node.py SANS drone.

Publie des images enregistrees (reduites en 480x360, comme le fera son PC) sur tello/video avec un en-tete
(frame_id, t, w, h, yaw, tof), et affiche les ORDRES recus sur tello/vision/ordre (envoyes par vision_node.py avec
TelloInterface.send_vision). Les images ne bougent pas : le "drone" simule garde un cap et une hauteur fixes.
--suivre : le cap suit r_yaw, et la hauteur r_z quand elle est donnee.
Cela sert a verifier le format des messages, le debit et le retard, pas la machine a etats (cote PC de controle).

Usage (broker Mosquitto local) :
    python tools/simulate_hil.py --images "captures/hoop/frame_*_17905873*.jpg" --fps 15
    python tools/vision_node.py --broker 127.0.0.1          (dans un autre terminal)
"""

import argparse
import glob
import json
import os
import random
import re
import threading
import time

import cv2
import paho.mqtt.client as mqtt
import yaml

from tellovision.link import encode_frame
from tellovision.ordres import wrap180

BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


def archive_loop(cl, state, hz=30.0):
    """
    Role du PC de controle pour l'IHM : boucles d'asservissement SIMULEES, publiees comme archive_sys_result()
    (tello/archive/<axe> : {timestamp, reference, command, measure}).
      Z, YAW : regulateur P (gains 1 et 2, comme TELLO.py) sur un drone simule (vitesse ~ commande rc).
      X, Y   : non asservis (comme chez lui) : commande = consigne, mesure = angle de roulis / tangage bruite.
    Independant de la video (les images enregistrees ne bougent pas).
    """
    z, yaw, dt = 100.0, 0.0, 1.0 / hz
    while True:
        t = time.time()
        ref_z, ref_yaw = state.get("target_z", z), state.get("target_yaw", yaw)
        cmd_z = max(-100.0, min(100.0, 1.0 * (ref_z - z)))
        err_yaw = wrap180(ref_yaw - yaw)
        cmd_yaw = max(-100.0, min(100.0, 2.0 * err_yaw))
        z += 0.8 * cmd_z * dt + random.gauss(0, 0.6)                 # ~0,8 cm/s par point de rc + bruit ToF
        yaw = wrap180(yaw + 0.9 * cmd_yaw * dt + random.gauss(0, 0.15))
        cx, cy = state.get("cmd_x", 0.0), state.get("cmd_y", 0.0)
        axes = {"X": (cx, int(cx), random.gauss(0, 1.5)), "Y": (cy, int(cy), random.gauss(0, 1.5)),
                "Z": (ref_z, int(cmd_z), z), "YAW": (ref_yaw, int(cmd_yaw), yaw)}
        for name, (ref, cmd, meas) in axes.items():
            cl.publish(f"tello/archive/{name}", json.dumps(
                {"timestamp": t, "reference": round(ref, 2), "command": cmd, "measure": round(meas, 2)}), qos=0)
        time.sleep(max(0.0, dt - (time.time() - t)))


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--images", default="captures/hoop/*.jpg")
    ap.add_argument("--fps", type=float, default=15.0)
    ap.add_argument("--broker", default="127.0.0.1")
    ap.add_argument("--reseau", default="configs/reseau.yaml")
    ap.add_argument("--suivre", action="store_true", help="le cap suit r_yaw, la hauteur r_z (recherche)")
    ap.add_argument("--loop", action="store_true", help="reprendre au debut a la fin des images")
    ap.add_argument("--status", action="store_true",
                    help="IHM : publier aussi un faux etat du drone (tello/status, 1/s) et des boucles "
                         "d'asservissement simulees (tello/archive/<axe>, 30/s)")
    args = ap.parse_args()
    os.chdir(BASE_DIR)
    cfg = yaml.safe_load(open(args.reseau))

    ts = lambda p: int(m.group(1)) if (m := re.search(r"_(\d{10,})\.\w+$", p)) else 0
    paths = sorted(glob.glob(args.images), key=ts)
    if not paths:
        raise SystemExit(f"aucune image : {args.images}")
    print(f"{len(paths)} images, {args.fps} i/s")

    state = {"yaw": 0.0, "tof": 100.0, "target_yaw": 0.0, "target_z": 100.0, "n_cmd": 0}

    def on_message(client, userdata, msg):
        o = json.loads(msg.payload)
        state["target_yaw"] = float(o["r_yaw"])
        if o.get("r_z") is not None:
            state["target_z"] = float(o["r_z"])
        state["n_cmd"] += 1
        if state["n_cmd"] % 5 == 1:
            print(f"ordre {state['n_cmd']:4d} : " + ", ".join(f"{k}={o.get(k)}" for k in (
                "frame_id", "etat", "present", "delta_x", "delta_z", "distance", "r_yaw", "r_z")))

    cl = mqtt.Client(mqtt.CallbackAPIVersion.VERSION2, client_id="tello_hil_simu")
    if cfg.get("username"):
        cl.username_pw_set(cfg["username"], cfg.get("password"))
    cl.on_message = on_message
    cl.on_connect = lambda c, u, f, rc, p: c.subscribe(cfg["topic_vision"])
    cl.connect(args.broker, cfg["port"])
    cl.loop_start()
    if args.status:
        threading.Thread(target=archive_loop, args=(cl, state), daemon=True).start()

    period, fid, t0 = 1.0 / args.fps, 0, time.time()
    t_status = 0.0
    try:
        while True:
            for p in paths:
                t_next = t0 + fid * period
                time.sleep(max(0.0, t_next - time.time()))
                if args.suivre:                                      # cap et hauteur : 1er ordre vers la consigne
                    state["yaw"] = wrap180(state["yaw"] + 0.3 * wrap180(state["target_yaw"] - state["yaw"]))
                    state["tof"] += 0.3 * (state["target_z"] - state["tof"])
                img = cv2.imread(p)
                h, w = img.shape[:2]
                small = cv2.resize(img, (480, 360), interpolation=cv2.INTER_AREA)
                header = {"frame_id": fid, "t": time.time(), "w": w, "h": h,
                          "yaw": round(state["yaw"], 1), "tof": round(state["tof"], 1)}
                cl.publish(cfg["topic_video"], encode_frame(header, small), qos=0)
                fid += 1
                if args.status and time.time() - t_status >= 1.0:   # role du PC de controle : etat du drone
                    t_status = time.time()
                    vol = t_status - t0
                    cl.publish("tello/status", json.dumps({
                        "battery": max(5, int(100 - vol / 6)),        # -1 % toutes les 6 s (simulation)
                        "tof": round(state["tof"], 1), "yaw": round(state["yaw"], 1),
                        "temp": round(55 + vol / 30, 1), "temperature": round(55 + vol / 30, 1),   # "temperature" : nom lu par la page
                        "flight_time": int(vol), "t": t_status}), qos=0)
            if not args.loop:
                break
    except KeyboardInterrupt:
        pass
    finally:
        time.sleep(0.5)
        cl.loop_stop()
        cl.disconnect()
        print(f"{fid} images publiees, {state['n_cmd']} ordres recus")


if __name__ == "__main__":
    main()
