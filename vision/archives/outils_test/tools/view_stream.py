"""
view_stream.py : affiche dans OpenCV la video recue du PC de controle (tello/video), SANS envoyer de commande.

    python tools/view_stream.py                 # video + detection du cerceau (CNN E2), comme vision_node.py
    python tools/view_stream.py --no-detect     # video seule (+ cap, hauteur, cadence)

Touches : q / ESC quitter.
"""

import argparse
import os
import time

os.environ.setdefault("QT_QPA_FONTDIR", "/usr/share/fonts/truetype/dejavu")

import cv2  # noqa: E402
import numpy as np  # noqa: E402

from tellovision.link import VisionLink  # noqa: E402

BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--reseau", default="configs/reseau.yaml")
    ap.add_argument("--broker", default=None)
    ap.add_argument("--no-detect", action="store_true", help="video seule, sans le CNN")
    args = ap.parse_args()
    os.chdir(BASE_DIR)

    det = None
    if not args.no_detect:
        from tellovision.detector import HoopDetector, draw_detection
        print("Chargement du CNN...")
        det = HoopDetector()
    # identifiant distinct de vision_node.py et des autres lecteurs (sinon le broker les ejecte l'un l'autre)
    link = VisionLink(args.reseau, broker_ip=args.broker, client_id=f"tello_vision_viewer_{os.getpid()}")
    link.start()

    win = "Camera recue SANS CNN (tello/video)" if det is None else "Camera recue + CNN (view_stream)"
    cv2.namedWindow(win, cv2.WINDOW_AUTOSIZE | cv2.WINDOW_GUI_NORMAL)
    cv2.imshow(win, np.zeros((360, 480, 3), np.uint8))   # fenetre visible tout de suite, meme sans image
    print("En attente des images...")
    t_prev, fps = time.time(), 0.0
    try:
        while True:
            got = link.get_frame(timeout=0.5)
            if got is not None and got[1] is not None:
                header, img, _ = got
                now = time.time()
                fps = 0.9 * fps + 0.1 / max(now - t_prev, 1e-3)
                t_prev = now
                view = img
                if det is not None:
                    d = det(img, orig_size=(header.get("w", 960), header.get("h", 720)))
                    view = draw_detection(img, d)
                    if header.get("frame_id", 0) % 15 == 0:          # resume dans le terminal, ~1 fois/s
                        if d.present and d.center_drone is not None:
                            a, b, c = d.center_drone
                            print(f"#{header.get('frame_id')} CERCEAU p={d.p:.2f}  distance {d.distance_m:.2f} m  "
                                  f"avant {a:+.2f}  droite {b:+.2f}  haut {c:+.2f} m")
                        else:
                            print(f"#{header.get('frame_id')} pas de cerceau (p={d.p:.2f})")
                h = view.shape[0]
                cv2.putText(view, f"{fps:4.1f} i/s  yaw {header.get('yaw')}  tof {header.get('tof')} cm  #{header.get('frame_id')}",
                            (8, h - 10), cv2.FONT_HERSHEY_SIMPLEX, 0.5, (0, 255, 255), 1, cv2.LINE_AA)
                cv2.imshow(win, view)
            if (cv2.waitKey(1) & 0xFF) in (ord("q"), 27):
                break
    except KeyboardInterrupt:
        pass
    finally:
        link.stop()
        cv2.destroyAllWindows()
        print(f"{link.received} images recues, {link.dropped} sautees")


if __name__ == "__main__":
    main()
