"""
Tello_CL_Z_photo.py
Montée en altitude (Z) par correcteur P en boucle fermée, stabilisation, puis prise de photos.
Basé sur la structure de Tello_CL_yaw_control.py (threads register / send_rc / boucle de commande).

Séquence :
    décollage -> pour chaque hauteur et chaque angle de lacet demandés :
        aller à la pose (P sur Z, P sur le lacet) -> attendre la stabilisation -> N photos
    -> atterrissage

Modèle supposé pour Z (comme pour le lacet au Lab 1) :
        Z(s)/U(s) = K_Z / ( s (1 + T_Z s) )
    Z en cm (get_distance_tof), U = commande up_down en %  ->  K_Z en (cm/s)/%.
Le gain kp_z est calculé comme au §1.2.4 : zeta imposé par le dépassement voulu,
puis omega_n = 1/(2 zeta T), kp = omega_n^2 T / K.

Exemples :
    python Tello_CL_Z_photo.py --label hoop --heights 100,150,200 --yaws -30,0,30 --photos 5
    python Tello_CL_Z_photo.py --label no_hoop --heights 150 --photos 20 --plot
"""

import argparse
import csv
import math
import os
import threading
import time

import cv2
from djitellopy import Tello

# ------------------------------------------------------------------ #
# A RENSEIGNER : paramètres identifiés pour l'axe Z
# ------------------------------------------------------------------ #
K_Z = None     # gain du modèle Z, en (cm/s) par % de commande
T_Z = None     # constante de temps du modèle Z, en s
KP_Z = None    # optionnel : impose directement kp_z (en %/cm) et ignore K_Z / T_Z
OVERSHOOT_PCT = 4.3   # dépassement visé (même valeur que le cahier des charges du Lab 1)

# ------------------------------------------------------------------ #
# Autres réglages
# ------------------------------------------------------------------ #
Ts = 0.015            # période de la boucle de commande (s), comme dans vos scripts
KP_YAW = 2.5          # gain P du lacet (valeur de Tello_CL_yaw_control.py)
MAX_RC_Z = 50         # saturation de la commande verticale (%), prudente
MAX_RC_YAW = 60       # saturation de la commande de lacet (%)
TOL_Z = 5             # tolérance sur Z pour considérer la consigne atteinte (cm)
TOL_YAW = 3           # tolérance sur le lacet (degrés)
HOLD_S = 1.5          # durée pendant laquelle l'erreur doit rester faible (s)
SETTLE_TIMEOUT = 20   # temps max pour atteindre une pose (s)
Z_MIN, Z_MAX = 40, 250   # plage de hauteurs acceptée (cm) : capteur ToF fiable, cage/plafond
TOF_MAX_VALID = 500   # au-delà, la lecture ToF est considérée invalide (ex. 6553 au décollage)
BLUR_THRESHOLD = 60.0 # variance du Laplacien minimale pour accepter une photo
FRAME_IS_RGB = True   # passer à False si les couleurs paraissent inversées

# ------------------------------------------------------------------ #
# Variables globales partagées entre threads
# ------------------------------------------------------------------ #
RC_Z = RC_YAW = 0
Z_ref = YAW_ref = 0.0
Z_meas = YAW_meas = 0.0
last_tof = 0.0
Controling = False
Registering = False

LOG_FILE = "dataCL_Z_photo.txt"


# ------------------------------------------------------------------ #
# Outils
# ------------------------------------------------------------------ #
def saturation(val, vmin, vmax):
    return max(vmin, min(vmax, val))


def wrap180(angle):
    """Ramène un angle en degrés dans [-180, 180]."""
    return (angle + 180.0) % 360.0 - 180.0


def compute_kp_z():
    if KP_Z is not None:
        print(f"kp_z imposé : {KP_Z}")
        return KP_Z
    if K_Z is None or T_Z is None:
        raise SystemExit("Renseignez K_Z et T_Z (ou KP_Z) en haut du fichier avant de lancer.")
    d = OVERSHOOT_PCT / 100.0
    zeta = -math.log(d) / math.sqrt(math.pi ** 2 + math.log(d) ** 2)
    wn = 1.0 / (2.0 * zeta * T_Z)          # imposé par T avec un simple P
    kp = wn ** 2 * T_Z / K_Z
    print(f"zeta = {zeta:.3f}   wn = {wn:.2f} rad/s   kp_z = {kp:.4f} %/cm   "
          f"(temps de réponse à 5 % attendu ~ {3.0 / (zeta * wn):.2f} s)")
    return kp


