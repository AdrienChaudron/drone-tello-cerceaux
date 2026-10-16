"""
unicycle.py : guidance NON HOLONOME (premier test) : le drone ne se deplace jamais de cote.

Seules commandes : avancer (Y) et tourner (YAW), comme une voiture, mais qui tourne sur place ; la hauteur (Z)
vise le centre du cerceau ; X (lateral) vaut toujours 0 (le VPS du Tello tient la position laterale).

AVANCE = VITESSE, pas distance : le PC de controle n'asservit pas Y, il envoie Y tel quel au Tello comme PUISSANCE
rc d'avance, tenue tant qu'on ne la change pas. La guidance commande donc une vitesse d'avance (m/s, `vitesse_avant_mps`)
petite, proportionnelle a ce qui reste jusqu'au point A (nulle en A), limitee en acceleration ; link.py la convertit en
puissance rc (`rc_par_mps`). L'estime integre cette vitesse commandee.

Loi de guidance (suivi de l'axe du cerceau en avancant, type Stanley / poursuite pure) :
        cap vise = cap de l'axe + atan(-ecart_lateral / L)
    le drone rejoint l'axe progressivement en avancant vers le point d'approche A (sur l'axe, `standoff_m` devant
    le cerceau) ; en A, aligne -> TRAVERSEE a l'aveugle jusqu'au point B (`margin_m` derriere le cerceau).

Champ de la camera (+-27 deg) : pour rejoindre l'axe d'un cerceau vu de biais, le drone doit parfois viser loin
du cerceau et le perdre de vue. C'est permis grace a la memoire, mais pas trop longtemps : apres `reacquire_m`
parcourus a l'aveugle, il s'arrete et se retourne vers le cerceau (+-`fov_keep_deg`) pour le re-mesurer, puis repart.

MEMOIRE du cerceau (pour ne pas perdre la trajectoire quand il sort de l'image) :
    a chaque detection, position du centre, hauteur et axe sont ranges dans un REPERE FIXE (le sol), filtres ;
    hors detection, la pose du drone est estimee (cap : IMU de l'en-tete ; avance : commandes envoyees, a une
    vitesse supposee) et la guidance continue sur la memoire. Memoire perimee (trop vieille ou trop de chemin
    parcouru a l'aveugle) -> RECHERCHE.

Repere fixe : (x, y) au sol, cap psi > 0 vers la droite ; avant = (cos psi, sin psi), droite = (-sin psi, cos psi).
"""

import math

import numpy as np
import yaml

from tellovision.guidance import Command, Telemetry, wrap180  # noqa: F401  (Telemetry : meme entree que guidance.py)

