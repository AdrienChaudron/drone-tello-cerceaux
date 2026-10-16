"""
vision_node.py : programme principal de NOTRE PC pendant le vol.

    PC de controle --tello/video--> [derniere image] -> CNN E2 + pose -> ordre -> send_vision(...)
                                                                                  --tello/vision/ordre--> PC de controle

Notre PC fait la RECHERCHE du cerceau (paliers de cap, montee entre deux tours) et la MISE EN AXE ; le PC de
controle asservit le drone sur nos consignes et gere lui-meme l'AVANCE (axe Y). Le dialogue avec son PC passe par
SON interface (collegue/tello_nn/TelloInterface.py) : a chaque image traitee, send_vision(etat, present, delta_x,
delta_z, distance, r_yaw, r_z) (il le lit avec retrieve_vision()), et la hauteur du drone est lue avec
get_measures(Z). La video, elle, est recue par tellovision/link.py.
Etat interne (recherche, mise en axe) : tellovision/ordres.py ; reglages : configs/ordres.yaml.

Usage :
    python tools/vision_node.py                         # broker du collegue (configs/reseau.yaml)
    python tools/vision_node.py --broker 127.0.0.1      # test local avec tools/simulate_hil.py
    python tools/vision_node.py --no-window             # sans fenetre OpenCV (l'IHM web recoit toujours l'image)
    python tools/vision_node.py --sans-vue-brute        # sans la 2e fenetre (derniere image MQTT brute, sans CNN)
    python tools/vision_node.py --no-ihm                # ne rien publier pour l'IHM web (tello/vision/view, state)
    python tools/vision_node.py --no-commande           # TEST : vision et IHM seulement, aucune consigne envoyee

IHM web : chaque image annotee et l'etat de la vision sont servis en HTTP par ce programme :
http://<ce PC>:8080/video.mjpeg et /events (lus directement par la page web). L'etat est aussi publie sur MQTT
(tello/vision/state, JSON) ; l'IMAGE n'est PAS republiee en MQTT : elle chargerait la connexion qui recoit la video.
Sur l'image : le reticule blanc est le point vise "droit devant" (camera inclinee : au-dessus du centre de l'image),
le trait relie ce point au centre du cerceau detecte ; bandeau vert quand le cerceau est centre
(|delta_x| <= 40 px et |delta_z| <= 10 cm, a titre indicatif), rouge sombre sans cerceau (recherche).

Touches (fenetre) : m masque CNN, s photo, q / ESC quitter.
Journal : logs/vol/vision_<horodatage>.csv (detection, etat, consigne envoyee, temps de calcul).
"""

import argparse
import csv
import os
import socket
import sys
import time

os.environ.setdefault("QT_QPA_FONTDIR", "/usr/share/fonts/truetype/dejavu")

import cv2  # noqa: E402
import numpy as np  # noqa: E402

from tellovision.detector import HoopDetector, draw_detection  # noqa: E402
from tellovision.ihm_server import VisionWebServer  # noqa: E402
from tellovision.link import VisionLink  # noqa: E402
from tellovision.ordres import OrdreVision  # noqa: E402

BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(BASE_DIR, "collegue"))           # interface du PC de controle (code du collegue)
from lib.AxisName import Z  # noqa: E402
from lib.EtatVision import EtatVision  # noqa: E402
from tello_nn.TelloInterface import TelloInterface  # noqa: E402
from lib.MqttInterface import TelloMQTTInterface  # noqa: E402
OUT_DIR = os.path.join(BASE_DIR, "logs", "vol")


def overlay_mask(view, prob):
    heat = cv2.applyColorMap((cv2.resize(prob, (view.shape[1], view.shape[0])) * 255).astype(np.uint8),
                             cv2.COLORMAP_INFERNO)
    return cv2.addWeighted(view, 0.55, heat, 0.45, 0)


def phase(o):
    return o["etat"]


