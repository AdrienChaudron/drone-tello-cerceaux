import json
import logging
import math
import struct
import sys
import termios
import threading
import time
import tty
from pathlib import Path

import cv2

ROOT_DIR = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT_DIR))

from djitellopy import Tello
from lib.AxisName import YAW, X, Y, Z
from lib.MqttInterface import TelloMQTTInterface
from tello_hil.lib.Environment import Environment
from tello_hil.lib.EtatVision import EtatVision
from tello_hil.lib.goToPosition import go_to_position
from tello_hil.lib.TELLO import AXIS, EVT

VIDEO_TOPIC = "tello/video"  # images envoyees en continu au PC vision (via le broker MQTT de ce PC)
VIDEO_FPS = 15
TARGET_WIDTH = 640
TARGET_HEIGHT = 480
JPEG_QUALITY = 60  # Keeps packet size well under the ~65 KB UDP limit
AFFICHER_VIDEO = True

def loop_fetch_references(environment: Environment, tello):
    """
    Fetches command references and publishes drone status periodically.
    """
    control_vision_enabled = False

    while environment.get_tello_running_state():
        vision = environment.neural_network.retrieve_vision()
        if vision is not None:
            control_vision_enabled = True
            EVT.set_pv(vision["etat"], vision["present"], vision["delta_x"], vision["delta_z"], vision["distance"], vision["r_yaw"], vision["r_z"])

            match EVT.get_pv().get_state():
                case EtatVision.RECHERCHE:
                    AXIS[Y].set_reference(0)
                    AXIS[Z].CONTROLLING = True
                    AXIS[Z].set_reference(math.floor(EVT.get_pv().get_z_reference()))
                case EtatVision.MISE_EN_AXE:
                    AXIS[X].CONTROLLING = True
                    AXIS[X].set_reference(0)
                    AXIS[Y].set_reference(50)
                    AXIS[Z].CONTROLLING = True
                    AXIS[Z].set_reference(math.floor(AXIS[Z].get_nth_value(0) + 100 * EVT.get_pv().get_delta_z()))
                case EtatVision.TRAVERSEE:
                    AXIS[Y].set_reference(50)
                    AXIS[Z].CONTROLLING = False
                    AXIS[Z].set_reference(0)
                case EtatVision.PERDU:
                    AXIS[Y].set_reference(0)
                case _:
                    AXIS[X].CONTROLLING = False

            AXIS[YAW].set_reference(math.floor(EVT.get_pv().get_yaw_reference()))

        references = environment.neural_network.retrieve_command(block=True, timeout=0.1)
        if references is not None:
            if control_vision_enabled == False:
                AXIS[X].set_reference(references[X.name])
                AXIS[Y].set_reference(references[Y.name])
                AXIS[Z].set_reference(references[Z.name])
                AXIS[YAW].set_reference(references[YAW.name])

            if references[X.name] == -69 and references[Y.name] == -69 and references[Z.name] == -69 and references[YAW.name] == -69:
                EVT.remote_deadman = True

        time.sleep(EVT.T_sample)


def fetch_cam(environment: Environment, tello: Tello, frame_read):
    """
    Envoie en continu (sans demande) la derniere image du Tello au PC vision, sur MQTT (tello/video).
    Message = [4 octets : taille N de l'en-tete, big-endian][en-tete JSON (N octets)][JPEG 480x360]
    en-tete = {"frame_id", "t" (s), "w", "h" (taille d'origine), "yaw" (deg), "tof" (cm)}
    Le cap et la hauteur sont lus au moment de l'image : le PC vision en a besoin pour Z et YAW absolus.
    """
    frame_id = 0
    period = 1.0 / VIDEO_FPS
    last_time = time.time()
    while True:
        t_start = time.time()
        frame = frame_read.frame
        if frame is not None:
            h, w = frame.shape[:2]
            frame_bgr = cv2.cvtColor(frame, cv2.COLOR_RGB2BGR)

            small = cv2.resize(frame_bgr, (TARGET_WIDTH, TARGET_HEIGHT), interpolation=cv2.INTER_AREA)
            success, buffer = cv2.imencode(".jpg", small, [int(cv2.IMWRITE_JPEG_QUALITY), JPEG_QUALITY])
            now = time.time()

            if success and now - last_time >= period:
                last_time = now
                header = json.dumps({"frame_id": frame_id, "t": t_start, "w": w, "h": h,
                                     "yaw": tello.get_yaw(), "tof": tello.get_distance_tof()}).encode("utf-8")
                payload = struct.pack(">I", len(header)) + header + buffer.tobytes()
                environment.neural_network.client.publish(VIDEO_TOPIC, payload, qos=0)
                frame_id += 1

        time.sleep(EVT.T_sample)


if __name__ == "__main__":
    tello = Tello()
    tello.connect()
    Tello.LOGGER.setLevel(logging.ERROR)
    print("battery: " + str(tello.get_battery()) + "%")

    EVT.neural_network = TelloMQTTInterface(broker_ip="localhost")
    EVT.neural_network.init_mqtt_connection(subscribe_commands=True, subscribe_vision=True)

    old_termios_settings = None
    old_termios_settings = termios.tcgetattr(sys.stdin)
    tty.setcbreak(sys.stdin.fileno())

    AXIS[X]._logger.start()
    AXIS[Y]._logger.start()
    AXIS[Z]._logger.start()
    AXIS[YAW]._logger.start()

    time.sleep(1)
    tello.takeoff()
    tello.streamon()
    fr = tello.get_frame_read()
    time.sleep(3)

    EVT.set_initial_tof(tello.get_distance_tof())
    EVT.set_tello_running_state(True)
    mqtt_worker_thread = threading.Thread(target=loop_fetch_references, args=(EVT, tello), daemon=True)
    mqtt_worker_thread.start()
    cam_worker_thread = threading.Thread(target=fetch_cam, args=(EVT, tello, fr), daemon=True)
    cam_worker_thread.start()

    print(EVT)

    go_to_position(tello)

    AXIS[X]._logger.stop()
    AXIS[Y]._logger.stop()
    AXIS[Z]._logger.stop()
    AXIS[YAW]._logger.stop()

    time.sleep(2)

    EVT.neural_network.end_mqtt_connection()

    tello.land()
