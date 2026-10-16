"""
detector.py : chaine complete de localisation du cerceau sur une image.

    image BGR (960x720) -> CNN (E2 : segmentation de l'anneau) -> ellipse -> pose 3D (pose.py)

Sorties (classe Detection) :
    present, p             le cerceau est-il dans l'image ? (probabilite p)
    ellipse                (cx, cy, A, B, theta) en pixels
    center_px              CENTRE 2D DU CERCEAU = projection de son centre 3D (et non le centre de l'ellipse,
                           decale par la perspective quand le cerceau est vu de biais)
    center_m               centre 3D (x, y, z) en metres, repere CAMERA : x a droite, y en bas, z devant
    distance_m, normal     distance et normale (orientee dans le sens de la traversee), repere camera
    yaw_to_normal_deg      lacet pour aligner la camera sur la normale, repere camera (> 0 : tourner a droite)
    ambiguous              l'ambiguite double n'a pas pu etre levee

    Memes grandeurs dans le REPERE DRONE (convention des commandes rc du Tello, voir frames.py) :
    center_drone = (avant, droite, haut) en metres, normal_drone, yaw_drone_deg (> 0 : tourner a DROITE)
"""

import os
from dataclasses import dataclass, field

import cv2
import numpy as np

from tellovision import data, seg
from tellovision.frames import CameraToDrone
from tellovision.main import load_checkpoint, predict
from tellovision.pose import PoseEstimator


@dataclass
class Detection:
    present: bool
    p: float
    ellipse: tuple = None
    center_px: tuple = None
    center_m: np.ndarray = None
    distance_m: float = None
    couverture: float = None                # part du contour de l'ellipse sur le masque "tube" (seg.contour_coverage)
    normal: np.ndarray = None
    yaw_to_normal_deg: float = None
    view_angle_deg: float = None
    ambiguous: bool = True
    candidates: list = field(default_factory=list)
    center_drone: np.ndarray = None        # repere drone : (avant, droite, haut) en convention "tello"
    normal_drone: np.ndarray = None
    yaw_drone_deg: float = None             # convention "tello" : > 0 = tourner a droite
    img_scale: float = 1.0                  # taille d'origine / taille de l'image traitee (2 si 480x360 <- 960x720)


class HoopDetector:
    def __init__(self, run="logs/E3_segmentation480_couleur_0", camera_yaml="configs/camera.yaml",
                 hoop_yaml="configs/hoop.yaml", drone_yaml="configs/drone.yaml", track=True):
        self.model, self.cfg, _ = load_checkpoint(run)
        self.pose = PoseEstimator(camera_yaml, hoop_yaml)
        self.to_drone = CameraToDrone.from_yaml(drone_yaml)
        self.track = track                      # suivi d'une image a l'autre pour lever l'ambiguite
        self.last_prob = None                   # derniere carte de probabilite "tube" (segmentation)

    def reset(self):
        self.pose.previous = None

    def project(self, X):
        """Point 3D (repere camera) -> pixel de l'image brute (avec la distorsion de l'objectif)."""
        px, _ = cv2.projectPoints(np.asarray(X, float).reshape(1, 3), np.zeros(3), np.zeros(3),
                                  self.pose.K, self.pose.dist)
        return tuple(px.reshape(2))

    def __call__(self, img, orig_size=None):
        """
        img : image BGR. orig_size = (w, h) de l'image d'origine si img est une REDUCTION (ex. 480x360 recue par
        MQTT, issue d'une image 960x720) : l'ellipse est alors remise a l'echelle de la calibration (960x720)
        avant le calcul 3D. Toutes les coordonnees en pixels de la Detection sont dans l'image d'origine.
        """
        p, e, self.last_prob = predict(self.model, self.cfg, img, return_prob=True)   # last_prob : masque brut
        s = 1.0 if orig_size is None else orig_size[0] / img.shape[1]
        cov = seg.contour_coverage(self.last_prob, e, img.shape[1], img.shape[0]) \
            if (e is not None and self.last_prob is not None) else None
        if e is None:
            if self.track:
                self.reset()                    # cerceau perdu : on oublie la pose precedente
            return Detection(present=False, p=p, img_scale=s)
        if s != 1.0:                            # centres de pixels : x_origine = (x + 0.5) * s - 0.5
            e = data.affine_ellipse(e, s * np.eye(2), np.array([0.5 * s - 0.5, 0.5 * s - 0.5]))
        pose, ambiguous, cands = self.pose(e, track=self.track)
        if pose is None:
            return Detection(present=True, p=p, ellipse=e, center_px=(e[0], e[1]), couverture=cov, img_scale=s)
        n_d = self.to_drone.vector(pose.normal)
        return Detection(present=True, p=p, ellipse=e, center_px=self.project(pose.center), couverture=cov,
                         center_m=pose.center, distance_m=pose.distance, normal=pose.normal,
                         yaw_to_normal_deg=pose.yaw_to_normal_deg, view_angle_deg=pose.view_angle_deg,
                         ambiguous=ambiguous, candidates=cands,
                         center_drone=self.to_drone.point(pose.center), normal_drone=n_d,
                         yaw_drone_deg=self.to_drone.yaw_deg(n_d), img_scale=s)