def draw_ordre(view, o, d, aim_px, scale, lines):
    """Reticule du point vise, trait vers le centre du cerceau, bandeau (vert si le cerceau est centre)."""
    h, w = view.shape[:2]
    k = min(1.0, w / 960.0)
    ax, ay = int(round(aim_px[0] / scale)), int(round(aim_px[1] / scale))
    cv2.drawMarker(view, (ax, ay), (255, 255, 255), cv2.MARKER_TILTED_CROSS, int(22 * k) + 6, 2, cv2.LINE_AA)
    if o["vu"] and d.center_px is not None:                 # trait vers le centre du cerceau detecte
        cx, cy = (d.center_px[0] + 0.5) / scale - 0.5, (d.center_px[1] + 0.5) / scale - 0.5
        cv2.line(view, (ax, ay), (int(cx), int(cy)), (255, 255, 255), 1, cv2.LINE_AA)
    centre = (o["present"] and o["delta_x"] is not None and o["delta_z"] is not None
              and abs(o["delta_x"]) <= 40 and abs(o["delta_z"]) <= 0.10)
    color = (0, 200, 0) if centre else ((0, 0, 0) if o["present"] else (0, 0, 120))
    step = max(14, int(26 * k))
    top = h - step * len(lines) - 6
    cv2.rectangle(view, (0, top), (w, h), color, -1)
    for i, t in enumerate(lines):
        cv2.putText(view, t, (6, top + step * (i + 1) - 4), cv2.FONT_HERSHEY_SIMPLEX, 0.6 * k + 0.05, (0, 255, 255),
                    1, cv2.LINE_AA)
    return view