def read_tof():
    """Lecture ToF (cm) en rejetant les valeurs aberrantes (ex. 6553 juste après le décollage)."""
    global last_tof
    v = tello.get_distance_tof()
    if 0 < v < TOF_MAX_VALID:
        last_tof = v
    return last_tof


def sharpness(img):
    gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
    return cv2.Laplacian(gray, cv2.CV_64F).var()


# ------------------------------------------------------------------ #
# Threads (même organisation que Tello_CL_yaw_control.py)
# ------------------------------------------------------------------ #
def control_loop(kp_z):
    """Correcteurs P sur Z et sur le lacet, recalculés toutes les Ts (équivalent de go_to_position)."""
    global RC_Z, RC_YAW, Z_meas, YAW_meas
    while Controling:
        Z_meas = read_tof()
        YAW_meas = tello.get_yaw()

        e_z = Z_ref - Z_meas
        RC_Z = int(saturation(kp_z * e_z, -MAX_RC_Z, MAX_RC_Z))

        e_yaw = wrap180(YAW_ref - YAW_meas)
        RC_YAW = int(saturation(KP_YAW * e_yaw, -MAX_RC_YAW, MAX_RC_YAW))

        time.sleep(Ts)


def send_rc():
    """Envoi continu des commandes au drone."""
    while Controling:
        tello.send_rc_control(0, 0, RC_Z, RC_YAW)
        time.sleep(Ts)


def register(start_time):
    """Enregistre : t, altitude, commande Z, consigne Z, lacet, commande lacet, consigne lacet."""
    print("Registering")
    with open(LOG_FILE, "w") as f:
        while Registering:
            t = time.time() - start_time
            f.write(f"{t} {Z_meas} {RC_Z} {Z_ref} {YAW_meas} {RC_YAW} {YAW_ref}\n")
            time.sleep(Ts)
    print("Done registering")


# ------------------------------------------------------------------ #
# Séquence : aller à une pose, puis photographier
# ------------------------------------------------------------------ #
def go_to_pose(z, yaw):
    """Fixe les consignes et attend que Z et lacet soient stabilisés. Renvoie True si atteint."""
    global Z_ref, YAW_ref
    Z_ref, YAW_ref = float(z), float(yaw)
    t0 = time.time()
    ok_since = None
    while time.time() - t0 < SETTLE_TIMEOUT:
        ok = (abs(Z_ref - Z_meas) <= TOL_Z) and (abs(wrap180(YAW_ref - YAW_meas)) <= TOL_YAW)
        if ok:
            if ok_since is None:
                ok_since = time.time()
            elif time.time() - ok_since >= HOLD_S:
                return True
        else:
            ok_since = None
        time.sleep(0.02)
    return False


def take_photos(reader, n, label, out_dir, writer, counters, interval):
    taken, tries = 0, 0
    while taken < n and tries < 5 * n:
        frame = reader.frame
        tries += 1
        if frame is not None:
            img = cv2.cvtColor(frame, cv2.COLOR_RGB2BGR) if FRAME_IS_RGB else frame.copy()
            if sharpness(img) >= BLUR_THRESHOLD:
                counters[label] += 1
                name = f"{label}_{int(time.time() * 1000)}_{counters[label]:05d}.jpg"
                cv2.imwrite(os.path.join(out_dir, label, name), img, [cv2.IMWRITE_JPEG_QUALITY, 95])
                writer.writerow([os.path.join(label, name), label, f"{time.time():.3f}",
                                 f"{YAW_meas:.1f}", f"{Z_meas:.1f}", tello.get_battery()])
                taken += 1
        time.sleep(interval)
    return taken


