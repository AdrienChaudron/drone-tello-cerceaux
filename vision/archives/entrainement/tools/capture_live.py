import os
import time

os.environ.setdefault("QT_QPA_FONTDIR", "/usr/share/fonts/truetype/dejavu")
import cv2  # noqa: E402
from djitellopy import Tello  # noqa: E402

BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))  # racine du projet
CAPTURE_DIR = os.path.join(BASE_DIR, "captures")
os.makedirs(CAPTURE_DIR, exist_ok=True)
print("Images enregistrées dans :", CAPTURE_DIR)

tello = Tello()
tello.connect()
print("battery: " + str(tello.get_battery()) + "%")
#tello.set_video_resolution(tello.RESOLUTION_480P)
#tello.set_video_fps(Tello.FPS_30)
#tello.set_video_bitrate(Tello.BITRATE_2MBPS)
tello.streamon()
print("Ouverture du flux video (port UDP 11111)... si ca bloque ici : Wi-Fi ou port deja utilise")
frame_read = tello.get_frame_read()
print("Flux video ouvert")
time.sleep(2)  # laisse le flux démarrer

img_id = 0
last_save_time = 0

try:
    while True:
        frame = frame_read.frame
        if frame is not None:
            frame_bgr= cv2.cvtColor(frame, cv2.COLOR_RGB2BGR)
            cv2.imshow("Tello Live Camera", frame_bgr)

            now = time.time()
            if now - last_save_time >= 0.2:  # 5 images par seconde
                filename = os.path.join(CAPTURE_DIR, f"frame_{img_id:04d}_{int(now*1000)}.jpg")
                cv2.imwrite(filename, frame_bgr)
                img_id += 1
                last_save_time = now

        # Appuie sur 'q' dans la fenêtre vidéo pour quitter
        if cv2.waitKey(1) & 0xFF == ord('q'):
            break
finally:
    tello.streamoff()
    tello.end()
    cv2.destroyAllWindows()
    print(f"{img_id} images enregistrées dans {CAPTURE_DIR}")