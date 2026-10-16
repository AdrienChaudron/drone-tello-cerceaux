from enum import Enum


class EtatVision(Enum):
    """Etat de la vision, envoye avec chaque ordre (push_vision / retrieve_vision)."""
    RECHERCHE = "RECHERCHE"        # pas de cerceau : r_yaw (paliers) et r_z (hauteur de recherche) a suivre
    MISE_EN_AXE = "MISE_EN_AXE"    # cerceau vu : delta_x, delta_z, distance valables ; r_yaw vers le cerceau
    PERDU = "PERDU"                # cerceau perdu de loin : dernier r_yaw tenu 2 s, puis RECHERCHE
    TRAVERSEE = "TRAVERSEE"        # cerceau perdu de pres : le drone est en train de le passer
    ECHEC = "ECHEC"                # 3 tours de recherche sans cerceau


RECHERCHE = EtatVision.RECHERCHE
MISE_EN_AXE = EtatVision.MISE_EN_AXE
PERDU = EtatVision.PERDU
TRAVERSEE = EtatVision.TRAVERSEE
ECHEC = EtatVision.ECHEC
