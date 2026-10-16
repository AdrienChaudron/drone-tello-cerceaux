"""
test_flux_tello.py : affiche le flux video du Tello avec l'heure du PC au centieme, pour mesurer son retard.
Autonome (djitellopy + OpenCV seulement). Le drone NE DECOLLE PAS.

Test du chronometre : filmer avec le drone l'ecran qui affiche cette fenetre ; l'ecart entre l'heure en jaune
(maintenant) et celle visible DANS l'image filmee = retard camera -> affichage.
Le bandeau donne aussi le nombre de NOUVELLES images decodees par seconde (normal : ~25-30).

Usage : python test_flux_tello.py        (q ou ESC pour quitter)
"""
import time

import cv2
from djitellopy import Tello

tello = Tello()
tello.connect()
print("batterie :", tello.get_battery(), "%")
tello.streamon()
frame_read = tello.get_frame_read()

derniere, n_nouvelles, t_compte, debit = None, 0, time.time(), 0.0
t_keepalive = time.time()
try:
    while True:
        img = frame_read.frame
        if img is None:
            time.sleep(0.01)
            continue
        if img is not derniere:                      # nouvelle image decodee
            n_nouvelles += 1
            derniere = img
        maintenant = time.time()
        if maintenant - t_compte >= 1.0:
            debit, n_nouvelles, t_compte = n_nouvelles / (maintenant - t_compte), 0, maintenant
        if maintenant - t_keepalive > 10:            # le Tello coupe s'il ne recoit plus rien
            tello.send_keepalive()
            t_keepalive = maintenant

        vue = cv2.cvtColor(img, cv2.COLOR_RGB2BGR)   # djitellopy renvoie du RGB
        heure = time.strftime("%H:%M:%S") + f".{int(maintenant * 100) % 100:02d}"
        for couleur, ep in (((0, 0, 0), 8), ((0, 255, 255), 3)):
            cv2.putText(vue, heure, (vue.shape[1] - 340, 60), cv2.FONT_HERSHEY_SIMPLEX, 1.4, couleur, ep, cv2.LINE_AA)
        cv2.putText(vue, f"{debit:.0f} nouvelles images/s", (10, vue.shape[0] - 15), cv2.FONT_HERSHEY_SIMPLEX, 0.8,
                    (0, 255, 255), 2, cv2.LINE_AA)
        cv2.imshow("Flux Tello (q : quitter)", vue)
        if (cv2.waitKey(1) & 0xFF) in (ord("q"), 27):
            break
finally:
    cv2.destroyAllWindows()
    tello.streamoff()
    tello.end()
