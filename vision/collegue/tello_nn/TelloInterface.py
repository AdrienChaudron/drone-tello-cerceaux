import sys
from pathlib import Path

ROOT_DIR = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT_DIR))

from lib.AxisName import AxisName
from lib.EtatVision import EtatVision
from lib.MqttInterface import TelloMQTTInterface

class TelloInterface:
    _tello_hil: TelloMQTTInterface

    def __init__(self, tello_hil_ip: str) -> None:
        self._tello_hil = TelloMQTTInterface(broker_ip=tello_hil_ip, client_id="tello_nn_controller")

    def start_communication(self) -> None:
        """Initializes MQTT connection and subscribes to archive and status telemetry."""
        self._tello_hil.init_mqtt_connection(
            subscribe_commands=False,
            subscribe_archive=True,
            subscribe_status=True
        )

    def send_command(self, x: int, y: int, z: int, yaw: int) -> None:
        """Sends command reference to the control loop."""
        self._tello_hil.push_command(x, y, z, yaw)

    def send_vision(self, etat: EtatVision, present: bool, delta_x: int | None, delta_z: float | None,
                    distance: float | None, r_yaw: int, r_z: int | None, **extra) -> None:
        """Sends the vision order (tello/vision/ordre) to the control PC. See TelloMQTTInterface.push_vision."""
        self._tello_hil.push_vision(etat, present, delta_x, delta_z, distance, r_yaw, r_z, **extra)

    def get_measures(self, axis: AxisName) -> int:
        """Retrieves the latest sensor/state estimate for a specified axis."""
        archive = self._tello_hil.retrieve_archive(axis, block=False, timeout=0.1)

        if archive is not None:
            return archive["measure"]
        else:
            raise ValueError("No value to fetch")

    # --- Drone Status Telemetry ---

    def get_battery(self) -> int:
        """Returns the drone battery percentage (0-100%)."""
        battery = self._tello_hil.get_battery()
        if battery is not None:
            return battery
        raise ValueError("No status value to fetch (battery)")

    def is_flying(self) -> bool:
        """Returns True if the drone is currently airborne, False otherwise."""
        flying = self._tello_hil.is_flying()
        if flying is not None:
            return flying
        raise ValueError("No status value to fetch (is_flying)")

    def get_temperature(self) -> float:
        """Returns the drone temperature in °C."""
        temp = self._tello_hil.get_temperature()
        if temp is not None:
            return temp
        raise ValueError("No status value to fetch (temperature)")

    def get_flight_time(self) -> int:
        """Returns drone flight time in seconds."""
        flight_time = self._tello_hil.get_flight_time()
        if flight_time is not None:
            return flight_time
        raise ValueError("No status value to fetch (flight_time)")

    def get_status(self) -> dict:
        """
        Returns the entire drone status dictionary:
        {'battery': int, 'is_flying': bool, 'temperature': float, 'flight_time': int}
        """
        status = self._tello_hil.retrieve_status()
        if status is not None:
            return status
        raise ValueError("No status value to fetch")

    def end_communication(self) -> None:
        """Disconnects cleanly from the MQTT broker."""
        self._tello_hil.end_mqtt_connection()