def plot_log():
    import matplotlib.pyplot as plt
    d = [list(map(float, l.split())) for l in open(LOG_FILE) if l.strip()]
    t, z, rcz, zr, yw, rcy, yr = zip(*d)
    fig, (a1, a2, a3) = plt.subplots(3, 1, sharex=True)
    a1.plot(t, z); a1.plot(t, zr); a1.legend(["Altitude (cm)", "Consigne Z (cm)"])
    a2.plot(t, yw); a2.plot(t, yr); a2.legend(["Lacet (°)", "Consigne lacet (°)"])
    a3.plot(t, rcz); a3.plot(t, rcy); a3.legend(["Commande Z (%)", "Commande lacet (%)"])
    plt.xlabel("Time (s)")
    plt.show()


# ------------------------------------------------------------------ #
# Programme principal
# ------------------------------------------------------------------ #
def main():
    global tello, Controling, Registering, Z_ref, YAW_ref, Z_meas, YAW_meas

    p = argparse.ArgumentParser()
    p.add_argument("--label", choices=["hoop", "no_hoop"], default="hoop")
    p.add_argument("--heights", default="150", help="hauteurs en cm, séparées par des virgules")
    p.add_argument("--yaws", default="0", help="angles de lacet en °, séparés par des virgules")
    p.add_argument("--photos", type=int, default=5, help="photos par pose")
    p.add_argument("--interval", type=float, default=0.4, help="pause entre deux photos (s)")
    p.add_argument("--out", default="captures")
    p.add_argument("--res", choices=["720", "480"], default="720")
    p.add_argument("--plot", action="store_true", help="trace les courbes de suivi à la fin")
    args = p.parse_args()

    heights = [float(h) for h in args.heights.split(",")]
    yaws = [float(y) for y in args.yaws.split(",")]
    for h in heights:
        if not (Z_MIN <= h <= Z_MAX):
            raise SystemExit(f"Hauteur {h} cm hors plage [{Z_MIN}, {Z_MAX}] cm.")

    kp_z = compute_kp_z()

    for l in ("hoop", "no_hoop"):
        os.makedirs(os.path.join(args.out, l), exist_ok=True)
    counters = {l: len([f for f in os.listdir(os.path.join(args.out, l)) if f.endswith(".jpg")])
                for l in ("hoop", "no_hoop")}
    meta_path = os.path.join(args.out, "metadata.csv")
    new_file = not os.path.exists(meta_path)
    meta_f = open(meta_path, "a", newline="")
    writer = csv.writer(meta_f)
    if new_file:
        writer.writerow(["file", "label", "timestamp", "yaw", "tof_cm", "battery"])

    tello = Tello()
    tello.connect()
    print(f"battery: {tello.get_battery()} %")
    tello.set_video_resolution(Tello.RESOLUTION_720P if args.res == "720" else Tello.RESOLUTION_480P)
    tello.set_video_fps(Tello.FPS_30)
    tello.streamon()
    reader = tello.get_frame_read()
    time.sleep(3)

    start_time = time.time()
    Registering = True
    t_reg = threading.Thread(target=register, args=(start_time,))
    t_reg.start()
    t_ctl = t_snd = None

    try:
        tello.takeoff()
        time.sleep(3)

        # Initialisation : la consigne de départ = état courant (pas de mouvement parasite)
        Z_meas = read_tof()
        YAW_meas = tello.get_yaw()
        Z_ref, YAW_ref = Z_meas, YAW_meas

        Controling = True
        t_ctl = threading.Thread(target=control_loop, args=(kp_z,))
        t_snd = threading.Thread(target=send_rc)
        t_ctl.start()
        t_snd.start()

        total = 0
        for h in heights:
            for y in yaws:
                print(f"-> pose : Z = {h:.0f} cm, lacet = {y:.0f}°")
                if not go_to_pose(h, y):
                    print("   ATTENTION : pose non stabilisée dans le délai imparti, photos prises quand même")
                total += take_photos(reader, args.photos, args.label, args.out, writer,
                                     counters, args.interval)
        print(f"{total} photos enregistrées (label {args.label})")

    finally:
        Controling = False
        for t in (t_ctl, t_snd):
            if t is not None:
                t.join()
        try:
            tello.send_rc_control(0, 0, 0, 0)
            time.sleep(1)
            tello.land()
        finally:
            Registering = False
            t_reg.join()
            tello.streamoff()
            tello.end()
            meta_f.close()

    if args.plot:
        plot_log()


if __name__ == "__main__":
    main()
