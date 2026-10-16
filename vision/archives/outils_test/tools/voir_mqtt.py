"""
voir_mqtt.py : affiche l'image recue en MQTT (tello/video) avec la detection du cerceau (CNN E2), sans rien publier.
Pour verification. --sans-cnn : image brute seule (alors autonome : paho-mqtt + OpenCV + numpy).

Message tello/video : [4 octets : taille N de l'en-tete, big-endian][en-tete JSON (N octets)][JPEG]
Affiche la DERNIERE image arrivee (aucune file d'attente), avec son numero, le cap, la hauteur et la cadence.

Seule la DERNIERE image est traitee par le CNN (les autres sont sautees) : aucun retard ne s'accumule.

Usage : python tools/voir_mqtt.py                  (broker 192.168.20.1, avec CNN)
        python tools/voir_mqtt.py --sans-cnn       (image brute)
        python tools/voir_mqtt.py 127.0.0.1        (autre broker)
q ou ESC dans la fenetre pour quitter.
"""
import json
import os
import struct
import sys
import threading
import time

import cv2
import numpy as np
import paho.mqtt.client as mqtt

ARGS = [a for a in sys.argv[1:] if not a.startswith("--")]
AVEC_CNN = "--sans-cnn" not in sys.argv
BROKER = ARGS[0] if ARGS else "192.168.20.1"

det = None
if AVEC_CNN:                                       # CNN du projet (tellovision), charge une seule fois
    RACINE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    sys.path.insert(0, RACINE)
    os.chdir(RACINE)
    from tellovision.detector import HoopDetector, draw_detection
    print("Chargement du CNN...")
    det = HoopDetector(os.path.join(RACINE, "logs", "E3_segmentation480_couleur_0"))
PORT, USER, PASSWORD, TOPIC = 1883, "tello", "tello", "tello/video"

derniere = {"msg": None}
verrou = threading.Lock()
compte = {"recues": 0}


def on_connect(client, userdata, flags, reason_code, properties):
    print(f"connexion a {BROKER} : {reason_code}")
    client.subscribe(TOPIC, qos=0)


def on_message(client, userdata, msg):
    with verrou:                                   # on ne garde que la derniere image
        derniere["msg"] = msg.payload
        compte["recues"] += 1


client = mqtt.Client(mqtt.CallbackAPIVersion.VERSION2, client_id=f"voir_mqtt_{os.getpid()}")   # identifiant unique
client.username_pw_set(USER, PASSWORD)
client.on_connect, client.on_message = on_connect, on_message
client.connect(BROKER, PORT, keepalive=30)
client.loop_start()

fenetre = "Image recue en MQTT + CNN" if AVEC_CNN else "Image recue en MQTT (sans CNN)"
cv2.namedWindow(fenetre, cv2.WINDOW_AUTOSIZE)
cv2.imshow(fenetre, np.zeros((360, 480, 3), np.uint8))
t_prec, cadence = time.time(), 0.0
try:
    while True:
        with verrou:
            payload, derniere["msg"] = derniere["msg"], None
        if payload is not None:
            n = struct.unpack(">I", payload[:4])[0]
            entete = json.loads(payload[4:4 + n])
            img = cv2.imdecode(np.frombuffer(payload[4 + n:], np.uint8), cv2.IMREAD_COLOR)
            if img is not None:
                if det is not None:                # detection du cerceau sur cette image
                    t_cnn = time.time()
                    d = det(img, orig_size=(entete.get("w", 960), entete.get("h", 720)))
                    img = draw_detection(img, d)
                    ms_cnn = 1000 * (time.time() - t_cnn)
                maintenant = time.time()
                cadence = 0.9 * cadence + 0.1 / max(maintenant - t_prec, 1e-3)
                t_prec = maintenant
                cv2.rectangle(img, (0, img.shape[0] - 28), (img.shape[1], img.shape[0]), (0, 0, 0), -1)
                cv2.putText(img, f"#{entete.get('frame_id')}  {cadence:4.1f} i/s  cap {entete.get('yaw')}  "
                                 f"tof {entete.get('tof')}  recues {compte['recues']}"
                                 + (f"  CNN {ms_cnn:.0f} ms" if det is not None else ""),
                            (6, img.shape[0] - 8), cv2.FONT_HERSHEY_SIMPLEX, 0.55, (0, 255, 255), 1, cv2.LINE_AA)
                cv2.imshow(fenetre, img)
        if (cv2.waitKey(1) & 0xFF) in (ord("q"), 27):
            break
except KeyboardInterrupt:
    pass
finally:
    client.loop_stop()
    client.disconnect()
    cv2.destroyAllWindows()
    print(f"{compte['recues']} images recues")
