

import math

import cv2
import numpy as np
import yaml

DEFAULTS = {
    "min_p": 0.6,               # probabilite minimale d'une detection
    # ellipses pas credibles (main, manche, perche prises pour un morceau d'anneau) : detection ignoree
    "filtre_ba_min": 0.35,      # ellipse plus plate que B/A = 0,35...
    "filtre_ba_dist_m": 2.5,    # ... ET cerceau estime a plus de 2,5 m (de loin, il n'est pas vu si de biais)
    "filtre_couverture_min": 0.35,  # moins de 35 % du contour de l'ellipse sur le masque "tube" (fragment)
    "grace_s": 0.5,             # cerceau plus vu depuis moins de 0,5 s : present reste vrai (dernieres valeurs)
    "pose_memo_s": 1.0,         # pose 3D impossible : position estimee avec la distance de moins de 1 s
    # confirmation sur plusieurs images (contre les faux positifs)
    "confirm_n": 5,             # cerceau retenu apres 5 detections consecutives coherentes (~0,35 s a 15 i/s)...
    "confirm_cap_deg": 10.0,    # ... cap absolu qui varie de moins de 10 deg d'une image a l'autre...
    "confirm_dist_rel": 0.30,   # ... et distance de moins de 30 %
    "r_yaw_fige": True,         # MISE_EN_AXE : cap vers le centre du cerceau jusqu'a l'alignement, puis FIGE ;
                                # le correcteur X du PC de controle corrige la derive laterale avec delta_x.
                                # False : le cap suit le centre du cerceau a chaque image (il masque alors la derive)
    "r_yaw_fige_deg": 3.0,      # aligne (cap a moins de 3 deg du centre du cerceau) : le cap est fige
    "r_yaw_mode": "centre",     # "centre" : cap vers le centre du cerceau ; "axe" : cap de l'axe du cerceau
                                # (pose 3D non ambigue seulement, sinon "centre")
    # cerceau perdu
    "retrouver_s": 2.0,         # perdu de loin (PERDU) : on garde le dernier r_yaw 2 s avant de relancer la recherche
    "traversee_dist_m": 1.5,    # perdu a moins de 1,5 m : le drone est en train de passer le cerceau (TRAVERSEE)...
    "traversee_vitesse_ms": 0.4,  # ... duree de la traversee = (derniere distance + marge) / vitesse d'avance
    "traversee_marge_m": 0.5,   # ... (le drone doit depasser le cerceau de 0,5 m)...
    "traversee_s": 6.0,         # ... au plus 6 s ; puis NOUVELLE recherche (cerceau suivant)
    # RECHERCHE
    "observe_s": 2.0,           # au debut : regarder 2 s sur place avant de tourner
    "search_step_deg": 30.0,    # palier de rotation (champ horizontal de la camera : 55 deg)
    "search_pause_s": 1.5,      # pause sur chaque palier une fois atteint (image nette, retard de la vision)
    "search_reach_deg": 5.0,    # palier atteint a 5 deg pres (cap de l'en-tete)...
    "search_step_timeout_s": 4.0,  # ... ou au bout de 4 s
    "search_z_start_cm": 120.0, # premier tour a 1,20 m au moins (camera inclinee : trop bas, le cerceau sort par le haut)
    "search_total_deg": 360.0,  # un tour complet sans cerceau...
    "search_climb_cm": 50.0,    # ... on monte de 50 cm et on refait un tour...
    "search_levels": 3,         # ... au plus 3 tours (hauteur de depart, +50, +100)...
    "search_z_max_cm": 200.0,   # ... jamais au-dessus de 2 m (dernier tour plafonne a 2 m)...
    "search_z_min_cm": 60.0,    # ... ni au-dessous de 60 cm (consigne r_z)
    "search_climb_reach_cm": 10.0,   # montee atteinte a 10 cm pres...
    "search_climb_timeout_s": 6.0,   # ... ou au bout de 6 s
}


def wrap180(a):
    return (a + 180.0) % 360.0 - 180.0