DEFAULTS = {
    "confirm_frames": 3,          # detections consecutives avant de suivre un cerceau
    "min_p": 0.5,                 # probabilite minimale d'une detection
    # loi de guidance
    "lookahead_m": 1.0,           # L : distance de visee sur l'axe
    "fov_keep_deg": 20.0,         # cap vise a +- 20 deg du relevement du cerceau (champ camera +-27 deg)
    "turn_first_deg": 25.0,       # erreur de cap au-dela : tourner sur place avant d'avancer
    "v_max_mps": 0.3,             # vitesse d'avance maximale (moderee : plus de mesures par metre)
    "v_first_mps": 0.15,          # vitesse maximale tant que le cerceau est peu connu (moins de `n_obs_confident` mesures)
    "n_obs_confident": 8,         # nombre de mesures du cerceau avant d'avancer a `v_max_mps`
    "v_gain": 0.8,                # vitesse = 0,8 /s x distance restante jusqu'a A : ralentit et s'annule en A
    "accel_mps2": 0.3,            # la vitesse commandee augmente d'au plus 0,3 m/s par seconde (freinage immediat)
    "standoff_m": 1.0,            # point d'approche A : 1 m devant le cerceau, sur l'axe
    "margin_m": 0.7,              # traversee : jusqu'a 0,7 m derriere le cerceau (point B)
    "commit_lat_m": 0.10,         # alignement requis pour traverser : ecart lateral...
    "commit_head_deg": 8.0,       # ... ecart de cap ...
    "commit_window_m": 0.35,      # ... et distance au point A
    "min_room_m": 0.6,            # plus pres du plan sans etre aligne -> RECUL (un unicycle doit avancer pour corriger)
    "recul_until_m": 1.6,         # ... jusqu'a etre a nouveau a 1,6 m du plan (hysteresis : pas d'aller-retour)
    "v_backup_mps": 0.3,          # vitesse de recul (pas trop lente : la memoire se perime pendant le recul)
    "v_creep_mps": 0.15,          # vitesse minimale pour corriger l'ecart lateral quand on est deja vers A
    "reacquire_m": 0.8,           # apres 0,8 m a l'aveugle : se retourner vers le cerceau pour le re-mesurer
    # memoire
    "alpha_pos": 0.35,            # lissage de la position du centre (0 = fige, 1 = derniere mesure)
    "alpha_axis": 0.25,           # lissage du cap de l'axe
    "outlier_m": 0.6,             # mesure a plus de 0,6 m de la memoire : ignoree...
    "outlier_confirm": 4,         # ... sauf si 4 mesures de suite concordent (cerceau deplace, ou memoire fausse)
    "memory_max_age_s": 6.0,      # memoire perimee apres 6 s sans voir le cerceau...
    "memory_max_travel_m": 2.5,   # ... ou 2,5 m parcourus a l'aveugle
    "retrouver_s": 5.0,           # memoire perimee : 5 s pour se tourner vers sa position (et reculer si trop pres)...
    "retrouver_dist_m": 1.4,      # ... en reculant tant qu'elle le place a moins de 1,4 m ; sinon : RECHERCHE
    "rc_par_mps": 50.0,           # puissance rc d'avance pour 1 m/s (essai du 09/10 : rc ~27 -> 0,54 m/s ; a identifier)
    "rc_max": 30,                 # puissance rc d'avance jamais depassee (en valeur absolue)
    # traversee, recherche
    "traverse_speed_mps": 0.3,    # vitesse constante pendant la traversee
    "traverse_time_factor": 1.3,  # duree de traversee = distance / vitesse x 1,3 : franchit le cerceau meme si
                                  # le drone est 25 % plus lent que commande (depasse d'autant s'il est plus rapide)
    "traverse_lookahead_m": 0.6,  # traversee : correction de cap sur l'axe (memoire + estime)...
    "traverse_max_corr_deg": 15.0,  # ... bornee a +-15 deg
    "traverse_extra_s": 1.0,
    "observe_s": 2.0,             # au demarrage : regarder 2 s sur place avant de chercher (confirmer un cerceau deja en vue)
    "search_step_deg": 30.0,
    "search_pause_s": 1.2,
    "search_total_deg": 380.0,
    "z_min_m": 0.4,               # consigne de hauteur toujours entre 0,4...
    "z_max_m": 2.0,               # ... et 2 m (ToF)
    "z_rate_mps": 0.15,           # et variant d'au plus 0,15 m/s (le temps d'affiner l'estimation de pres)
    "height_max_dist_m": 3.0,     # hauteur du cerceau memorisee seulement s'il est vu a moins de 3 m
    "search_climb_m": 0.5,        # tour complet sans cerceau : on monte de 0,5 m et on refait un tour...
    "search_levels": 3,           # ... au plus 3 tours (hauteur de depart, +0,5 m, +1 m)...
    "search_max_height_m": 2.0,   # ... sans jamais viser plus de 2 m (ToF)
    "search_climb_wait_s": 2.5,   # temps laisse pour monter avant de reprendre la rotation
    "max_hoops": 1,
}


def _unit(a):
    return np.array([math.cos(a), math.sin(a)])


def _wrap_pi(a):
    return (a + math.pi) % (2 * math.pi) - math.pi


class HoopMemory:
    """Cerceau dans le repere fixe : centre C (x, y), hauteur absolue H (m), cap de l'axe phi (rad, sens de traversee)."""

    def __init__(self):
        self.C = None
        self.H = None
        self.phi = None
        self.t_seen = None
        self.travel_blind = 0.0
        self.n_obs = 0
        self._outliers = []

    @property
    def valid(self):
        return self.C is not None and self.phi is not None


