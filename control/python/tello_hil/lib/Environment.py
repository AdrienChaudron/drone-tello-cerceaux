import time

from lib.MqttInterface import TelloMQTTInterface
from tello_hil.lib.PayloadVision import PayloadVision
from tello_hil.lib.EtatVision import EtatVision


class Environment:
    T_sample: float
    start_time: float
    log_folder: str
    _tello_running: bool
    neural_network: TelloMQTTInterface
    _initial_tof: int
    remote_deadman: bool
    pv: PayloadVision

    def __init__(self, T_sample: float, log_folder: str) -> None:
        self.T_sample = T_sample
        self.start_time = time.time()
        self.log_folder = log_folder
        self._tello_running = False
        self.remote_deadman = False
        self.pv = PayloadVision()

    def set_tello_running_state(self, state: bool) -> None:
        self._tello_running = state

    def get_tello_running_state(self) -> bool:
        return self._tello_running

    def set_initial_tof(self, tof: int) -> None:
        self._initial_tof = tof

    def get_initial_tof(self) -> int:
        return self._initial_tof

    def __str__(self) -> str:
        elapsed_time = time.time() - self.start_time
        initial_tof = getattr(self, "_initial_tof", "Not set")
        has_nn = "Initialized" if hasattr(self, "neural_network") else "Not set"

        return (
            f"Environment(\n"
            f"  T_sample: {self.T_sample}s,\n"
            f"  Elapsed Time: {elapsed_time:.2f}s,\n"
            f"  Log Folder: '{self.log_folder}',\n"
            f"  Tello Running: {self._tello_running},\n"
            f"  Initial ToF: {initial_tof},\n"
            f"  Neural Network Interface: {has_nn}\n"
            f")"
        )

    def set_vision_offsets(self, x: float, y: float) -> None:
        self._vision_offset_width = x
        self._vision_offset_height = y

    def set_pv(self, etat: str, present: bool, delta_x: int | None, delta_z: float, distance: float, r_yaw: int, r_z: int):
        self.pv.set_payload_vision(
            etat,
            present,
            - 1 * float(delta_x / 3) if type(delta_x) == int else 0,
            delta_z,
            distance,
            r_yaw,
            r_z
        )

    def get_pv(self) -> PayloadVision:
        return self.pv
