"""
frames.py : changement de repere camera (OpenCV) -> repere du drone.

Convention retenue par defaut : celle des commandes rc du TELLO, pour qu'il n'y ait aucun changement de signe
entre la vision et la trame envoyee (send_rc_control(droite, avant, haut, lacet)).

    Repere camera (OpenCV)            Repere drone "tello" (par defaut)        Repere "ros" (option)
        x : vers la droite                avant  : devant          (rc 2e)          x : devant
        y : vers le BAS                   droite : a droite        (rc 1er)         y : a gauche
        z : devant (axe optique)          haut   : en haut         (rc 3e)          z : en haut
                                          lacet > 0 : tourner a DROITE (rc 4e)      lacet > 0 : a gauche

Les vecteurs sont ranges dans l'ordre (avant, droite, haut) pour "tello", (x, y, z) pour "ros".
Attention : le repere (avant, droite, haut) est INDIRECT (main gauche). Sans consequence pour comparer
consigne et mesure axe par axe ou pour un lacet dans le plan horizontal ; ne pas y faire de produit vectoriel 3D.

    p_drone = M @ R_tilt @ p_camera + camera_offset
    R_tilt        : inclinaison eventuelle de la camera vers le bas (camera_pitch_deg > 0 = regarde vers le bas)
    camera_offset : position de la camera par rapport au centre du drone, dans le repere drone (m)
"""

import math
import os

import numpy as np
import yaml

M_TELLO = np.array([[0.0, 0.0, 1.0],      # avant  = z camera
                    [1.0, 0.0, 0.0],      # droite = x camera
                    [0.0, -1.0, 0.0]])    # haut   = -y camera
M_ROS = np.array([[0.0, 0.0, 1.0],        # x devant = z camera
                  [-1.0, 0.0, 0.0],       # y gauche = -x camera
                  [0.0, -1.0, 0.0]])      # z haut   = -y camera
CONVENTIONS = {"tello": M_TELLO, "ros": M_ROS}


class CameraToDrone:
    def __init__(self, convention="tello", camera_offset_m=(0.0, 0.0, 0.0), camera_pitch_deg=0.0):
        self.convention = convention
        a = math.radians(camera_pitch_deg)
        # camera inclinee vers le bas d'un angle a : rotation autour de l'axe x de la camera
        R_tilt = np.array([[1.0, 0.0, 0.0],
                           [0.0, math.cos(a), math.sin(a)],
                           [0.0, -math.sin(a), math.cos(a)]])
        self.R = CONVENTIONS[convention] @ R_tilt
        self.t = np.asarray(camera_offset_m, float)

    @classmethod
    def from_yaml(cls, path="configs/drone.yaml"):
        if not os.path.exists(path):
            return cls()
        with open(path) as f:
            c = yaml.safe_load(f) or {}
        return cls(c.get("convention", "tello"), c.get("camera_offset_m", (0.0, 0.0, 0.0)),
                   c.get("camera_pitch_deg", 0.0))

    def point(self, p_cam):
        """Point (position) : rotation + translation."""
        return self.R @ np.asarray(p_cam, float) + self.t

    def vector(self, v_cam):
        """Direction (normale) : rotation seulement."""
        return self.R @ np.asarray(v_cam, float)

    def yaw_deg(self, v):
        """Lacet d'une direction exprimee dans le repere drone ("tello" : > 0 a droite ; "ros" : > 0 a gauche)."""
        return math.degrees(math.atan2(v[1], v[0]))


def rc_order(v_tello):
    """(avant, droite, haut) -> ordre des arguments de send_rc_control : (droite, avant, haut)."""
    return v_tello[1], v_tello[0], v_tello[2]