def _panel(v, lines, color=(255, 255, 255)):
    """Cadre semi-transparent en haut a gauche avec les lignes de texte."""
    font = cv2.FONT_HERSHEY_SIMPLEX
    k = min(1.0, v.shape[1] / 960.0)                 # texte reduit sur les petites images (480x360)
    th = 2 if k > 0.7 else 1
    scale = 0.75 * k
    w0 = max(cv2.getTextSize(t, font, scale, th)[0][0] for t in lines)
    if w0 + 24 * k > 0.95 * v.shape[1]:              # encore trop large : on reduit jusqu'a tenir
        scale *= 0.95 * v.shape[1] / (w0 + 24 * k)
        k = scale / 0.75
    w = max(cv2.getTextSize(t, font, scale, th)[0][0] for t in lines) + int(24 * k)
    step = max(12, int(32 * k))
    h = step * len(lines) + int(14 * k)
    overlay = v.copy()
    cv2.rectangle(overlay, (4, 4), (4 + w, 4 + h), (0, 0, 0), -1)
    cv2.addWeighted(overlay, 0.55, v, 0.45, 0, dst=v)
    for i, t in enumerate(lines):
        cv2.putText(v, t, (int(4 + 12 * k), int(4 + step * (i + 1))), font, scale, color, th, cv2.LINE_AA)


def draw_detection(img, d, color=(255, 0, 255), title=None):
    """Dessine l'ellipse (magenta), le centre du cerceau (croix jaune) et un cadre avec sa position (repere drone)."""
    v = img.copy()
    head = [title] if title else []
    if not d.present:
        _panel(v, head + [f"pas de cerceau  (p = {d.p:.2f})"], (80, 80, 255))
        return v
    k = d.img_scale                                  # l'image affichee peut etre une reduction (480x360)
    cx, cy, A, B, th = data.affine_ellipse(d.ellipse, np.eye(2) / k, np.array([0.5 / k - 0.5, 0.5 / k - 0.5]))
    cv2.ellipse(v, (int(cx), int(cy)), (int(A), int(B)), th, 0, 360, color, 3, cv2.LINE_AA)
    if d.center_m is None:
        _panel(v, head + [f"cerceau detecte (p = {d.p:.2f})", "pose 3D impossible"], (80, 200, 255))
        return v
    u, w = int(round(d.center_px[0])), int(round(d.center_px[1]))         # pixels d'origine (affiches)
    cv2.drawMarker(v, (int((u + 0.5) / k - 0.5), int((w + 0.5) / k - 0.5)), (0, 255, 255),
                   cv2.MARKER_CROSS, 30, 3, cv2.LINE_AA)
    a, b, c = d.center_drone
    _panel(v, head + [
        f"p = {d.p:.2f}      centre 2D : u = {u} px  v = {w} px",
        f"centre : avant {a:.2f} m   droite {b:+.2f} m   haut {c:+.2f} m",
    ])
    return v


