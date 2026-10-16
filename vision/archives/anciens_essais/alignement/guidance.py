"""
guidance.py : algorithme de passage des cerceaux (machine a etats), independant du transport (MQTT a venir).

A chaque image : detection du CNN (+ etat du drone si disponible)  ->  step()  ->  Consigne

Consigne = CIBLE DE POSITION RELATIVE, exprimee dans le repere du drone AU MOMENT DE L'IMAGE
(convention Tello : avant, droite, haut en metres ; lacet en degres, > 0 = tourner a droite).
Chaque consigne REMPLACE la precedente (elle ne s'y ajoute pas) : c'est un asservissement visuel,
qui converge meme si le modele du drone est approximatif. Le PC du collegue convertit en commandes moteur.
mode = "cible"   : nouvelle cible a viser
mode = "maintien": continuer vers la derniere cible envoyee (cerceau hors champ, traversee en cours)
mode = "atterrir": fin de mission

L'axe du cerceau est la droite P(s) = C + s.n (C centre, n normale orientee dans le sens de la traversee) :
    A = C - standoff.n  : point d'approche, sur l'axe, avant le cerceau
    B = C + margin.n    : cible de traversee, sur l'axe, apres le plan du cerceau (marge d'avance)

Etats :
    RECHERCHE  : rotation par paliers jusqu'a voir un cerceau confirme sur plusieurs images
    APPROCHE   : cap vers le centre C, avancer jusqu'a la distance d'alignement (normale encore peu fiable)
    ALIGNEMENT : viser A ; cap vers C (garde le cerceau centre) ; sortie quand aligne et stable
    TRAVERSEE  : cible B figee, vision ignoree, pendant la duree estimee de la traversee
    PERTE      : cerceau disparu : on continue vers la derniere cible, puis on revient au dernier cap, puis RECHERCHE
    FIN        : nombre de cerceaux atteint, ou recherche infructueuse
"""

import math
from dataclasses import asdict, dataclass, field

import numpy as np
import yaml

DEFAULTS = {
    "confirm_frames": 3,          # detections consecutives pour confirmer un cerceau
    "search_step_deg": 30,        # palier de rotation pendant la recherche (champ horizontal : 55 deg)
    "search_pause_s": 0.5,        # pause une fois le palier atteint (image nette, temps de calcul)
    "search_reach_tol_deg": 5.0,  # palier considere atteint a 5 deg pres (cap mesure par l'IMU)
    "search_total_deg": 380.0,    # rotation reellement parcourue avant d'abandonner (un peu plus d'un tour)
    "search_step_timeout_s": 4.0, # palier jamais atteint : on passe au suivant quand meme
    "search_blind_pause_s": 1.5,  # sans cap transmis : attente fixe par palier
    "search_max_steps": 14,       # sans cap transmis : nombre de paliers avant d'abandonner
    "approach_until_m": 2.0,      # distance au centre a partir de laquelle on s'aligne sur l'axe
    "approach_step_m": 0.6,       # deplacement maximal demande par consigne pendant l'approche
    "standoff_m": 1.0,            # point A : distance avant le plan du cerceau
    "margin_m": 0.7,              # point B : marge apres le plan du cerceau (traversee reelle)
    "commit_max_dist_m": 1.4,     # distance au plan maximale pour s'engager
    "align_tol_lateral_m": 0.10,  # tolerances d'alignement
    "align_tol_vertical_m": 0.10,
    "align_tol_yaw_deg": 8.0,
    "align_stable_s": 0.5,        # duree pendant laquelle l'alignement doit tenir
    "traverse_speed_mps": 0.4,    # vitesse supposee pendant la traversee (duree = distance / vitesse)
    "traverse_extra_s": 1.0,      # marge de temps
    "lost_continue_s": 1.5,       # PERTE : on continue vers la derniere cible pendant cette duree
    "lost_return_s": 2.0,         # puis on revient au dernier cap ou le cerceau etait vu
    "passed_ignore_deg": 50.0,    # apres une traversee : ignorer un cerceau vu dans le dos (+-)
    "max_hoops": 1,               # nombre de cerceaux a traverser avant FIN
    "phase_timeout_s": 25.0,      # securite : duree maximale d'une phase (sauf recherche)
}