class OrdreVision:
    def __init__(self, K, dist, to_drone, params=None):
        """K, dist : calibration de la camera (image 960x720) ; to_drone : CameraToDrone (inclinaison de la camera)."""
        self.p = dict(DEFAULTS)
        self.p.update(params or {})
        self.K, self.dist, self.to_drone = np.asarray(K, float), np.asarray(dist, float), to_drone
        self.etat = "RECHERCHE"
        self.last = None            # dernier ordre calcule sur une image ou le cerceau etait vu
        self.t_seen = None          # derniere image ou le cerceau etait vu
        self.t_lost = None          # instant ou le cerceau a ete perdu
        self.fx = float(self.K[0, 0])                           # focale (pixels, image 960x720)
        self.cap_fige = None        # cap fige pendant la mise en axe (r_yaw_fige)
        self.serie = []             # detections consecutives coherentes pas encore confirmees : (cap, distance)
        self.ref = None             # derniere detection retenue : (cap absolu, distance, instant)
        self.avant = self.t_avant = None   # derniere distance vers l'avant mesuree par la pose (m), et quand
        # recherche
        self.t_start = None         # debut de la recherche en cours
        self.r_yaw = None           # consigne de cap de la recherche (deg)
        self.r_z = None             # consigne de hauteur de la recherche (cm)
        self.turned = 0.0           # rotation demandee depuis le debut du tour (deg)
        self.level = 0              # numero du tour (0 = hauteur de depart)
        self.t_step = None          # debut du palier en cours
        self.t_reached = None       # instant ou le palier (ou la montee) a ete atteint
        self.climbing = False

    @classmethod
    def from_detector(cls, detector, path="configs/ordres.yaml"):
        try:
            with open(path) as f:
                params = yaml.safe_load(f) or {}
        except FileNotFoundError:
            params = {}
        return cls(detector.pose.K, detector.pose.dist, detector.to_drone, params)

    def direction(self, u, v):
        """Pixel (u, v) de l'image 960x720 -> direction (avant, droite, haut) dans le repere drone."""
        xn, yn = cv2.undistortPoints(np.array([[[u, v]]], float), self.K, self.dist).reshape(2)
        return self.to_drone.vector([xn, yn, 1.0])

    # ------------------------------------------------------------------ #
    def _search_reset(self, t, yaw, z_cm, keep_level=False):
        self.etat, self.t_start = "RECHERCHE", t
        self.cap_fige = None                                    # nouveau cerceau : le cap sera refige
        self.r_yaw, self.turned, self.t_step, self.t_reached, self.climbing = yaw, 0.0, t, None, False
        if not keep_level or self.r_z is None:
            self.level = 0
            if z_cm is None:
                self.r_z = None
            else:                                                # premier tour a search_z_start_cm au moins
                self.r_z = max(self.p["search_z_min_cm"], min(self.p["search_z_max_cm"],
                                                              max(z_cm, self.p["search_z_start_cm"])))
                self.climbing = z_cm < self.r_z - self.p["search_climb_reach_cm"]

    def _search(self, t, yaw, z_cm):
        """Etat RECHERCHE : r_yaw par paliers, r_z monte de search_climb_cm apres chaque tour complet."""
        p = self.p
        if self.climbing:                                        # montee entre deux tours
            reached = z_cm is not None and abs(z_cm - self.r_z) <= p["search_climb_reach_cm"]
            if reached or t - self.t_step >= p["search_climb_timeout_s"]:
                self.climbing, self.turned, self.t_step, self.t_reached = False, 0.0, t, t
            return
        if self.level == 0 and self.turned == 0.0 and t - self.t_start < p["observe_s"]:
            return                                               # on regarde d'abord sans tourner
        if self.t_reached is None:                               # palier en cours : atteint ?
            if abs(wrap180(yaw - self.r_yaw)) <= p["search_reach_deg"] or t - self.t_step >= p["search_step_timeout_s"]:
                self.t_reached = t
            return
        if t - self.t_reached < p["search_pause_s"]:             # pause sur le palier
            return
        if self.turned >= p["search_total_deg"]:                 # tour complet sans cerceau
            if self.level + 1 >= p["search_levels"] or self.r_z is None or self.r_z >= p["search_z_max_cm"]:
                self.etat = "ECHEC"
                return
            self.level += 1
            self.r_z = min(self.r_z + p["search_climb_cm"], p["search_z_max_cm"])
            self.climbing, self.t_step = True, t
            return
        self.r_yaw = wrap180(self.r_yaw + p["search_step_deg"])  # palier suivant
        self.turned += p["search_step_deg"]
        self.t_step, self.t_reached = t, None

    # ------------------------------------------------------------------ #
    def _r_yaw_mise_en_axe(self, o, yaw_deg=None):
        """
        Cap envoye pendant la mise en axe : vers le centre du cerceau tant que le drone n'est pas aligne, puis FIGE
        (r_yaw_fige) : plus de correction de lacet, la derive laterale est corrigee par X (delta_x) cote PC de controle.
        """
        if not self.p["r_yaw_fige"]:
            return o["r_yaw"]
        if self.cap_fige is None:
            if yaw_deg is not None and abs(wrap180(o["r_yaw"] - yaw_deg)) <= self.p["r_yaw_fige_deg"]:
                self.cap_fige = o["r_yaw"]                      # aligne : on fige
            else:
                return o["r_yaw"]                               # alignement initial
        return self.cap_fige

    def _mesure(self, d, t, yaw_deg):
        """Detection -> mesure du cerceau (repere drone, cap absolu, distance), ou None si rien d'exploitable."""
        p = self.p
        if not (d.present and d.center_px is not None and d.p >= p["min_p"]):
            return None
        if self.rejet(d) is not None:
            return None
        ua, ub, uc = self.direction(*d.center_px)
        pose = d.center_drone is not None
        if pose:                                                # position 3D par la pose
            a, b, c = (float(v) for v in d.center_drone)
        else:                                                   # direction seule : distance de la derniere pose
            ok = self.avant is not None and t - self.t_avant <= p["pose_memo_s"]
            a, b, c = (self.avant, self.avant * ub / ua, self.avant * uc / ua) if ok else (None, ub, uc)
        cap = math.degrees(math.atan2(b, a if a is not None else ua))
        if p["r_yaw_mode"] == "axe" and d.yaw_drone_deg is not None and not d.ambiguous:
            cap = float(d.yaw_drone_deg)
        return {"t": t, "p": float(d.p), "pose": pose, "a": a, "b": b, "c": c,
                "dx_px": self.fx * ub / ua,                     # decalage horizontal en pixels (camera horizontale)
                "cap_abs": wrap180(yaw_deg + cap),
                "dist": math.sqrt(a * a + b * b + c * c) if (pose and a is not None) else None}

    def rejet(self, d):
        """Raison du rejet d'une ellipse pas credible ("plate" ou "fragment"), ou None si elle est acceptee."""
        p = self.p
        cov, e, dist = (getattr(d, k, None) for k in ("couverture", "ellipse", "distance_m"))
        if cov is not None and cov < p["filtre_couverture_min"]:
            return "fragment"
        if e is not None and e[2] > 0 and e[3] / e[2] < p["filtre_ba_min"] \
                and dist is not None and dist > p["filtre_ba_dist_m"]:
            return "plate"
        return None

    def _coherent(self, m1, m2):
        """Deux mesures (cap absolu deg, distance m ou None) du meme cerceau ?"""
        p = self.p
        if abs(wrap180(m1[0] - m2[0])) > p["confirm_cap_deg"]:
            return False
        if m1[1] is not None and m2[1] is not None:
            return abs(m1[1] - m2[1]) <= p["confirm_dist_rel"] * min(m1[1], m2[1])
        return True

    def _confirme(self, t, cap_abs, dist):
        """
        Confirmation sur plusieurs images (contre les faux positifs) : une detection n'est retenue qu'apres
        confirm_n detections consecutives coherentes entre elles (cap et distance proches d'une image a l'autre).
        Une fois retenue, une detection incoherente avec la derniere retenue est ignoree ; une nouvelle serie
        coherente de confirm_n images la remplace (cerceau qui a vraiment bouge dans l'image).
        """
        m = (cap_abs, dist)
        if self.ref is not None and t - self.ref[2] <= self.p["grace_s"] and self._coherent(self.ref[:2], m):
            self.ref = (cap_abs, dist, t)                       # suit le cerceau deja retenu
            self.serie = [m]
            return True
        if self.serie and self._coherent(self.serie[-1], m):
            self.serie.append(m)
        else:
            self.serie = [m]
        if len(self.serie) >= self.p["confirm_n"]:
            self.ref = (cap_abs, dist, t)
            return True
        return False

    def step(self, d, t, yaw_deg, z_cm=None):
        """
        d : Detection (detector.py) ; t : instant de l'image (s) ; yaw_deg : cap du drone a cet instant (deg) ;
        z_cm : hauteur du drone (cm, meme repere que tello/status), pour la recherche (montee par paliers).
        """
        p = self.p
        if self.t_start is None:
            self._search_reset(t, yaw_deg, z_cm)
        m = self._mesure(d, t, yaw_deg)
        present = self.t_seen is not None and t - self.t_seen <= p["grace_s"]
        vu = m is not None and self._confirme(t, m["cap_abs"], m["dist"])
        if vu:                                                  # detection retenue
            a, b, c = m["a"], m["b"], m["c"]
            if m["pose"]:
                self.avant, self.t_avant = a, m["t"]
            self.t_seen = t
            r3 = lambda v: round(float(v), 3)
            self.last = {"delta_x": int(round(m["dx_px"])), "delta_z": r3(c) if a is not None else None,
                         "avant_m": r3(a) if a is not None else None,
                         "distance_m": r3(math.sqrt(a * a + b * b + c * c)) if a is not None else None,
                         "r_yaw": int(round(m["cap_abs"]))}
        present = self.t_seen is not None and t - self.t_seen <= p["grace_s"]

        if present:                                             # ---- MISE_EN_AXE ----
            self.t_lost, self.etat = None, "MISE_EN_AXE"
            o = self.last
            return self._ordre(present=True, vu=vu, age_s=round(t - self.t_seen, 2), p_det=d.p,
                               delta_x=o["delta_x"], delta_z=o["delta_z"], r_yaw=self._r_yaw_mise_en_axe(o, yaw_deg), r_z=None,
                               distance_m=o["distance_m"], avant_m=o["avant_m"])

        # ---- cerceau pas vu ----
        if self.etat == "MISE_EN_AXE":                          # on vient de le perdre
            near = self.last is not None and self.last["distance_m"] is not None \
                and self.last["distance_m"] < p["traversee_dist_m"]
            self.etat = "TRAVERSEE" if near else "PERDU"
            self.t_lost = t
        if self.etat in ("TRAVERSEE", "PERDU"):                 # cap tenu sur la derniere consigne
            if self.etat == "TRAVERSEE":                        # le temps de passer le cerceau
                hold = min(p["traversee_s"], (self.last["distance_m"] + p["traversee_marge_m"]) / p["traversee_vitesse_ms"])
            else:
                hold = p["retrouver_s"]
            if t - self.t_lost < hold:
                return self._ordre(present=False, vu=False, p_det=d.p, r_yaw=self._r_yaw_mise_en_axe(self.last),
                                   r_z=None)
            if self.etat == "TRAVERSEE":                        # cerceau passe : nouvelle recherche depuis la hauteur actuelle
                self.ref, self.serie, self.last = None, [], None
                self._search_reset(t, yaw_deg, z_cm)
            else:                                               # perdu de loin : on reprend la recherche en cours
                self._search_reset(t, self._r_yaw_mise_en_axe(self.last), z_cm, keep_level=True)
        if self.etat == "RECHERCHE":
            self._search(t, yaw_deg, z_cm)
        return self._ordre(present=False, vu=False, p_det=d.p, r_yaw=int(round(self.r_yaw)),
                           r_z=None if self.r_z is None else int(round(self.r_z)))

    def _ordre(self, present, vu, p_det, r_yaw, r_z, age_s=None, delta_x=None, delta_z=None, distance_m=None,
               avant_m=None):
        return {"etat": self.etat, "present": present, "vu": vu, "age_s": age_s, "p": round(float(p_det), 3),
                "delta_x": delta_x, "delta_z": delta_z, "avant_m": avant_m, "distance_m": distance_m,
                "r_yaw": r_yaw, "r_z": r_z}