def show(views):
    """Visionneuse : espace / fleche droite = suivante, fleche gauche = precedente, q ou ESC = quitter."""
    os.environ.setdefault("QT_QPA_FONTDIR", "/usr/share/fonts/truetype/dejavu")
    win = "Cerceau : localisation"
    cv2.namedWindow(win, cv2.WINDOW_AUTOSIZE | cv2.WINDOW_GUI_NORMAL)
    i = 0
    while True:
        v = views[i].copy()
        cv2.putText(v, f"{i + 1}/{len(views)}   espace/fleches : naviguer   q : quitter", (12, v.shape[0] - 16),
                    cv2.FONT_HERSHEY_SIMPLEX, 0.6, (0, 255, 255), 2, cv2.LINE_AA)
        cv2.imshow(win, v)
        k = cv2.waitKeyEx(0)
        if k in (ord("q"), 27) or k == -1:
            break
        if k in (81, 2424832, 65361, 0x01000012):          # fleche gauche (codes selon le systeme)
            i = max(i - 1, 0)
        else:                                               # espace, fleche droite ou autre touche
            i = min(i + 1, len(views) - 1)
    cv2.destroyAllWindows()


def main():
    """python -m tellovision.detector image1.jpg [image2.jpg ...] : coordonnees + images annotees dans logs/detections/."""
    import argparse
    import glob
    import os
    ap = argparse.ArgumentParser(description="Localise le cerceau sur des images et affiche ses coordonnees.")
    ap.add_argument("images", nargs="+", help="fichiers ou motifs (ex. 'captures/hoop/*.jpg')")
    ap.add_argument("--run", default="logs/E3_segmentation480_couleur_0")
    ap.add_argument("--out", default="logs/detections")
    ap.add_argument("--show", action="store_true",
                    help="afficher chaque image annotee (espace / fleche droite = suivante, fleche gauche = "
                         "precedente, q ou ESC = quitter)")
    args = ap.parse_args()
    paths = sorted(p for pat in args.images for p in (glob.glob(pat) or [pat]))
    det = HoopDetector(args.run, track=False)              # images independantes : pas de suivi
    os.makedirs(args.out, exist_ok=True)
    views = []
    print("Repere drone (convention Tello) : avant, droite, haut en metres ; lacet > 0 = tourner a droite ; "
          "u, v = pixel du centre")
    print(f"{'image':40s} {'p':>5s} {'u px':>6s} {'v px':>6s} | {'avant':>6s} {'droite':>6s} {'haut':>6s} {'dist m':>6s} | {'lacet':>6s}")
    for p in paths:
        img = cv2.imread(p)
        if img is None:
            print(f"{p:40s} illisible")
            continue
        d = det(img)
        name = os.path.basename(p)
        if d.center_m is None:
            print(f"{name:40s} {d.p:5.2f}   pas de cerceau localise")
        else:
            x, y, z = d.center_drone
            print(f"{name:40s} {d.p:5.2f} {d.center_px[0]:6.0f} {d.center_px[1]:6.0f} | {x:6.2f} {y:+6.2f} {z:+6.2f} "
                  f"{d.distance_m:6.2f} | {d.yaw_drone_deg:+5.0f}°" + (" (ambigu)" if d.ambiguous else ""))
        view = draw_detection(img, d, title=name)
        cv2.imwrite(os.path.join(args.out, name), view)
        views.append(view)
    print(f"Images annotees : {args.out}/")
    if args.show and views:
        show(views)



if __name__ == "__main__":
    main()