def vision_state(header, d, o, z_cm, calc_ms, link, test):
    """Etat de la vision pour l'IHM web (tello/vision/state)."""
    # "commande" : pour les IHM qui l'affichent sans verifier qu'il existe (ancienne version du panneau Vision) :
    # X = decalage horizontal du cerceau (px), Y = distance (cm), Z = hauteur visee (cm), YAW = r_yaw
    vu3d = o["present"] and o["delta_z"] is not None
    z_vise = o["r_z"] if o["r_z"] is not None else (z_cm + 100.0 * o["delta_z"] if vu3d else z_cm)
    cmd = {"X": float(o["delta_x"]) if o["delta_x"] is not None else 0.0,
           "Y": round(100.0 * o["distance_m"], 1) if vu3d else 0.0,
           "Z": round(float(z_vise), 1), "YAW": float(o["r_yaw"])}
    st = {"frame_id": header.get("frame_id"), "t": header.get("t"), "phase": phase(o), "mode": "ordre",
          "present": bool(d.present), "p": round(float(d.p), 3), "ambigu": bool(d.ambiguous),
          "distance_m": None, "centre": None, "axe": None,
          "ordre": {k: o[k] for k in ("etat", "present", "delta_x", "delta_z", "distance_m", "r_yaw", "r_z")},
          "commande": cmd,
          "calcul_ms": round(float(calc_ms), 1), "recues": link.received, "sautees": link.dropped, "test": test}
    if d.present and d.center_drone is not None:
        a, b, c = (round(float(v), 3) for v in d.center_drone)
        st["distance_m"] = round(float(d.distance_m), 3)
        st["centre"] = {"avant": a, "droite": b, "haut": c}
    return st


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--run", default=os.path.join(BASE_DIR, "logs", "E3_segmentation480_couleur_0"))
    ap.add_argument("--reseau", default="configs/reseau.yaml")
    ap.add_argument("--ordres", default="configs/ordres.yaml")
    ap.add_argument("--broker", default=None, help="adresse du broker (remplace celle de reseau.yaml)")
    ap.add_argument("--no-window", action="store_true")
    ap.add_argument("--sans-vue-brute", action="store_true",
                    help="pas de 2e fenetre avec la derniere image MQTT brute (sans CNN)")
    ap.add_argument("--no-ihm", action="store_true", help="ne pas publier l'image et l'etat pour l'IHM web")
    ap.add_argument("--no-commande", action="store_true",
                    help="TEST : n'envoie AUCUNE consigne au PC de controle (vision et IHM seulement)")
    ap.add_argument("--ihm-port", type=int, default=8080, help="port HTTP de la video et de l'etat pour l'IHM web")
    args = ap.parse_args()
    os.chdir(BASE_DIR)
    os.makedirs(OUT_DIR, exist_ok=True)

    print("Chargement du reseau...")
    det = HoopDetector(args.run)
    ordres = OrdreVision.from_detector(det, args.ordres)
    # point vise "droit devant" (direction avant du drone) dans l'image 960x720 : reticule de l'IHM
    aim_px = det.project(det.to_drone.R.T @ np.array([1.0, 0.0, 0.0]))
    link = VisionLink(args.reseau, broker_ip=args.broker)
    tof_facteur = float(link.cfg.get("tof_entete_facteur", 1.0))   # hauteur de l'en-tete faussee (voir reseau.yaml)
    link.start()
    tello = TelloInterface(tello_hil_ip=link.cfg["broker_ip"])      # SON interface : consignes et mesures
    # identifiant MQTT UNIQUE : TelloInterface impose "tello_nn_controller" ; si un autre programme l'utilise aussi
    # (random_commands.py, exemple.py...), le broker ejecte l'un puis l'autre en boucle (reconnexions sans fin)
    tello._tello_hil = TelloMQTTInterface(broker_ip=link.cfg["broker_ip"],
                                          client_id=f"tello_vision_ordres_{socket.gethostname()}_{os.getpid()}")
    tello.start_communication()

    def hauteur_cm(header):
        """Hauteur du drone : mesure de sa boucle Z (get_measures), sinon celle de l'en-tete corrigee."""
        try:
            return float(tello.get_measures(Z))
        except (ValueError, TypeError):
            return float(header["tof"]) / tof_facteur
    web = None
    if not args.no_ihm:
        web = VisionWebServer(port=args.ihm_port)
        web.start()
    test_label = "[SANS COMMANDE] " if args.no_commande else ""
    if args.no_commande:
        print("MODE TEST : aucune consigne envoyee, vision et IHM seulement")
    print(f"Ordres par TelloInterface.send_vision ; images attendues sur {link.cfg['topic_video']} "
          f"({link.cfg['broker_ip']})...")

    log = open(os.path.join(OUT_DIR, f"vision_{int(time.time())}.csv"), "w", newline="")
    w = csv.writer(log)
    w.writerow(["frame_id", "t_img", "yaw", "tof", "vu", "p", "avant_m", "droite_m", "haut_m", "etat", "present",
                "delta_x", "delta_z", "distance_m", "r_yaw", "r_z", "hauteur_cm", "calcul_ms", "attente_ms", "perdues",
                "BsurA", "couverture", "rejet"])
    win = "Vision : cerceau + ordre"
    win_brute = "Image MQTT brute (sans CNN)"
    vue_brute = not args.no_window and not args.sans_vue_brute
    if not args.no_window:
        cv2.namedWindow(win, cv2.WINDOW_AUTOSIZE | cv2.WINDOW_GUI_NORMAL)
    if vue_brute:
        cv2.namedWindow(win_brute, cv2.WINDOW_AUTOSIZE | cv2.WINDOW_GUI_NORMAL)
    show_mask, t_hist, last_phase = False, [], None
    try:
        while True:
            got = link.get_frame(timeout=0.5)
            if got is None:
                if not args.no_window and (cv2.waitKey(30) & 0xFF) in (ord("q"), 27):
                    break
                continue
            header, img, t_rx = got
            if img is None:
                continue
            t0 = time.time()
            d = det(img, orig_size=(header.get("w", 960), header.get("h", 720)))
            z_cm = hauteur_cm(header)
            o = ordres.step(d, float(header["t"]), float(header["yaw"]), z_cm)
            rejet = ordres.rejet(d) if d.present else None   # ellipse pas credible : ignoree par les ordres
            ba = d.ellipse[3] / d.ellipse[2] if (d.ellipse is not None and d.ellipse[2] > 0) else None
            if not args.no_commande:
                tello.send_vision(etat=EtatVision[o["etat"]], present=o["present"], delta_x=o["delta_x"], delta_z=o["delta_z"],
                                  distance=o["distance_m"], r_yaw=o["r_yaw"], r_z=o["r_z"],
                                  frame_id=header.get("frame_id"), t=header.get("t"), p=o["p"])
            t_hist = (t_hist + [time.time() - t0])[-30:]

            ph = phase(o)
            if ph != last_phase:
                print(f"[{header.get('frame_id')}] {last_phase} -> {ph}")
                last_phase = ph
            calc_ms, wait_ms = 1000 * (time.time() - t0), 1000 * (t0 - t_rx)
            row = [header.get("frame_id"), header["t"], header["yaw"], header["tof"], int(o["vu"]), round(d.p, 3)]
            row += [round(float(v), 3) for v in d.center_drone] if d.center_drone is not None else ["", "", ""]
            row += [o["etat"], int(o["present"]), o["delta_x"], o["delta_z"], o["distance_m"], o["r_yaw"], o["r_z"],
                    round(z_cm, 1), round(calc_ms, 1), round(wait_ms, 1), link.dropped,
                    "" if ba is None else round(ba, 3), "" if d.couverture is None else round(d.couverture, 3),
                    rejet or ""]
            w.writerow(row)

            if args.no_window and args.no_ihm:
                continue
            view = overlay_mask(img, det.last_prob) if (show_mask and det.last_prob is not None) else img
            view = draw_detection(view, d)
            ms = 1000 * np.mean(t_hist)
            draw_ordre(view, o, d, aim_px, d.img_scale, [
                f"{test_label}{ph}   " + ("" if o["delta_x"] is None else f"dx {o['delta_x']:+d} px  ")
                + ("" if o["delta_z"] is None else
                   f"dz {100 * o['delta_z']:+.0f} cm  dist {o['distance_m']:.2f} m   ")
                + f"r_yaw {o['r_yaw']:+d} (cap {float(header['yaw']):+.0f})"
                + ("" if o["r_z"] is None else f"   r_z {o['r_z']} (h {z_cm:.0f})"),
                f"image #{header.get('frame_id')}   calcul {ms:.0f} ms   recues {link.received}  sautees {link.dropped}"
                + ("" if rejet is None else f"   ELLIPSE REJETEE ({rejet} : B/A {ba:.2f}, couverture {d.couverture:.2f})")])
            if not args.no_ihm:                             # IHM web : image annotee + etat (HTTP et MQTT)
                ok, jpg = cv2.imencode(".jpg", view, [cv2.IMWRITE_JPEG_QUALITY, 75])
                state = vision_state(header, d, o, z_cm, ms, link, test_label.strip())
                if ok:
                    web.publish_frame(jpg.tobytes())
                web.publish_state(state)
                link.publish_state(state)
            if not args.no_window:
                cv2.imshow(win, view)
            if vue_brute:
                # derniere image arrivee par MQTT pendant le traitement (sinon celle qui vient d'etre traitee) :
                # comparer son numero a celui de la fenetre CNN = retard du traitement sur la reception
                brute = link.peek_frame()
                h_b, img_b = brute if (brute is not None and brute[1] is not None) else (header, img)
                vb = img_b.copy()
                cv2.rectangle(vb, (0, vb.shape[0] - 30), (vb.shape[1], vb.shape[0]), (0, 0, 0), -1)
                cv2.putText(vb, f"MQTT brute  image #{h_b.get('frame_id')}  (CNN : #{header.get('frame_id')})",
                            (6, vb.shape[0] - 9), cv2.FONT_HERSHEY_SIMPLEX, 0.55, (0, 255, 255), 1, cv2.LINE_AA)
                cv2.imshow(win_brute, vb)
                k = cv2.waitKey(1) & 0xFF
                if k in (ord("q"), 27):
                    break
                elif k == ord("m"):
                    show_mask = not show_mask
                elif k == ord("s"):
                    path = os.path.join(OUT_DIR, f"photo_{int(time.time() * 1000)}.jpg")
                    cv2.imwrite(path, view)
                    print("photo :", path)
    except KeyboardInterrupt:
        print("\nInterrompu (Ctrl+C)")
    finally:
        tello.end_communication()
        link.stop()
        if web is not None:
            web.stop()
        log.close()
        cv2.destroyAllWindows()
        print(f"{link.received} images recues, {link.dropped} sautees (calcul trop lent). Journal : {OUT_DIR}/")


if __name__ == "__main__":
    main()
