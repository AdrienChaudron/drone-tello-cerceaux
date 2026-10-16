"""
direct.py : guidance VISEE DIRECTE : on vise le CENTRE du cerceau (l'orientation de son axe n'est pas utilisee).

    YAW : on tourne vers le centre du cerceau (relevement vu par la camera) ;
    Z   : hauteur du centre du cerceau = hauteur du drone + ecart vertical vu, filtree (mediane) et limitee en vitesse ;
    Y   : PUISSANCE rc d'avance (le PC de controle n'asservit pas Y), seulement si le cerceau est a peu pres centre
          en cap ET en hauteur ; sinon 0 (on tourne / on monte d'abord) ;
    X   : toujours 0.

A `commit_dist_m` du centre, centre en cap et en hauteur -> TRAVERSEE : puissance fixe ; tant que le cerceau est vu,
on continue de viser son centre en cap (le Tello derive lateralement de plusieurs cm/s) et on recalcule la duree ;
une fois le cerceau perdu (trop pres), cap et hauteur figes jusqu'a la fin de la duree, puis arret (FIN). Cerceau perdu : on s'arrete (Y = 0) puis, s'il ne revient pas,
on tourne par paliers pour le chercher.
"""

import math
from dataclasses import asdict, dataclass, field

import numpy as np
import yaml


@dataclass
class Telemetry:
    """Etat du drone au moment de l'image (en-tete envoye par le PC de controle)."""
    t: float                      # horodatage de la capture (s)
    yaw_deg: float = None         # cap absolu de l'IMU, > 0 a droite
    height_m: float = None        # hauteur (ToF)


@dataclass
class Command:
    frame_id: int
    t: float
    phase: str
    mode: str                     # "cible", "maintien", "atterrir"
    avant_m: float = 0.0          # inutilise (Y est une puissance : voir vitesse_avant_mps)
    droite_m: float = 0.0         # toujours 0
    haut_m: float = 0.0           # ecart vertical voulu (m) par rapport a la hauteur de l'image
    lacet_deg: float = 0.0        # rotation relative, > 0 = droite
    confiance: float = 0.0
    ambigu: bool = False
    info: dict = field(default_factory=dict)
    vitesse_avant_mps: float = None   # Y = PUISSANCE d'avance (rc) = rc_par_mps x vitesse

    def to_dict(self):
        return asdict(self)

DEFAULTS = {
    "confirm_frames": 3,          # detections consecutives avant de suivre un cerceau
    "min_p": 0.6,                 # probabilite minimale d'une detection
    # cap
    "yaw_gain": 1.0,              # rotation demandee = gain x relevement du centre
    # hauteur
    "z_depart_m": 1.2,            # hauteur tenue tant que celle du cerceau est inconnue (camera inclinee vers le bas :
                                  # trop bas, le cerceau sort par le haut de l'image)
    "height_max_dist_m": 4.0,     # hauteur du cerceau mesuree seulement a moins de 4 m
    "height_window_s": 1.5,       # mediane des mesures de hauteur sur 1,5 s
    "height_reject_m": 0.25,      # mesure a plus de 25 cm de la mediane : ignoree
    "z_min_m": 0.4,               # consigne de hauteur toujours entre 0,4...
    "z_max_m": 1.9,               # ... et 1,9 m (ToF)
    "z_rate_mps": 0.15,           # et variant d'au plus 0,15 m/s
    # avance (puissance rc)
    "y_rc_min": 10,               # puissance d'avance quand on est centre et proche du point de traversee
    "y_rc_max": 18,               # puissance d'avance maximale (loin)
    "y_rc_gain": 6.0,             # puissance = min + gain x (distance - commit_dist), bornee
    "go_bearing_deg": 10.0,       # on n'avance que si le centre est a moins de 10 deg en cap...
    "go_height_m": 0.25,          # ... et a moins de 25 cm en hauteur (sinon on tourne / monte sur place)
    # traversee
    "commit_dist_m": 1.3,         # traversee declenchee a 1,3 m du centre...
    "commit_bearing_deg": 5.0,    # ... si le centre est a moins de 5 deg en cap...
    "commit_height_m": 0.10,      # ... et 10 cm en hauteur
    "traverse_rc": 30,            # puissance pendant la traversee (~0,3 m/s : moins de temps pour deriver)
    "traverse_track_min_m": 0.5,  # traversee : on vise encore le centre en cap tant qu'il est vu a plus de 0,5 m
    "rc_par_mps": 100.0,          # puissance rc pour 1 m/s (essai du 09/10 10:13 : rc 15 -> ~0,15 m/s ; a identifier)
    "traverse_margin_m": 0.8,     # aller jusqu'a 0,8 m derriere le cerceau
    "traverse_time_factor": 1.3,  # duree = (distance + marge) / vitesse x 1,3
    # cerceau perdu, recherche
    "lost_grace_s": 0.5,          # cerceau plus vu depuis moins de 0,5 s (image ratee) : on garde la derniere commande
    "lost_search_s": 4.0,         # plus vu depuis 4 s : recherche
    "observe_s": 2.0,             # au demarrage : regarder 2 s sur place avant de chercher
    "search_step_deg": 25.0,
    "search_pause_s": 1.5,
    "search_total_deg": 380.0,
    "max_hoops": 1,
}