@dataclass
class Telemetry:
    """Etat du drone au moment de l'image (envoye par le PC du collegue avec l'image, si disponible)."""
    t: float                      # horodatage de la capture (s)
    yaw_deg: float = None         # cap absolu de l'IMU (get_yaw), > 0 a droite
    height_m: float = None        # hauteur (ToF)


@dataclass
class Command:
    frame_id: int
    t: float
    phase: str
    mode: str                     # "cible", "maintien", "atterrir"
    avant_m: float = 0.0          # cible relative, repere drone a l'instant de l'image
    droite_m: float = 0.0
    haut_m: float = 0.0
    lacet_deg: float = 0.0        # rotation relative, > 0 = droite
    confiance: float = 0.0
    ambigu: bool = False
    info: dict = field(default_factory=dict)
    vitesse_avant_mps: float = None   # renseignee : Y = PUISSANCE d'avance (rc) a tenir, et non une distance

    def to_dict(self):
        return asdict(self)


def wrap180(a):
    return (a + 180.0) % 360.0 - 180.0


def bearing_deg(v):
    """Direction horizontale d'un vecteur (avant, droite, haut) : > 0 a droite."""
    return math.degrees(math.atan2(v[1], v[0]))


class HoopGuidance:
    def __init__(self, params=None):
        self.p = dict(DEFAULTS)
        self.p.update(params or {})
        self.phase = "RECHERCHE"
        self.t_phase = None
        self.hoops_done = 0
        self.seen_streak = 0
        self.search_steps = 0
        self.t_last_step = None
        self.aligned_since = None
        self.traverse_until = None
        self.last_target = None           # derniere cible "vue" : (avant, droite, haut, lacet)
        self.last_seen_t = None
        self.last_seen_yaw_world = None   # cap absolu (IMU) vers le cerceau, quand il etait vu
        self.passed_yaw_world = None      # cap de la derniere traversee (pour ignorer le cerceau passe)
        self._goto("RECHERCHE", None)     # au demarrage : recherche (initialise aussi ses variables)

    @classmethod
    def from_yaml(cls, path="configs/guidance.yaml"):
        try:
            with open(path) as f:
                return cls(yaml.safe_load(f) or {})
        except FileNotFoundError:
            return cls()

    # ------------------------------------------------------------------ #
    def _goto(self, phase, t):
        self.phase, self.t_phase = phase, t
        self.aligned_since = None
        if phase == "RECHERCHE":
            self.search_steps, self.t_last_step = 0, None
            self.search_target_yaw, self.search_reached_t = None, None
            self.search_turned, self.search_prev_yaw = 0.0, None

    def _cmd(self, fid, t, mode, target=None, d=None, **info):
        a, b, c, y = target if target is not None else (0.0, 0.0, 0.0, 0.0)
        return Command(fid, t, self.phase, mode, float(a), float(b), float(c), float(y),
                       float(d.p) if d is not None else 0.0, bool(d.ambiguous) if d is not None else False, info)

    def _usable(self, d, tel):
        """Detection exploitable ? (presente, pose 3D, et pas le cerceau qu'on vient de traverser)."""
        if d is None or not d.present or d.center_drone is None:
            return False
        if self.passed_yaw_world is not None and tel is not None and tel.yaw_deg is not None:
            yaw_to_hoop = wrap180(tel.yaw_deg + bearing_deg(d.center_drone))
            behind = wrap180(self.passed_yaw_world + 180.0)
            if abs(wrap180(yaw_to_hoop - behind)) < self.p["passed_ignore_deg"]:
                return False                      # c'est le cerceau qu'on vient de passer, vu de dos
        return True

    def _search_with_yaw(self, frame_id, t, yaw):
        """Recherche guidee par le cap mesure : palier suivant seulement quand le precedent est atteint."""
        p = self.p
        if self.search_prev_yaw is not None:      # rotation reellement parcourue (sens de la recherche)
            self.search_turned += max(0.0, wrap180(yaw - self.search_prev_yaw) * math.copysign(1, p["search_step_deg"]))
        self.search_prev_yaw = yaw
        if self.search_turned >= p["search_total_deg"]:
            self._goto("FIN", t)
            return self._cmd(frame_id, t, "atterrir", info={"raison": "aucun cerceau trouve apres un tour"})
        new_step = self.search_target_yaw is None
        if not new_step:
            if abs(wrap180(self.search_target_yaw - yaw)) <= p["search_reach_tol_deg"]:
                self.search_reached_t = self.search_reached_t if self.search_reached_t is not None else t
                new_step = t - self.search_reached_t >= p["search_pause_s"]
            new_step = new_step or t - self.t_last_step >= p["search_step_timeout_s"]
        if new_step:
            self.search_steps += 1
            self.t_last_step, self.search_reached_t = t, None
            self.search_target_yaw = wrap180(yaw + p["search_step_deg"])
            return self._cmd(frame_id, t, "cible", (0, 0, 0, p["search_step_deg"]),
                             info={"palier": self.search_steps, "tourne_deg": round(self.search_turned)})
        rest = wrap180(self.search_target_yaw - yaw)      # cible du palier en cours, mise a jour (consigne remplacee)
        return self._cmd(frame_id, t, "cible", (0, 0, 0, rest), info={"palier": self.search_steps})

    # ------------------------------------------------------------------ #
    def step(self, d, tel: Telemetry, frame_id=0):
        """d : Detection (detector.py) ou None ; tel : etat du drone a l'image. Renvoie une Command."""
        t = tel.t
        if self.t_phase is None:
            self.t_phase = t
        p = self.p
        usable = self._usable(d, tel)
        self.seen_streak = self.seen_streak + 1 if usable else 0

        if self.phase == "FIN":
            return self._cmd(frame_id, t, "atterrir")

        if self.phase not in ("RECHERCHE", "TRAVERSEE") and t - self.t_phase > p["phase_timeout_s"]:
            self._goto("RECHERCHE", t)            # securite : phase bloquee

        # ---------------- TRAVERSEE : cible figee, vision ignoree ---------------- #
        if self.phase == "TRAVERSEE":
            if t < self.traverse_until:
                return self._cmd(frame_id, t, "maintien", info={"reste_s": round(self.traverse_until - t, 2)})
            self.hoops_done += 1
            self._goto("FIN" if self.hoops_done >= p["max_hoops"] else "RECHERCHE", t)
            return self._cmd(frame_id, t, "atterrir" if self.phase == "FIN" else "maintien")

        # ---------------- RECHERCHE : rotation par paliers ---------------- #
        if self.phase == "RECHERCHE":
            if self.seen_streak >= p["confirm_frames"]:
                self._goto("APPROCHE", t)
            elif tel.yaw_deg is not None:
                return self._search_with_yaw(frame_id, t, tel.yaw_deg)
            else:                                 # sans cap transmis : paliers au temps, pauses plus longues
                if self.t_last_step is None or t - self.t_last_step >= p["search_blind_pause_s"]:
                    if self.search_steps >= p["search_max_steps"]:
                        self._goto("FIN", t)
                        return self._cmd(frame_id, t, "atterrir", info={"raison": "aucun cerceau trouve"})
                    self.search_steps += 1
                    self.t_last_step = t
                    return self._cmd(frame_id, t, "cible", (0, 0, 0, p["search_step_deg"]),
                                     info={"palier": self.search_steps})
                return self._cmd(frame_id, t, "maintien")

        # ---------------- PERTE du cerceau ---------------- #
        if not usable:
            if self.last_seen_t is None:
                self._goto("RECHERCHE", t)
                return self._cmd(frame_id, t, "maintien")
            if self.phase != "PERTE":
                self._goto("PERTE", t)
            dt = t - self.last_seen_t
            if dt < p["lost_continue_s"]:
                return self._cmd(frame_id, t, "maintien", info={"perdu_depuis_s": round(dt, 2)})
            if dt < p["lost_continue_s"] + p["lost_return_s"] and tel.yaw_deg is not None \
                    and self.last_seen_yaw_world is not None:
                back = wrap180(self.last_seen_yaw_world - tel.yaw_deg)       # revenir au dernier cap utile
                return self._cmd(frame_id, t, "cible", (0, 0, 0, back), info={"retour_cap": True})
            self._goto("RECHERCHE", t)
            return self._cmd(frame_id, t, "maintien")

        # ---------------- le cerceau est vu ---------------- #
        if self.phase == "PERTE":
            self._goto("ALIGNEMENT" if d.distance_m <= p["approach_until_m"] else "APPROCHE", t)
        C = np.asarray(d.center_drone, float)
        n = np.asarray(d.normal_drone, float)
        bearing = bearing_deg(C)                  # cap vers le centre : garde le cerceau au milieu de l'image
        self.last_seen_t = t
        if tel.yaw_deg is not None:
            self.last_seen_yaw_world = wrap180(tel.yaw_deg + bearing)

        if self.phase == "APPROCHE":
            dist = float(np.linalg.norm(C))
            if dist <= p["approach_until_m"] and not d.ambiguous:
                self._goto("ALIGNEMENT", t)
            else:
                u = C / max(dist, 1e-6)
                go = max(dist - p["approach_until_m"] + 0.2, 0.0)            # avancer vers le centre
                go = min(go, p["approach_step_m"])
                target = (u * go)
                target[2] = C[2]                                              # se mettre a la hauteur du centre
                self.last_target = (*target, bearing)
                return self._cmd(frame_id, t, "cible", self.last_target, d, distance_m=round(dist, 2))

        # ALIGNEMENT : viser A, sur l'axe, en gardant le cerceau centre
        A = C - p["standoff_m"] * n
        pdrone = -C
        s_axis = float(pdrone @ n)                 # < 0 : avant le plan du cerceau
        off = pdrone - s_axis * n
        lateral, vertical = float(off[1]), float(off[2])
        yaw_axis = bearing_deg(n)
        aligned = (abs(lateral) < p["align_tol_lateral_m"] and abs(vertical) < p["align_tol_vertical_m"]
                   and abs(yaw_axis) < p["align_tol_yaw_deg"] and -s_axis <= p["commit_max_dist_m"]
                   and not d.ambiguous)
        if aligned:
            self.aligned_since = self.aligned_since if self.aligned_since is not None else t
        else:
            self.aligned_since = None
        info = {"distance_plan_m": round(-s_axis, 2), "ecart_lateral_m": round(lateral, 3),
                "ecart_vertical_m": round(vertical, 3), "cap_axe_deg": round(yaw_axis, 1)}

        if self.aligned_since is not None and t - self.aligned_since >= p["align_stable_s"]:
            B = C + p["margin_m"] * n             # TRAVERSEE : cible B, puis on ne regarde plus
            self._goto("TRAVERSEE", t)
            dist_B = float(np.linalg.norm(B))
            self.traverse_until = t + dist_B / p["traverse_speed_mps"] + p["traverse_extra_s"]
            if tel.yaw_deg is not None:
                self.passed_yaw_world = wrap180(tel.yaw_deg + yaw_axis)
            self.last_target = (*B, yaw_axis)
            return self._cmd(frame_id, t, "cible", self.last_target, d, **info, distance_B_m=round(dist_B, 2))

        if d.ambiguous:                           # normale incertaine : pas de decalage lateral franc
            u = C / max(np.linalg.norm(C), 1e-6)
            A = C - p["standoff_m"] * u
        self.last_target = (*A, bearing)
        return self._cmd(frame_id, t, "cible", self.last_target, d, **info)
