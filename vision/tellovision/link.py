"""
link.py : liaison MQTT entre notre PC (vision) et le PC de controle du collegue.

    PC de controle  --tello/video-->        notre PC : image 480x360 JPEG + etat du drone a l'instant de l'image
    notre PC        --tello/vision/view, tello/vision/state--> IHM web (image annotee, etat de la vision)
L'ordre vers le PC de controle et ses mesures passent par SON interface (collegue/tello_nn/TelloInterface.py :
send_vision -> tello/vision/ordre, get_measures), pas par ce module.

Format d'une image (un message binaire) :
    [4 octets : taille N de l'en-tete, big-endian][en-tete JSON (N octets)][JPEG]
    en-tete = {"frame_id", "t" (s), "w", "h" (taille d'origine, 960x720), "yaw" (deg), "tof" (cm)}

Reception : on ne garde que la DERNIERE image (une seule case, pas de file d'attente) ; le decodage JPEG se fait
dans la boucle principale, pas dans la fonction de reception MQTT, pour ne jamais la bloquer.
"""

import json
import struct
import threading
import time

import cv2
import numpy as np
import paho.mqtt.client as mqtt
import yaml


# ------------------------------------------------------------------ #
# Format des messages
# ------------------------------------------------------------------ #
def encode_frame(header: dict, img_bgr, quality=90) -> bytes:
    ok, jpg = cv2.imencode(".jpg", img_bgr, [cv2.IMWRITE_JPEG_QUALITY, quality])
    if not ok:
        raise ValueError("encodage JPEG impossible")
    h = json.dumps(header).encode("utf-8")
    return struct.pack(">I", len(h)) + h + jpg.tobytes()


def split_frame(payload: bytes):
    """Message brut -> (en-tete dict, octets JPEG). Rapide : ne decode pas l'image."""
    n = struct.unpack(">I", payload[:4])[0]
    return json.loads(payload[4:4 + n].decode("utf-8")), payload[4 + n:]


def decode_jpeg(jpg: bytes):
    return cv2.imdecode(np.frombuffer(jpg, np.uint8), cv2.IMREAD_COLOR)


# ------------------------------------------------------------------ #
# Client MQTT de notre PC
# ------------------------------------------------------------------ #
class VisionLink:
    def __init__(self, cfg_path="configs/reseau.yaml", broker_ip=None, client_id=None):
        with open(cfg_path) as f:
            self.cfg = yaml.safe_load(f)
        if broker_ip:
            self.cfg["broker_ip"] = broker_ip
        if client_id:                       # un identifiant par programme : le broker ejecte les doublons
            self.cfg["client_id"] = client_id
        self.client = mqtt.Client(mqtt.CallbackAPIVersion.VERSION2, client_id=self.cfg["client_id"])
        if self.cfg.get("username"):
            self.client.username_pw_set(self.cfg["username"], self.cfg.get("password"))
        self.client.on_connect = self._on_connect
        self.client.on_message = self._on_message
        self._lock = threading.Lock()
        self._latest = None                     # (instant de reception, message brut) : une seule case
        self._event = threading.Event()
        self.received = self.dropped = 0
        self.connected = False

    def _on_connect(self, client, userdata, flags, reason_code, properties):
        self.connected = not reason_code.is_failure
        print(f"[vision] connexion au broker {self.cfg['broker_ip']} : {reason_code}")
        if self.connected:
            client.subscribe(self.cfg["topic_video"], qos=0)

    def _on_message(self, client, userdata, msg):
        with self._lock:                        # on remplace l'image precedente si elle n'a pas ete traitee
            if self._latest is not None:
                self.dropped += 1
            self._latest = (time.time(), msg.payload)
            self.received += 1
        self._event.set()

    def start(self):
        self.client.connect(self.cfg["broker_ip"], self.cfg["port"], keepalive=30)
        self.client.loop_start()

    def stop(self):
        self.client.disconnect()                # d'abord : le thread reseau s'arrete tout seul
        self.client.loop_stop()

    def peek_frame(self):
        """
        Derniere image recue SANS la retirer de la case (elle sera traitee au prochain get_frame) :
        (en-tete, image BGR) ou None si aucune image n'est arrivee depuis le dernier get_frame.
        """
        with self._lock:
            latest = self._latest
        if latest is None:
            return None
        header, jpg = split_frame(latest[1])
        return header, decode_jpeg(jpg)

    def get_frame(self, timeout=1.0):
        """Attend la prochaine image. Renvoie (en-tete, image BGR, instant de reception) ou None."""
        if not self._event.wait(timeout):
            return None
        with self._lock:
            t_rx, payload = self._latest
            self._latest = None
            self._event.clear()
        header, jpg = split_frame(payload)
        return header, decode_jpeg(jpg), t_rx

    # ---- IHM web : image annotee et etat de la vision (rien n'est attendu en retour) ----
    def publish_view(self, view, quality=75):
        """Image annotee (ellipse, centre, infos) en JPEG brut : image BGR, ou octets JPEG deja encodes."""
        topic = self.cfg.get("topic_view")
        if not topic:
            return
        if not isinstance(view, (bytes, bytearray)):
            ok, jpg = cv2.imencode(".jpg", view, [cv2.IMWRITE_JPEG_QUALITY, quality])
            if not ok:
                return
            view = jpg.tobytes()
        self.client.publish(topic, view, qos=0)

    def publish_state(self, state: dict):
        topic = self.cfg.get("topic_state")
        if topic:
            self.client.publish(topic, json.dumps(state), qos=0)