class DirectGuidance:
    def __init__(self, params=None):
        self.p = dict(DEFAULTS)
        self.p.update(params or {})
        self.phase = "RECHERCHE"
        self.seen_streak = 0
        self.t_seen = None            # derniere detection utilisable
        self.t_start = None
        self.yaw_hold = None          # cap absolu tenu (deg)
        self.H_samples = []           # (t, hauteur absolue du centre)
        self.H = None                 # hauteur du centre du cerceau (mediane)
        self.z_out = self.z_t = None  # derniere consigne de hauteur (bornee, vitesse limitee)
        self.t_search = None
        self.search_turned = 0.0
        self.traverse_until = None
        self.hoops_done = 0
        self.rc = 0.0                 # derniere puissance d'avance demandee en SUIVI

    @classmethod
    def from_yaml(cls, path="configs/direct.yaml"):
        try:
            with open(path) as f:
                return cls(yaml.safe_load(f) or {})
        except FileNotFoundError:
            return cls()

    # ------------------------------------------------------------------ #
    def _update_height(self, t, h):
        p = self.p
        self.H_samples = [(ti, hi) for ti, hi in self.H_samples if t - ti <= p["height_window_s"]]
        med = float(np.median([hi for _, hi in self.H_samples])) if self.H_samples else None
        if med is None or len(self.H_samples) < 4 or abs(h - med) <= p["height_reject_m"]:
            self.H_samples.append((t, h))
        self.H = float(np.median([hi for _, hi in self.H_samples]))

    def _z(self, target, t, tof_m):
        """Consigne de hauteur absolue SURE (m) : bornee et variant d'au plus z_rate m/s."""
        p = self.p
        if self.z_out is None:
            self.z_out = tof_m if tof_m is not None else target
        if target is None:
            target = self.z_out
        z = min(max(target, p["z_min_m"]), p["z_max_m"])
        if self.z_t is not None:
            dz = p["z_rate_mps"] * max(0.0, t - self.z_t)
            z = min(max(z, self.z_out - dz), self.z_out + dz)
        self.z_out, self.z_t = z, t
        return z

    def _cmd(self, fid, t, tof_m, yaw_deg, mode="cible", rc=0.0, lacet_deg=0.0, z=None, d=None, **info):
        """rc : puissance d'avance ; z : hauteur absolue voulue (m) ; lacet_deg : rotation relative au cap de l'image."""
        haut = (z - tof_m) if (z is not None and tof_m is not None) else 0.0
        v = float(rc) / self.p["rc_par_mps"]          # link.py la reconvertit en puissance (meme rc_par_mps)
        return Command(fid, t, self.phase, mode, 0.0, 0.0, float(haut), float(lacet_deg),
                       float(d.p) if d is not None else 0.0, False, info, vitesse_avant_mps=v)

    # ------------------------------------------------------------------ #
    def step(self, d, tel: Telemetry, frame_id=0):
        p, t = self.p, tel.t
        yaw, tof_m = (tel.yaw_deg or 0.0), tel.height_m
        if self.t_start is None:
            self.t_start = t
        if self.yaw_hold is None:
            self.yaw_hold = yaw

        def hold(mode="cible", **info):              # Y = 0, cap et hauteur tenus
            z = self._z(self.H if self.H is not None else p["z_depart_m"], t, tof_m)
            return self._cmd(frame_id, t, tof_m, yaw, mode, 0.0, self.yaw_hold - yaw, z, **info)

        if self.phase == "FIN":
            return hold("atterrir")

        # ---------------- TRAVERSEE : cap vers le centre tant qu'il est vu, puis fige ---------------- #
        if self.phase == "TRAVERSEE":
            if d is not None and d.present and d.p >= p["min_p"] and d.center_drone is not None:
                a, b, c = (float(x) for x in d.center_drone)
                dist = math.sqrt(a * a + b * b + c * c)
                if dist >= p["traverse_track_min_m"]:
                    self.yaw_hold = yaw + p["yaw_gain"] * math.degrees(math.atan2(b, a))
                    v = p["traverse_rc"] / p["rc_par_mps"]
                    self.traverse_until = t + (dist + p["traverse_margin_m"]) / v * p["traverse_time_factor"]
            if t < self.traverse_until:
                z = self._z(self.H, t, tof_m)
                return self._cmd(frame_id, t, tof_m, yaw, "cible", p["traverse_rc"], self.yaw_hold - yaw, z,
                                 reste_s=round(self.traverse_until - t, 1))
            self.hoops_done += 1
            self.phase = "FIN" if self.hoops_done >= p["max_hoops"] else "RECHERCHE"
            self.H, self.H_samples, self.t_seen, self.seen_streak = None, [], None, 0
            self.t_search, self.search_turned = None, 0.0
            return hold("atterrir" if self.phase == "FIN" else "maintien")

        usable = (d is not None and d.present and d.p >= p["min_p"] and d.center_drone is not None)
        self.seen_streak = self.seen_streak + 1 if usable else 0

        # ---------------- SUIVI : on vise le centre ---------------- #
        if usable and (self.seen_streak >= p["confirm_frames"] or self.phase == "SUIVI"):
            self.phase, self.t_seen = "SUIVI", t
            self.t_search, self.search_turned = None, 0.0
            a, b, c = (float(v) for v in d.center_drone)
            dist = math.sqrt(a * a + b * b + c * c)
            bearing = math.degrees(math.atan2(b, a))                 # > 0 : centre a droite
            if tof_m is not None and dist <= p["height_max_dist_m"]:
                self._update_height(t, tof_m + c)
            self.yaw_hold = yaw + p["yaw_gain"] * bearing
            z = self._z(self.H if self.H is not None else p["z_depart_m"], t, tof_m)
            dz = (self.H - tof_m) if (self.H is not None and tof_m is not None) else c
            info = dict(dist_m=round(dist, 2), releve_deg=round(bearing, 1), ecart_haut_m=round(dz, 2),
                        hauteur_cerceau_m=round(self.H, 2) if self.H is not None else None)
            if dist <= p["commit_dist_m"] and abs(bearing) < p["commit_bearing_deg"] and abs(dz) < p["commit_height_m"]:
                self.phase = "TRAVERSEE"
                v = p["traverse_rc"] / p["rc_par_mps"]
                self.traverse_until = t + (dist + p["traverse_margin_m"]) / v * p["traverse_time_factor"]
                return self._cmd(frame_id, t, tof_m, yaw, "cible", p["traverse_rc"], self.yaw_hold - yaw, z, d,
                                 traversee_s=round(self.traverse_until - t, 1), **info)
            rc = 0.0
            if abs(bearing) < p["go_bearing_deg"] and abs(dz) < p["go_height_m"] and dist > p["commit_dist_m"]:
                rc = min(p["y_rc_max"], p["y_rc_min"] + p["y_rc_gain"] * (dist - p["commit_dist_m"]))
            self.rc = rc
            return self._cmd(frame_id, t, tof_m, yaw, "cible", rc, self.yaw_hold - yaw, z, d, **info)

        # ---------------- cerceau pas vu ---------------- #
        lost = (t - self.t_seen) if self.t_seen is not None else None
        if lost is not None and lost < p["lost_grace_s"]:            # image ratee : on continue comme avant
            z = self._z(self.H if self.H is not None else p["z_depart_m"], t, tof_m)
            return self._cmd(frame_id, t, tof_m, yaw, "cible", self.rc, self.yaw_hold - yaw, z, perdu_s=round(lost, 2))
        if lost is not None and lost < p["lost_search_s"]:
            self.phase = "PERDU"                                       # arret sur place, cap et hauteur tenus
            return hold(perdu_s=round(lost, 2))
        self.phase = "RECHERCHE"
        if self.hoops_done == 0 and self.t_seen is None and t - self.t_start < p["observe_s"]:
            return hold("maintien", observation=True)
        if self.search_turned >= p["search_total_deg"]:
            self.phase = "FIN"
            return hold("atterrir", raison="aucun cerceau trouve")
        if self.t_search is None or t - self.t_search >= p["search_pause_s"]:
            self.t_search = t
            self.search_turned += p["search_step_deg"]
            self.yaw_hold = yaw + p["search_step_deg"]
        return hold(palier=True)
