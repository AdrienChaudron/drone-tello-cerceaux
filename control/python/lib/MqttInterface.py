import json
import queue
import threading

import paho.mqtt.client as mqtt
from lib.AxisName import YAW, AxisName, X, Y, Z


class TelloMQTTInterface:
    def __init__(self, broker_ip: str, port: int = 1883, username: str = "tello", password: str = "tello", client_id: str = "tello_node"):
        self.broker_ip = broker_ip
        self.port = port
        self.username = username
        self.password = password
        self.client_id = client_id

        # Topics
        self.cmd_topic = "tello/commands"
        self.status_topic = "tello/status"
        self.archive_base_topic = "tello/archive"
        self.archive_all_topic = "tello/archive/+"
        self.vision_topic = "tello/vision/ordre"

        # Storage & synchronization
        self.cmd_queue = queue.Queue()

        self.latest_archive = {}
        self.archive_lock = threading.Lock()

        self.latest_status = {}
        self.status_lock = threading.Lock()

        self.latest_vision = {}
        self.vision_lock = threading.Lock()

        # MQTT Client initialization
        self.client = mqtt.Client(client_id=self.client_id)
        self.client.on_connect = self._on_connect
        self.client.on_message = self._on_message

    def _on_connect(self, client, userdata, flags, rc):
        if rc == 0:
            print(f"[{self.client_id}] Connected successfully to broker at {self.broker_ip}")
        else:
            print(f"[{self.client_id}] Connection failed with return code: {rc}")

    def _on_message(self, client, userdata, msg):
        try:
            payload = json.loads(msg.payload.decode("utf-8"))

            # 1. Incoming Target Commands
            if msg.topic == self.cmd_topic:
                self.cmd_queue.put(payload)

            # 2. Incoming Status Telemetry
            elif msg.topic == self.status_topic:
                with self.status_lock:
                    self.latest_status = payload

            # 3. Incoming Vision Order (latest only)
            elif msg.topic == self.vision_topic:
                with self.vision_lock:
                    self.latest_vision = payload

            # 4. Incoming Archive / Telemetry Data
            elif msg.topic.startswith(self.archive_base_topic):
                axis_name = msg.topic.split("/")[-1]
                with self.archive_lock:
                    self.latest_archive[axis_name] = payload

        except Exception as e:
            print(f"[{self.client_id}] Error decoding payload on {msg.topic}: {e}")

    def init_mqtt_connection(self, subscribe_commands: bool = False, subscribe_archive: bool = False, subscribe_status: bool = False, subscribe_vision: bool = False):
        """
        Connects to broker and conditionally subscribes based on the role.
        """
        self.client.username_pw_set(username=self.username, password=self.password)
        self.client.connect(self.broker_ip, self.port, keepalive=60)
        self.client.loop_start()

        if subscribe_commands:
            self.client.subscribe(self.cmd_topic, qos=0)

        if subscribe_archive:
            # Subscribes to all axes: tello/archive/axis_1, axis_2, etc.
            self.client.subscribe(self.archive_all_topic, qos=0)

        if subscribe_status:
            self.client.subscribe(self.status_topic, qos=0)

        if subscribe_vision:
            self.client.subscribe(self.vision_topic, qos=0)

    # --- PUSH METHODS ---

    def push_command(self, x: float, y: float, z: float, yaw: float):
        """Machine 1: Sends command references (cm, °, %, %)."""
        payload = {
            X.name: x,
            Y.name: y,
            Z.name: z,
            YAW.name: yaw
        }
        self.client.publish(self.cmd_topic, json.dumps(payload), qos=0)

    def publish_status(self, battery: int, is_flying: bool, temperature: float, flight_time: int, tof: float, yaw: float):
        """
        Publishes Tello physical status telemetry.
        - battery: percentage (0 - 100)
        - is_flying: boolean state
        - temperature: average temperature in °C
        - flight_time: elapsed flight time in seconds
        """
        payload = {
            "battery": battery,
            "is_flying": is_flying,
            "temperature": temperature,
            "flight_time": flight_time,
            "tof" : tof,
            "yaw" : yaw
        }
        self.client.publish(self.status_topic, json.dumps(payload), qos=0)

    def push_vision(self, etat: str, present: bool, delta_x: float | None, delta_z: float | None, distance: float | None, r_yaw: int, r_z: int | None):
        """
        PC vision : publie l'ordre de la vision (une fois par image traitee).
        - etat     : "RECHERCHE", "MISE_EN_AXE", "PERDU", "TRAVERSEE" ou "ECHEC"
        - present  : cerceau vu recemment (sinon delta_x, delta_z, distance valent None)
        - delta_x  : position LATERALE du centre du cerceau (m, repere du drone), > 0 : a droite
        - delta_z  : position VERTICALE du centre du cerceau (m), > 0 : plus haut que le drone
        - distance : distance du drone au centre du cerceau (m) : pour l'avance (axe Y)
        - r_yaw    : consigne de cap ABSOLUE (deg, meme repere que la mesure YAW)
        - r_z      : consigne de hauteur ABSOLUE (cm) pendant la recherche ; None sinon (hauteur sur delta_z)
        """
        payload = {
            "etat": etat,
            "present": present,
            "delta_x": delta_x,
            "delta_z": delta_z,
            "distance": distance,
            "r_yaw": r_yaw,
            "r_z": r_z,
        }
        self.client.publish(self.vision_topic, json.dumps(payload), qos=0)

    def archive_sys_result(self, axis_id: AxisName, timestamp: float, cmd_ref: float, cmd_corr: float, measure: float):
        """Machine 2: Pushes real-time axis results."""
        topic = f"{self.archive_base_topic}/{axis_id.name}"
        payload = {
            "timestamp": timestamp,
            "reference": cmd_ref,
            "command": cmd_corr,
            "measure": measure
        }
        self.client.publish(topic, json.dumps(payload), qos=0)

    # --- RETRIEVE METHODS ---

    def retrieve_command(self, block: bool = False, timeout: float | None = None):
        """Machine 2: Retrieves the latest command reference."""
        try:
            return self.cmd_queue.get(block=block, timeout=timeout)
        except queue.Empty:
            return None

    def retrieve_vision(self) -> dict | None:
        """
        PC de controle : dernier ordre de la vision, ou None si rien n'a ete recu.
        Format : {"etat", "present", "delta_x", "delta_z", "distance", "r_yaw", "r_z"} (voir push_vision)
        """
        with self.vision_lock:
            return dict(self.latest_vision) if self.latest_vision else None

    def retrieve_archive(self, axis_name: AxisName, block: bool = False, timeout: float | None = None):
        """
        Machine 1: Retrieves the next measure for a SPECIFIED axis.
        Example: retrieve_archive(X) or retrieve_archive(Z)
        Returns:
            dict: {"timestamp": ..., "reference": ..., "command": ..., "measure": ...}
            or None if no data has been received yet.
        """
        with self.archive_lock:
            return self.latest_archive.get(axis_name.name)

    def retrieve_status(self) -> dict | None:
        """
        Returns the entire latest status dict or None if not received yet.
        Format: {"battery": int, "is_flying": bool, "temperature": float, "flight_time": int}
        """
        with self.status_lock:
            return self.latest_status.copy() if self.latest_status else None

    def get_battery(self) -> int | None:
        """Returns the latest battery percentage or None."""
        with self.status_lock:
            return self.latest_status.get("battery")

    def is_flying(self) -> bool | None:
        """Returns the latest flying boolean state or None."""
        with self.status_lock:
            return self.latest_status.get("is_flying")

    def get_temperature(self) -> float | None:
        """Returns the latest temperature in °C or None."""
        with self.status_lock:
            return self.latest_status.get("temperature")

    def get_flight_time(self) -> int | None:
        """Returns the latest flight time in seconds or None."""
        with self.status_lock:
            return self.latest_status.get("flight_time")

    def end_mqtt_connection(self):
        """Disconnects cleanly."""
        self.client.loop_stop()
        self.client.disconnect()
