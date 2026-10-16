from tello_hil.lib.EtatVision import EtatVision


class PayloadVision:
    etat: EtatVision
    present: bool
    delta_x: float | None
    delta_z: float | None
    distance: float | None
    r_yaw: int | None
    r_z: int | None

    def __init__(self):
        self.etat = EtatVision.RECHERCHE
        self.present = False
        self.delta_x = 0.0
        self.delta_z = 0.0
        self.distance = 0.0
        self.r_yaw = 0
        self.r_z = 0

    def set_payload_vision(self, etat: str, present: bool, delta_x: float | None, delta_z: float | None, distance: float | None, r_yaw: int | None, r_z: int | None):
        self.etat = EtatVision(etat)
        self.present = present
        self.delta_x = delta_x
        self.delta_z = delta_z
        self.distance = distance
        self.r_yaw = r_yaw
        self.r_z = r_z

    def get_delta_x(self) -> float:
        return self.delta_x if type(self.delta_x) == float else 0

    def get_delta_z(self) -> float:
        return self.delta_z if type(self.delta_z) == float else 0

    def get_yaw_reference(self) -> float:
        return self.r_yaw if type(self.r_yaw) == int else 0

    def get_z_reference(self) -> float:
        return self.r_z if type(self.r_z) == int else 0

    def get_state(self) -> EtatVision:
        return self.etat

    def get_distance_to_circle(self) -> float:
        return self.distance if type(self.distance) == float else 0

    def __str__(self) -> str:
        return (
            f"PayloadVision("
            f"etat={self.etat}, "
            f"present={self.present}, "
            f"delta_x={self.delta_x}, "
            f"delta_z={self.delta_z}, "
            f"distance={self.distance}, "
            f"r_yaw={self.r_yaw}, "
            f"r_z={self.r_z})"
        )
