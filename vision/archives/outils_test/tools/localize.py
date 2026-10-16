"""
localize.py : localisation 2D / 3D du cerceau, image par image.

Deux sources possibles :
    python tools/localize.py --images "captures/hoop/frame_*_17907*.jpg"   # sequence enregistree -> video
    python tools/localize.py --tello                                       # flux du Tello en direct (moteurs coupes)

Affiche (et enregistre) l'ellipse, le centre 3D projete (croix jaune), la distance, la position (x, y, z)
du centre du cerceau dans le repere camera et le lacet pour s'aligner sur sa normale.
Le suivi d'une image a l'autre sert a lever l'ambiguite double de l'orientation.
Le drone ne decolle PAS : ce script ne fait que regarder.
"""

import argparse
import csv
import glob
import os
import re
import time

os.environ.setdefault("QT_QPA_FONTDIR", "/usr/share/fonts/truetype/dejavu")

import cv2  # noqa: E402

from tellovision.detector import HoopDetector, draw_detection  # noqa: E402


def sorted_by_time(paths):
    def ts(p):
        m = re.search(r"_(\d{10,})\.\w+$", p)
        return int(m.group(1)) if m else 0
    return sorted(paths, key=ts)


def main():
    ap = argparse.ArgumentParser()
    src = ap.add_mutually_exclusive_group(required=True)
    src.add_argument("--images", help="motif glob d'images, lues dans l'ordre chronologique")
    src.add_argument("--tello", action="store_true", help="flux video du Tello (sans decollage)")
    ap.add_argument("--run", default="logs/E3_segmentation480_couleur_0")
    ap.add_argument("--out", default="logs/localisation")
    ap.add_argument("--no-window", action="store_true", help="ne pas afficher (calcul seul)")
    args = ap.parse_args()

    det = HoopDetector(args.run)
    os.makedirs(os.path.dirname(args.out) or ".", exist_ok=True)
    writer, log = None, open(args.out + ".csv", "w", newline="")
    w = csv.writer(log)
    w.writerow(["t", "present", "p", "u_px", "v_px", "avant_m", "droite_m", "haut_m", "distance_m", "lacet_droite_deg", "ambiguous"])

    tello = reader = None
    if args.tello:
        from djitellopy import Tello
        tello = Tello()
        tello.connect()
        print(f"batterie : {tello.get_battery()} %")
        tello.streamon()
        reader = tello.get_frame_read()
        time.sleep(2)
        frames = iter(int, 1)                                   # boucle infinie
    else:
        frames = sorted_by_time(glob.glob(args.images))
        print(f"{len(frames)} images")

    if not args.no_window:
        cv2.namedWindow("Localisation", cv2.WINDOW_AUTOSIZE | cv2.WINDOW_GUI_NORMAL)
    t_start, n, t_det = time.time(), 0, 0.0
    try:
        for f in frames:
            if args.tello:
                if reader.frame is None:
                    continue
                img = cv2.cvtColor(reader.frame, cv2.COLOR_RGB2BGR)
            else:
                img = cv2.imread(f)
            t0 = time.time()
            d = det(img)
            t_det += time.time() - t0
            n += 1
            view = draw_detection(img, d)
            fps = n / max(t_det, 1e-6)
            cv2.putText(view, f"{fps:.1f} img/s (calcul)", (view.shape[1] - 290, 40),
                        cv2.FONT_HERSHEY_SIMPLEX, 0.8, (0, 255, 255), 2)
            if writer is None:
                writer = cv2.VideoWriter(args.out + ".mp4", cv2.VideoWriter_fourcc(*"mp4v"), 5 if not args.tello else 10,
                                         (view.shape[1], view.shape[0]))
            writer.write(view)
            row = [round(time.time() - t_start, 3), int(d.present), round(d.p, 3)]
            if d.center_m is not None:
                row += [round(d.center_px[0], 1), round(d.center_px[1], 1)] + [round(float(v), 3) for v in d.center_drone] \
                       + [round(d.distance_m, 3), round(d.yaw_drone_deg, 1), int(d.ambiguous)]
            w.writerow(row)
            if not args.no_window:
                cv2.imshow("Localisation", view)
                if (cv2.waitKey(1) & 0xFF) in (ord("q"), 27):
                    break
    except KeyboardInterrupt:
        pass
    finally:
        if writer is not None:
            writer.release()
        log.close()
        cv2.destroyAllWindows()
        if tello is not None:
            try:
                tello.streamoff()
                tello.end()
            except Exception as exc:
                print("Fermeture :", exc)
    print(f"{n} images, calcul moyen {1000 * t_det / max(n, 1):.0f} ms/image -> {args.out}.mp4 et {args.out}.csv")


if __name__ == "__main__":
    main()
