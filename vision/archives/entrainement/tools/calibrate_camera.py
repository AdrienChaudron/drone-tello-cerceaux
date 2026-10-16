"""
calibrate_camera.py
Calibration de la camera du Tello avec un damier (docs/damier_9x6_27mm.pdf).

La calibration donne :
    - la matrice intrinseque K (focales fx, fy et centre optique cx, cy, en pixels)
    - les coefficients de distorsion de l'objectif grand angle (k1, k2, p1, p2, k3)
Elle doit etre faite a la resolution du flux video (960x720), celle des images du CNN et du vol.

1) Capture (drone allume, PC connecte a son Wi-Fi, damier imprime a 100 % et colle sur un carton rigide) :
       python tools/calibrate_camera.py capture
   Le damier detecte est dessine en couleur. Faire varier distance, inclinaison et position :
   le damier doit passer dans TOUS les coins de l'image (la distorsion est la plus forte sur les bords).
   La carte de couverture (en bas a droite) montre les zones deja couvertes.
       ESPACE   enregistrer l'image (seulement si le damier est detecte)
       a        capture automatique on/off (une image des que le damier a assez bouge)
       q / ESC  quitter
   Viser 25 a 40 images.

2) Calcul :
       python tools/calibrate_camera.py compute
   -> configs/camera.yaml + logs/calibration_check.jpg (image brute / image corrigee)
   Erreur de reprojection (RMS) : < 0.5 px = bonne calibration.
"""

import argparse
import glob
import math
import os
import time

# le Qt fourni avec opencv-python ne contient pas de polices : on lui indique celles du systeme
os.environ.setdefault("QT_QPA_FONTDIR", "/usr/share/fonts/truetype/dejavu")

import cv2  # noqa: E402
import numpy as np
import yaml

PATTERN = (9, 6)           # coins interieurs (colonnes, lignes)
SQUARE_MM = 27.0           # cote d'une case, a VERIFIER a la regle apres impression
CALIB_DIR = os.path.join("captures", "calibration")
OUT_YAML = os.path.join("configs", "camera.yaml")
FLAGS = cv2.CALIB_CB_ADAPTIVE_THRESH | cv2.CALIB_CB_NORMALIZE_IMAGE | cv2.CALIB_CB_FAST_CHECK


def find_corners_fast(gray):
    """Detection sur l'image reduite de moitie (apercu fluide) ; coins ramenes en pleine resolution."""
    small = cv2.resize(gray, None, fx=0.5, fy=0.5, interpolation=cv2.INTER_AREA)
    ok, corners = cv2.findChessboardCorners(small, PATTERN, FLAGS)
    return corners.reshape(-1, 1, 2).astype(np.float32) * 2 if ok else None


def find_corners(gray, refine=True):
    ok, corners = cv2.findChessboardCorners(gray, PATTERN, FLAGS)
    if not ok:
        return None
    corners = corners.reshape(-1, 1, 2).astype(np.float32)   # OpenCV 5 renvoie (N, 2)
    if refine:
        crit = (cv2.TERM_CRITERIA_EPS + cv2.TERM_CRITERIA_MAX_ITER, 30, 1e-3)
        corners = cv2.cornerSubPix(gray, corners, (11, 11), (-1, -1), crit)
    return corners


# ------------------------------------------------------------------ #
# Capture
# ------------------------------------------------------------------ #
def capture(args):
    from djitellopy import Tello
    os.makedirs(CALIB_DIR, exist_ok=True)
    n = len(glob.glob(os.path.join(CALIB_DIR, "*.jpg")))
    tello = Tello()
    tello.connect()
    print(f"batterie : {tello.get_battery()} %   |   {n} images deja dans {CALIB_DIR}")
    tello.streamon()
    reader = tello.get_frame_read()
    time.sleep(2)

    coverage = None
    last_saved = None
    auto = False
    win = "Calibration Tello"
    cv2.namedWindow(win, cv2.WINDOW_AUTOSIZE | cv2.WINDOW_GUI_NORMAL)
    print("Fenetre ouverte. Quitter avec q ou ESC dans la fenetre (pas Ctrl+C).")
    try:
        while True:
            frame = reader.frame
            if frame is None or frame.max() == 0:           # flux pas encore arrive
                wait = np.zeros((360, 640, 3), np.uint8)
                cv2.putText(wait, "En attente du flux video du Tello...", (40, 180),
                            cv2.FONT_HERSHEY_SIMPLEX, 0.8, (0, 255, 255), 2)
                cv2.imshow(win, wait)
                if (cv2.waitKey(50) & 0xFF) in (ord("q"), 27):
                    break
                continue
            img = cv2.cvtColor(frame, cv2.COLOR_RGB2BGR)
            gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
            if coverage is None:
                coverage = np.zeros(gray.shape, np.uint8)
            corners = find_corners_fast(gray)

            view = img.copy()
            if corners is not None:
                cv2.drawChessboardCorners(view, PATTERN, corners, True)
            moved = corners is not None and (last_saved is None or
                                             np.abs(corners - last_saved).mean() > args.min_move)
            mini = cv2.resize(cv2.cvtColor(coverage, cv2.COLOR_GRAY2BGR), (240, 180))
            view[-185:-5, -245:-5] = mini
            cv2.putText(view, f"{n} images  auto={'ON' if auto else 'off'}  ESPACE=enregistrer  a=auto  q=quitter",
                        (10, 25), cv2.FONT_HERSHEY_SIMPLEX, 0.6, (0, 255, 255), 2)
            cv2.imshow(win, view)
            k = cv2.waitKey(1) & 0xFF

            if corners is not None and ((k == 32) or (auto and moved)):
                path = os.path.join(CALIB_DIR, f"calib_{int(time.time() * 1000)}.jpg")
                cv2.imwrite(path, img, [cv2.IMWRITE_JPEG_QUALITY, 95])
                hull = cv2.convexHull(corners.reshape(-1, 2).astype(np.int32))
                cv2.fillConvexPoly(coverage, hull, 255)
                last_saved = corners
                n += 1
            elif k == ord("a"):
                auto = not auto
            elif k in (ord("q"), 27):
                break
    except KeyboardInterrupt:
        print("\nInterrompu (Ctrl+C) : fermeture propre...")
    finally:
        cv2.destroyAllWindows()
        try:
            tello.streamoff()
            tello.end()
        except Exception as exc:                            # le drone peut deja etre deconnecte
            print("Fermeture de la connexion :", exc)
    print(f"{n} images dans {CALIB_DIR}. Lancer ensuite : python tools/calibrate_camera.py compute")


