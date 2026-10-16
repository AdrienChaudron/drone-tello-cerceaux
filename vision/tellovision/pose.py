"""
pose.py : de l'ellipse vue dans l'image au cercle 3D (position et vecteur normal du cerceau).

Principe (geometrie projective, aucun apprentissage) :
    Les rayons qui partent de la camera et touchent le cerceau forment un CONE. Son equation se lit
    directement sur l'ellipse : si C est la conique de l'ellipse (pixels) et K la matrice de la camera,
    le cone est  X^T Q X = 0  avec  Q = K^T C K  (X en metres, repere camera).
    Un plan ne coupe ce cone selon un CERCLE que pour deux orientations : d'ou DEUX solutions
    (l'ambiguite double). Connaissant le rayon reel r du cerceau, chaque orientation donne
    une seule position. Ref. : Chen, Wu, Wada, "Camera calibration with two arbitrary coplanar
    circles", ECCV 2004 (formules du cercle a partir d'une conique).

Repere camera (convention OpenCV) : x vers la droite, y vers le BAS, z vers l'avant (axe optique).
La normale renvoyee est orientee vers l'avant (n_z > 0) : c'est la direction dans laquelle traverser.
"""

import math
import os
from dataclasses import dataclass

import cv2
import numpy as np
import yaml

from tellovision import data


@dataclass
class CirclePose:
    center: np.ndarray        # centre du cerceau (m), repere camera
    normal: np.ndarray        # normale unitaire, orientee vers l'avant (n_z > 0)

    @property
    def distance(self):
        """Distance camera -> centre du cerceau (m)."""
        return float(np.linalg.norm(self.center))

    @property
    def view_angle_deg(self):
        """Angle entre l'axe optique et la normale (0 = camera parallele a la normale)."""
        return math.degrees(math.acos(min(1.0, self.normal[2])))

    @property
    def yaw_to_normal_deg(self):
        """Lacet a appliquer au drone pour aligner l'axe optique sur la normale (> 0 : tourner a droite)."""
        return math.degrees(math.atan2(self.normal[0], self.normal[2]))

    @property
    def offset_from_axis(self):
        """Position de la camera par rapport a l'axe du cerceau, dans le plan du cerceau (m)."""
        p = -self.center                                   # camera vue depuis le centre du cerceau
        return p - (p @ self.normal) * self.normal


def load_camera(path="configs/camera.yaml"):
    with open(path) as f:
        cam = yaml.safe_load(f)
    return np.array(cam["camera_matrix"], float), np.array(cam["dist_coeffs"], float)


def undistort_ellipse(e, K, dist, n=72):
    """Corrige la distorsion de l'objectif : on corrige des points du contour puis on reajuste l'ellipse."""
    pts = data.ellipse_points(e, n).astype(np.float32).reshape(-1, 1, 2)
    und = cv2.undistortPoints(pts, K, dist, P=K).reshape(-1, 2)
    (cx, cy), (w, h), th = cv2.fitEllipse(und.astype(np.float32))
    A, B = w / 2, h / 2
    if B > A:
        A, B, th = B, A, th + 90
    return cx, cy, A, B, th % 180


def circle_poses(e, K, radius, dist=None):
    """
    Ellipse (pixels, convention de data.py) -> les deux poses 3D possibles du cerceau.
    radius : rayon reel (m). Renvoie une liste de CirclePose (0 ou 2 elements).
    """
    if dist is not None and np.any(np.abs(dist) > 0):
        e = undistort_ellipse(e, K, dist)
    Q = K.T @ data.ellipse_to_conic(e) @ K
    Q = (Q + Q.T) / 2
    vals, vecs = np.linalg.eigh(Q)
    if np.sum(vals > 0) == 1:                          # on veut deux valeurs propres positives
        vals, Q = -vals, -Q
    pos = np.where(vals > 0)[0]
    neg = np.where(vals < 0)[0]
    if len(pos) != 2 or len(neg) != 1:
        return []
    i1, i2 = pos[np.argsort(-vals[pos])]               # l1 >= l2 > 0 > l3
    i3 = neg[0]
    l1, l2, l3 = vals[i1], vals[i2], vals[i3]
    V = np.stack([vecs[:, i1], vecs[:, i2], vecs[:, i3]], axis=1)
    if np.linalg.det(V) < 0:
        V[:, 2] = -V[:, 2]
    a = math.sqrt((l1 - l2) / (l1 - l3))
    b = math.sqrt((l2 - l3) / (l1 - l3))
    k = radius / math.sqrt(-l1 * l3)
    poses = []
    for s1 in (1, -1):
        n = V @ np.array([s1 * a, 0.0, -b])
        c = V @ np.array([s1 * a * l3, 0.0, -b * l1]) * k
        if c[2] < 0:                                    # le cerceau est devant la camera
            c, n = -c, -n
        if n[2] < 0:                                    # normale orientee vers l'avant
            n = -n
        poses.append(CirclePose(center=c, normal=n / np.linalg.norm(n)))
    return poses


def select_pose(poses, previous=None, max_tilt_deg=25.0):
    """
    Leve l'ambiguite double :
      1) si on connait la pose de l'image precedente : on garde la plus proche (continuite) ;
      2) sinon on utilise le fait que le cerceau est VERTICAL : sa normale est horizontale, donc n_y ~ 0
         (valable tant que le drone vole a plat ; inefficace si le drone est a la hauteur du centre).
    Renvoie (pose choisie, ambigu) ; ambigu = True si les deux candidates restent plausibles.
    """
    if not poses:
        return None, True
    if len(poses) == 1:
        return poses[0], False
    if previous is not None:
        d = [np.linalg.norm(p.normal - previous.normal) for p in poses]
        return poses[int(np.argmin(d))], abs(d[0] - d[1]) < 0.05
    tilt = [math.degrees(math.asin(min(1.0, abs(p.normal[1])))) for p in poses]
    best = int(np.argmin(tilt))
    other = 1 - best
    ambiguous = tilt[other] < max_tilt_deg or abs(tilt[0] - tilt[1]) < 5
    return poses[best], ambiguous


class PoseEstimator:
    """Ellipse predite par le CNN -> pose 3D, avec la calibration et le diametre du cerceau."""

    def __init__(self, camera_yaml="configs/camera.yaml", hoop_yaml="configs/hoop.yaml", hoop_diameter_m=None):
        if not os.path.exists(camera_yaml):
            raise FileNotFoundError(f"{camera_yaml} absent : lancer d'abord tools/calibrate_camera.py")
        self.K, self.dist = load_camera(camera_yaml)
        if hoop_diameter_m is None:
            with open(hoop_yaml) as f:
                hoop_diameter_m = yaml.safe_load(f)["diameter_m"]
        self.radius = hoop_diameter_m / 2
        self.previous = None

    def __call__(self, ellipse, track=True):
        poses = circle_poses(ellipse, self.K, self.radius, self.dist)
        pose, ambiguous = select_pose(poses, self.previous if track else None)
        if track and pose is not None:
            self.previous = pose
        return pose, ambiguous, poses
