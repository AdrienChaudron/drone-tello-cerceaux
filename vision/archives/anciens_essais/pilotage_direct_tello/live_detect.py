"""
live_detect.py : test du reseau en temps reel sur le flux du Tello (meme base que capture_live.py).

    flux video du Tello (30 i/s) -> derniere image -> CNN E2 -> ellipse -> pose 3D -> affichage OpenCV

Le drone NE DECOLLE PAS : il suffit de le tenir a la main et de viser le cerceau.
Le CNN traite ~15 images/s sur CPU : on prend toujours la DERNIERE image recue (sans file d'attente),
sinon le retard s'accumulerait.

Touches (dans la fenetre) :
    m   superposer / masquer le masque brut predit par le reseau (ce que le CNN "voit")
    s   enregistrer l'image affichee (logs/live/)
    r   demarrer / arreter l'enregistrement video (logs/live/)
    q   quitter (ou ESC)

Usage :  python tools/live_detect.py              (modele E2 par defaut)
         python tools/live_detect.py --run logs/E0_regression320_0
"""

import argparse
import csv
import os
import time

os.environ.setdefault("QT_QPA_FONTDIR", "/usr/share/fonts/truetype/dejavu")

import cv2  # noqa: E402
import numpy as np  # noqa: E402
from djitellopy import Tello  # noqa: E402

from tellovision.detector import HoopDetector, draw_detection  # noqa: E402

BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))   # racine du projet
OUT_DIR = os.path.join(BASE_DIR, "logs", "live")
FROZEN_S = 2.0           # image identique depuis plus de 2 s -> flux fige (Wi-Fi perdu ?)
KEEPALIVE_S = 10.0       # le Tello coupe la connexion s'il ne recoit plus de commande


def overlay_mask(view, prob):
    """Superpose la carte de probabilite 'tube' (rouge = probable) sur l'image."""
    heat = cv2.applyColorMap((cv2.resize(prob, (view.shape[1], view.shape[0])) * 255).astype(np.uint8),
                             cv2.COLORMAP_INFERNO)
    return cv2.addWeighted(view, 0.55, heat, 0.45, 0)


def status_bar(view, text, color=(0, 255, 255)):
    h = view.shape[0]
    cv2.rectangle(view, (0, h - 34), (view.shape[1], h), (0, 0, 0), -1)
    cv2.putText(view, text, (10, h - 10), cv2.FONT_HERSHEY_SIMPLEX, 0.6, color, 2, cv2.LINE_AA)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--run", default=os.path.join(BASE_DIR, "logs", "E2_segmentation480_0"))
    args = ap.parse_args()
    os.chdir(BASE_DIR)                                    # chemins des configs relatifs au projet
    os.makedirs(OUT_DIR, exist_ok=True)

    print("Chargement du reseau...")
    det = HoopDetector(args.run)                          # suivi actif : leve l'ambiguite de la normale
    tello = Tello()
    tello.connect()
    print(f"batterie : {tello.get_battery()} %")
    tello.streamon()
    frame_read = tello.get_frame_read()
    time.sleep(2)                                         # laisse le flux demarrer

    win = "Tello : detection du cerceau (CNN)"
    cv2.namedWindow(win, cv2.WINDOW_AUTOSIZE | cv2.WINDOW_GUI_NORMAL)
    show_mask, writer, n_snap = False, None, 0
    last_sig, last_change, last_keepalive = None, time.time(), time.time()
    t_hist = []
    log = open(os.path.join(OUT_DIR, f"live_{int(time.time())}.csv"), "w", newline="")
    w = csv.writer(log)
    w.writerow(["t", "present", "p", "u_px", "v_px", "avant_m", "droite_m", "haut_m", "distance_m", "lacet_droite_deg", "ambiguous"])
    t0 = time.time()
    try:
        while True:
            frame = frame_read.frame
            now = time.time()
            if now - last_keepalive > KEEPALIVE_S:        # garde la connexion ouverte
                try:
                    tello.send_keepalive()
                except Exception:
                    pass
                last_keepalive = now
            if frame is None:
                if (cv2.waitKey(30) & 0xFF) in (ord("q"), 27):
                    break
                continue
            img = cv2.cvtColor(frame, cv2.COLOR_RGB2BGR)

            sig = img[::40, ::40].tobytes()               # signature legere de l'image : le flux bouge-t-il ?
            if sig != last_sig:
                last_sig, last_change = sig, now
            frozen = now - last_change > FROZEN_S

            t1 = time.time()
            d = det(img)
            t_hist = (t_hist + [time.time() - t1])[-30:]

            view = overlay_mask(img, det.last_prob) if (show_mask and det.last_prob is not None) else img
            view = draw_detection(view, d)
            ms = 1000 * np.mean(t_hist)
            info = f"CNN+pose {ms:.0f} ms ({1000 / ms:.0f} i/s)   batterie {tello.get_battery()} %   " \
                   f"m: masque  s: photo  r: video{' [REC]' if writer else ''}  q: quitter"
            status_bar(view, info)
            if frozen:
                cv2.putText(view, "FLUX VIDEO FIGE : verifier le Wi-Fi du Tello", (40, view.shape[0] // 2),
                            cv2.FONT_HERSHEY_SIMPLEX, 1.1, (0, 0, 255), 3, cv2.LINE_AA)
            cv2.imshow(win, view)

            row = [round(now - t0, 3), int(d.present), round(d.p, 3)]
            if d.center_m is not None:
                row += [round(d.center_px[0], 1), round(d.center_px[1], 1)] + \
                       [round(float(v), 3) for v in d.center_drone] + \
                       [round(d.distance_m, 3), round(d.yaw_drone_deg, 1), int(d.ambiguous)]
            w.writerow(row)
            if writer is not None:
                writer.write(view)

            k = cv2.waitKey(1) & 0xFF
            if k in (ord("q"), 27):
                break
            elif k == ord("m"):
                show_mask = not show_mask
            elif k == ord("s"):
                n_snap += 1
                path = os.path.join(OUT_DIR, f"photo_{int(now * 1000)}.jpg")
                cv2.imwrite(path, view)
                print("photo :", path)
            elif k == ord("r"):
                if writer is None:
                    path = os.path.join(OUT_DIR, f"video_{int(now)}.mp4")
                    writer = cv2.VideoWriter(path, cv2.VideoWriter_fourcc(*"mp4v"), 12, (view.shape[1], view.shape[0]))
                    print("enregistrement :", path)
                else:
                    writer.release()
                    writer = None
                    print("enregistrement arrete")
    except KeyboardInterrupt:
        print("\nInterrompu (Ctrl+C)")
    finally:
        if writer is not None:
            writer.release()
        log.close()
        cv2.destroyAllWindows()
        try:
            tello.streamoff()
            tello.end()
        except Exception as exc:
            print("Fermeture de la connexion :", exc)
        print(f"Journal des detections : {OUT_DIR}/")


if __name__ == "__main__":
    main()