# ------------------------------------------------------------------ #
# Calcul
# ------------------------------------------------------------------ #
def compute(args):
    paths = sorted(glob.glob(os.path.join(args.dir, "*.jpg")) + glob.glob(os.path.join(args.dir, "*.png")))
    objp = np.zeros((PATTERN[0] * PATTERN[1], 3), np.float32)
    objp[:, :2] = np.mgrid[0:PATTERN[0], 0:PATTERN[1]].T.reshape(-1, 2) * args.square_mm   # en mm
    obj_pts, img_pts, used, size = [], [], [], None
    for p in paths:
        gray = cv2.imread(p, cv2.IMREAD_GRAYSCALE)
        size = gray.shape[::-1]
        c = find_corners(gray)
        if c is None:
            print("  damier non detecte :", os.path.basename(p))
            continue
        obj_pts.append(objp)
        img_pts.append(c)
        used.append(p)
    if len(used) < 10:
        raise SystemExit(f"Seulement {len(used)} images exploitables : il en faut au moins 10 (idealement 25-40).")

    rms, K, dist, rvecs, tvecs = cv2.calibrateCamera(obj_pts, img_pts, size, None, None)
    per_img = []
    for o, i, r, t in zip(obj_pts, img_pts, rvecs, tvecs):
        proj, _ = cv2.projectPoints(o, r, t, K, dist)
        per_img.append(float(np.sqrt(np.mean(np.sum((proj.reshape(-1, 2) - i.reshape(-1, 2)) ** 2, axis=1)))))

    w, h = size
    fx, fy, cx, cy = K[0, 0], K[1, 1], K[0, 2], K[1, 2]
    hfov = 2 * math.degrees(math.atan(w / (2 * fx)))
    vfov = 2 * math.degrees(math.atan(h / (2 * fy)))
    dfov = 2 * math.degrees(math.atan(math.hypot(w, h) / (fx + fy)))
    print(f"\n{len(used)} images utilisees   |   erreur de reprojection RMS : {rms:.3f} px "
          f"({'bonne' if rms < 0.5 else 'acceptable' if rms < 1.0 else 'a refaire'})")
    print(f"fx = {fx:.1f}  fy = {fy:.1f}  cx = {cx:.1f}  cy = {cy:.1f}   (image {w}x{h})")
    print(f"champ de vision : horizontal {hfov:.1f} deg, vertical {vfov:.1f} deg, diagonal {dfov:.1f} deg "
          f"(constructeur : 82.6 deg en diagonale)")
    print("distorsion (k1, k2, p1, p2, k3) :", np.round(dist.ravel(), 4).tolist())
    worst = sorted(zip(per_img, used), reverse=True)[:3]
    print("images les moins bien expliquees :", [(os.path.basename(p), round(e, 2)) for e, p in worst])

    os.makedirs(os.path.dirname(OUT_YAML), exist_ok=True)
    with open(OUT_YAML, "w") as f:
        yaml.safe_dump({
            "image_size": [int(w), int(h)],
            "camera_matrix": np.round(K, 4).tolist(),
            "dist_coeffs": np.round(dist.ravel(), 6).tolist(),
            "rms_px": round(float(rms), 4),
            "n_images": len(used),
            "pattern_inner_corners": list(PATTERN),
            "square_mm": args.square_mm,
        }, f, sort_keys=False)
    print("Calibration enregistree :", OUT_YAML)

    img = cv2.imread(used[int(np.argmax([abs(c.reshape(-1, 2) - [w / 2, h / 2]).max() for c in img_pts]))])
    und = cv2.undistort(img, K, dist)
    for im in (img, und):
        for x in range(0, w, 80):
            cv2.line(im, (x, 0), (x, h), (0, 255, 255), 1)
    both = np.hstack([img, und])
    cv2.putText(both, "brute", (10, 30), cv2.FONT_HERSHEY_SIMPLEX, 1, (0, 0, 255), 2)
    cv2.putText(both, "corrigee", (w + 10, 30), cv2.FONT_HERSHEY_SIMPLEX, 1, (0, 0, 255), 2)
    os.makedirs("logs", exist_ok=True)
    cv2.imwrite(os.path.join("logs", "calibration_check.jpg"), both)
    print("Controle visuel : logs/calibration_check.jpg (les bords du damier doivent devenir droits)")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("mode", choices=["capture", "compute"])
    ap.add_argument("--dir", default=CALIB_DIR, help="(compute) dossier des images du damier")
    ap.add_argument("--square-mm", type=float, default=SQUARE_MM, help="cote mesure d'une case, en mm")
    ap.add_argument("--min-move", type=float, default=40.0,
                    help="(capture auto) deplacement moyen minimal des coins entre deux images, en px")
    args = ap.parse_args()
    capture(args) if args.mode == "capture" else compute(args)


if __name__ == "__main__":
    main()