class UnicycleGuidance:
    def __init__(self, params=None):
        self.p = dict(DEFAULTS)
        self.p.update(params or {})
        self.mem = HoopMemory()
        self.P = np.zeros(2)          # position estimee du drone (repere fixe, origine au demarrage)
        self.t_prev = None
        self.v_cmd = 0.0              # vitesse d'avance commandee en cours (m/s), pour l'estime et l'acceleration
        self.seen_streak = 0
        self.phase = "RECHERCHE"
        self.search_turned = 0.0
        self.t_search = None
        self.traverse_until = None
        self.hoops_done = 0
        self.backing = False          # RECUL en cours (jusqu'a recul_until_m)
        self.t_retrouver = None       # debut de la tentative RETROUVER (memoire perimee)
        self.t_start = None           # premiere image (observation avant la recherche)
        self.z_search = None          # hauteur (ToF, m) du tour de recherche en cours
        self._z_out = self._z_t = None  # derniere consigne de hauteur envoyee (bornes et vitesse limitee)
        self.search_level = 0         # numero du tour (0 = hauteur de depart)
        self._t_cmd = None            # instant de la derniere commande (limite d'acceleration)

    @classmethod
    def from_yaml(cls, path="configs/unicycle.yaml"):
        try:
            with open(path) as f:
                return cls(yaml.safe_load(f) or {})
        except FileNotFoundError:
            return cls()

    # ------------------------------------------------------------------ #
    # Estime : avance du drone depuis l'image precedente
    # ------------------------------------------------------------------ #
    def _dead_reckoning(self, t, psi):
        if self.t_prev is not None:
            dt = max(0.0, t - self.t_prev)
            adv = self.v_cmd * min(dt, 0.5)                          # au plus 0,5 s (image perdue, pause)
            self.P = self.P + adv * _unit(psi)
            if self.mem.valid and self.mem.t_seen != t:
                self.mem.travel_blind += abs(adv)
        self.t_prev = t

    # ------------------------------------------------------------------ #
    # Memoire : mise a jour par une detection
    # ------------------------------------------------------------------ #
    def _update_memory(self, d, t, psi, tof_m):
        a, b, c = (float(v) for v in d.center_drone)
        f, r = _unit(psi), _unit(psi + math.pi / 2)
        C_meas = self.P + a * f + b * r
        dist = math.sqrt(a * a + b * b + c * c)
        # hauteur du cerceau : seulement de pres (de loin, l'erreur d'inclinaison et d'ellipse est trop grande)
        H_meas = (tof_m + c) if (tof_m is not None and dist <= self.p["height_max_dist_m"]) else None
        phi_meas = None
        if getattr(d, "normal_drone", None) is not None:
            n = np.asarray(d.normal_drone, float)
            phi_meas = psi + math.atan2(n[1], n[0])                  # cap de l'axe dans le repere fixe
            if np.dot(C_meas - self.P, _unit(phi_meas)) < 0:         # oriente dans le sens de la traversee
                phi_meas += math.pi
        m, p = self.mem, self.p

        if m.C is not None and np.linalg.norm(C_meas - m.C) > p["outlier_m"]:
            m._outliers.append(C_meas)                               # mesure aberrante : on attend confirmation
            if len(m._outliers) < p["outlier_confirm"]:
                return False
            if np.ptp(np.array(m._outliers), axis=0).max() > p["outlier_m"]:
                m._outliers = m._outliers[-1:]
                return False
            m.C, m.phi = np.mean(m._outliers, axis=0), None          # nouvelle position confirmee : on repart
        m._outliers = []

        m.C = C_meas if m.C is None else (1 - p["alpha_pos"]) * m.C + p["alpha_pos"] * C_meas
        if H_meas is not None:
            m.H = H_meas if m.H is None else 0.7 * m.H + 0.3 * H_meas
        if phi_meas is not None and not (getattr(d, "ambiguous", False) and m.phi is not None):
            if m.phi is None:
                m.phi = phi_meas
            else:                                                     # moyenne circulaire
                m.phi = m.phi + p["alpha_axis"] * _wrap_pi(phi_meas - m.phi)
        m.t_seen, m.travel_blind = t, 0.0
        m.n_obs += 1
        return True

    def _memory_fresh(self, t):
        m = self.mem
        return (m.valid and t - m.t_seen <= self.p["memory_max_age_s"]
                and m.travel_blind <= self.p["memory_max_travel_m"])

    # ------------------------------------------------------------------ #
    def _cmd(self, fid, t, mode, vitesse=0.0, haut=0.0, lacet_deg=0.0, d=None, **info):
        """vitesse : vitesse d'avance voulue (m/s, < 0 = recul) ; toujours 0 hors mode "cible"."""
        v = float(vitesse) if mode == "cible" else 0.0
        if abs(v) > abs(self.v_cmd) and v * self.v_cmd >= 0:           # acceleration limitee, freinage immediat
            dv = self.p["accel_mps2"] * max(0.0, t - self._t_cmd) if self._t_cmd is not None else abs(v)
            v = math.copysign(min(abs(v), abs(self.v_cmd) + dv), v)
        self.v_cmd, self._t_cmd = v, t
        return Command(fid, t, self.phase, mode, 0.0, 0.0, float(haut), float(lacet_deg),
                       float(d.p) if d is not None else 0.0, bool(getattr(d, "ambiguous", False)) if d else False,
                       info, vitesse_avant_mps=v)

    def _z_safe(self, z_target, t, tof_m):
        """Consigne de hauteur absolue SURE : bornee [z_min, z_max] et variant d'au plus z_rate m/s."""
        p = self.p
        z = min(max(z_target, p["z_min_m"]), p["z_max_m"])
        if self._z_out is None:
            self._z_out = tof_m if tof_m is not None else z
        if self._z_t is not None:
            dz = p["z_rate_mps"] * max(0.0, t - self._z_t)
            z = min(max(z, self._z_out - dz), self._z_out + dz)
        self._z_out, self._z_t = z, t
        return z

    def _haut(self, tof_m, t=None):
        """Ecart vertical a commander (m) vers la hauteur memorisee du cerceau, borne et limite en vitesse."""
        if tof_m is None:
            return 0.0
        target = self.mem.H if self.mem.H is not None else (self._z_out if self._z_out is not None else tof_m)
        return float(self._z_safe(target, self.t_prev if t is None else t, tof_m) - tof_m)

    def step(self, d, tel: Telemetry, frame_id=0):
        """d : Detection (detector.py) ou None ; tel : t, yaw_deg (cap IMU), height_m (ToF). Renvoie une Command."""
        p, t = self.p, tel.t
        psi = math.radians(tel.yaw_deg or 0.0)
        tof_m = tel.height_m
        self._dead_reckoning(t, psi)

        usable = (d is not None and d.present and d.p >= p["min_p"] and d.center_drone is not None)
        self.seen_streak = self.seen_streak + 1 if usable else 0
        seen = usable and (self.mem.valid or self.seen_streak >= p["confirm_frames"])
        if seen and self.phase not in ("TRAVERSEE", "FIN"):
            self._update_memory(d, t, psi, tof_m)

        # ---------------- FIN / TRAVERSEE ---------------- #
        if self.phase == "FIN":
            return self._cmd(frame_id, t, "atterrir")
        if self.phase == "TRAVERSEE":
            m = self.mem
            rel = self.P - m.C
            s_tr, e_tr = float(rel @ _unit(m.phi)), float(rel @ _unit(m.phi + math.pi / 2))
            left = p["margin_m"] - s_tr                                 # reste jusqu'au point B (estime, indicatif)
            # on avance en continu jusqu'a la fin du temps prevu (prudent) : ne PAS s'arreter sur l'estime, qui
            # croirait le cerceau franchi trop tot si le drone est plus lent que suppose (arret DANS le cerceau)
            if t < self.traverse_until:
                # vision ignoree (cerceau trop proche, coupe) ; cap corrige sur l'axe par la memoire et l'estime
                corr = math.atan2(-e_tr, p["traverse_lookahead_m"])
                lim = math.radians(p["traverse_max_corr_deg"])
                psi_t = m.phi + max(-lim, min(lim, corr))
                return self._cmd(frame_id, t, "cible", vitesse=p["traverse_speed_mps"], haut=self._haut(tof_m),
                                 lacet_deg=math.degrees(_wrap_pi(psi_t - psi)),
                                 reste_m=round(left, 2), ecart_lateral_m=round(e_tr, 2))
            self.hoops_done += 1
            self.mem = HoopMemory()
            self.backing = False
            self.phase = "FIN" if self.hoops_done >= p["max_hoops"] else "RECHERCHE"
            self.t_search, self.search_turned = None, 0.0
            self.z_search, self.search_level = None, 0
            return self._cmd(frame_id, t, "atterrir" if self.phase == "FIN" else "maintien")

        # ---------------- RETROUVER : memoire perimee mais encore indicative ---------------- #
        if self._memory_fresh(t):
            self.t_retrouver = None
        elif self.mem.C is not None:
            if self.t_retrouver is None:
                self.t_retrouver = t
            if t - self.t_retrouver <= p["retrouver_s"]:
                self.phase = "RETROUVER"
                to_C = self.mem.C - self.P
                bearing = math.atan2(to_C[1], to_C[0])
                err = _wrap_pi(bearing - psi)
                back = p["v_backup_mps"] if (np.linalg.norm(to_C) < p["retrouver_dist_m"]
                                         and abs(math.degrees(err)) < p["turn_first_deg"]) else 0.0
                return self._cmd(frame_id, t, "cible", vitesse=-back, haut=self._haut(tof_m),
                                 lacet_deg=math.degrees(err), memoire_age_s=round(t - self.mem.t_seen, 2))
            self.mem, self.t_retrouver = HoopMemory(), None              # echec : on oublie, recherche complete

        # ---------------- RECHERCHE : tours de 360 deg, en montant de `search_climb_m` entre deux tours ----------- #
        if not self._memory_fresh(t):
            if self.phase != "RECHERCHE":
                self.phase, self.t_search, self.search_turned = "RECHERCHE", None, 0.0
            if self.t_start is None:
                self.t_start = t
            if self.z_search is None and tof_m is not None:
                self.z_search = tof_m                                   # 1er tour a la hauteur actuelle
            haut_s = (self._z_safe(self.z_search, t, tof_m) - tof_m) if (self.z_search is not None and tof_m is not None) else 0.0
            if self.hoops_done == 0 and self.search_turned == 0 and t - self.t_start < p["observe_s"]:
                return self._cmd(frame_id, t, "maintien", observation=True)   # on regarde avant de tourner
            if self.search_turned >= p["search_total_deg"]:            # tour complet sans cerceau
                z_next = (self.z_search or 0.0) + p["search_climb_m"]
                if self.search_level + 1 < p["search_levels"] and z_next <= p["search_max_height_m"]:
                    self.search_level += 1                              # on monte d'un palier et on refait un tour
                    self.z_search, self.search_turned = z_next, 0.0
                    self.t_search = t + p["search_climb_wait_s"]        # le temps de monter avant de tourner
                    return self._cmd(frame_id, t, "cible",
                                     haut=(self._z_safe(z_next, t, tof_m) - tof_m) if tof_m is not None else 0.0,
                                     palier_hauteur_m=round(z_next, 2), niveau=self.search_level)
                self.phase = "FIN"
                return self._cmd(frame_id, t, "atterrir",
                                 raison=f"aucun cerceau trouve ({self.search_level + 1} tours, jusqu'a "
                                        f"{(self.z_search or 0):.2f} m)")
            if self.t_search is None or t - self.t_search >= p["search_pause_s"]:
                self.t_search = t
                self.search_turned += p["search_step_deg"]
                return self._cmd(frame_id, t, "cible", lacet_deg=p["search_step_deg"], haut=haut_s, palier=True,
                                 niveau=self.search_level)
            return self._cmd(frame_id, t, "maintien")

        # ---------------- SUIVI de l'axe (cerceau vu ou en memoire) ---------------- #
        m = self.mem
        n, perp = _unit(m.phi), _unit(m.phi + math.pi / 2)
        rel = self.P - m.C
        s = float(rel @ n)                          # abscisse le long de l'axe (< 0 : avant le plan du cerceau)
        e_lat = float(rel @ perp)                   # ecart lateral a l'axe (> 0 : a droite de l'axe)
        head_err_axis = math.degrees(_wrap_pi(psi - m.phi))
        bearing = math.atan2(*(m.C - self.P)[::-1])  # relevement du centre du cerceau
        self.phase = "SUIVI" if seen else "MEMOIRE"
        info = dict(s_m=round(s, 2), ecart_lateral_m=round(e_lat, 2), ecart_cap_deg=round(head_err_axis, 1),
                    vu=bool(seen), memoire_age_s=round(t - m.t_seen, 2), aveugle_m=round(m.travel_blind, 2))
        haut = self._haut(tof_m)

        aligned = abs(e_lat) < p["commit_lat_m"] and abs(head_err_axis) < p["commit_head_deg"]
        if aligned and abs(s + p["standoff_m"]) < p["commit_window_m"]:
            dist = -s + p["margin_m"]                                  # jusqu'au point B, derriere le cerceau
            self.phase = "TRAVERSEE"
            self.traverse_until = t + dist / p["traverse_speed_mps"] * p["traverse_time_factor"] + p["traverse_extra_s"]
            return self._cmd(frame_id, t, "cible", vitesse=p["traverse_speed_mps"], haut=haut,
                             lacet_deg=math.degrees(_wrap_pi(m.phi - psi)), d=d, traversee_m=round(dist, 2), **info)

        keep = math.radians(p["fov_keep_deg"])
        if s > -p["min_room_m"] and not aligned:                       # trop pres pour corriger : on recule
            self.backing = True
        if self.backing and s < -p["recul_until_m"]:
            self.backing = False
        if self.backing:
            # reculer LE LONG DE L'AXE (cap = axe, borne pour garder le cerceau en vue) : s diminue vraiment
            self.phase = "RECUL"
            psi_b = bearing + max(-keep, min(keep, _wrap_pi(m.phi - bearing)))
            err_b = _wrap_pi(psi_b - psi)
            back = p["v_backup_mps"] if abs(math.degrees(err_b)) < p["turn_first_deg"] else 0.0
            return self._cmd(frame_id, t, "cible", vitesse=-back, haut=haut, lacet_deg=math.degrees(err_b), d=d, **info)

        # loi de suivi de l'axe (forme continue, sans point vise : jamais de demi-tour) :
        #   cap vise = cap de l'axe + atan(-ecart lateral / L)  (> 0 a droite de l'axe -> tourner a gauche)
        psi_t = m.phi + math.atan2(-e_lat, p["lookahead_m"])
        # vitesse : proportionnelle a ce qui reste jusqu'au point A le long de l'axe (nulle en A) ; un minimum (creep)
        # si on n'est pas aligne, car un unicycle doit avancer pour reduire l'ecart lateral (RECUL plus pres que min_room)
        to_A = -p["standoff_m"] - s
        dist = max(to_A, abs(e_lat) * 0.5, 0.0)
        v = p["v_gain"] * dist if aligned else max(p["v_gain"] * dist, p["v_creep_mps"])
        # trop longtemps a l'aveugle : s'arreter et se retourner vers le cerceau pour le re-mesurer
        look = (not seen) and m.travel_blind > p["reacquire_m"]
        if look:
            self.phase = "RELEVE"
            psi_t = bearing + max(-keep, min(keep, _wrap_pi(psi_t - bearing)))
        err = _wrap_pi(psi_t - psi)
        if look or abs(math.degrees(err)) > p["turn_first_deg"]:
            v = 0.0                                                     # tourner sur place d'abord
        else:
            v_max = p["v_max_mps"] if m.n_obs >= p["n_obs_confident"] else p["v_first_mps"]   # prudent au debut
            v = min(v_max, v) * max(0.0, math.cos(err))
        return self._cmd(frame_id, t, "cible", vitesse=v, haut=haut, lacet_deg=math.degrees(err), d=d,
                         cap_vise_deg=round(math.degrees(psi_t), 1), **info)
