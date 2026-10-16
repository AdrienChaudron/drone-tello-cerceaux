"""
annotate_hoops.py
Annotation des images du dataset (produit par Tello_capture_dataset.py / Tello_CL_Z_photo.py).

    dataset/hoop/*.jpg      -> vous dessinez UNE boite englobante autour du cerceau
    dataset/no_hoop/*.jpg   -> etiquetees automatiquement "absent" (aucune boite a dessiner)

Sortie : dataset/annotations.csv
    file, present, x1, y1, x2, y2, img_w, img_h      (coordonnees en pixels de l'image d'origine)

Commandes (fenetre d'annotation) :
    clic gauche + glisser   dessiner la boite (reprendre pour la corriger)
    ENTREE ou ESPACE        valider et passer a l'image suivante
    r                       effacer la boite
    x                       le cerceau n'est PAS visible sur cette image (present = 0)
    s                       passer sans enregistrer
    ESC                     quitter (la progression est sauvegardee, on reprend ou on s'est arrete)

Conseil : englobez le cadre EXTERIEUR du cerceau, de facon coherente d'une image a l'autre.
Si le cerceau est coupe par le bord de l'image, tracez la boite jusqu'au bord.

Usage :  python annotate_hoops.py --data dataset
"""

import argparse
import csv
import glob
import os

import cv2


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--data", default="dataset")
    args = ap.parse_args()

    csv_path = "captures/"
    done = set()
    new_file = not os.path.exists(csv_path)
    if not new_file:
        with open(csv_path, newline="") as f:
            done = {row["file"] for row in csv.DictReader(f)}

    f_out = open(csv_path, "a", newline="")
    writer = csv.writer(f_out)
    if new_file:
        writer.writerow(["file", "pcv2resent", "x1", "y1", "x2", "y2", "img_w", "img_h"])

    # ---- negatifs : etiquetage automatique ---- #
    n_neg = 0
    for p in sorted(glob.glob(os.path.join(args.data, "no_hoop", "*.jpg"))):
        rel = os.path.relpath(p, args.data).replace("\\", "/")
        if rel in done:
            continue
        h, w = cv2.imread(p).shape[:2]
        writer.writerow([rel, 0, 0, 0, 0, 0, w, h])
        done.add(rel)
        n_neg += 1
    f_out.flush()
    if n_neg:
        print(f"{n_neg} images no_hoop etiquetees automatiquement (absent).")

    # ---- images de cerceau : annotation manuelle ---- #
    todo = [p for p in sorted(glob.glob(os.path.join(args.data, "hoop", "*.jpg")))
            if os.path.relpath(p, args.data).replace("\\", "/") not in done]
    print(f"{len(todo)} images de cerceau a annoter.")

    state = {"p1": None, "p2": None, "drag": False}

    def on_mouse(event, x, y, flags, s):
        if event == cv2.EVENT_LBUTTONDOWN:
            s["p1"], s["p2"], s["drag"] = (x, y), (x, y), True
        elif event == cv2.EVENT_MOUSEMOVE and s["drag"]:
            s["p2"] = (x, y)
        elif event == cv2.EVENT_LBUTTONUP:
            s["p2"], s["drag"] = (x, y), False

    win = "Annotation cerceau"
    cv2.namedWindow(win)
    cv2.setMouseCallback(win, on_mouse, state)

    quit_all = False
    for i, p in enumerate(todo, 1):
        img = cv2.imread(p)
        h, w = img.shape[:2]
        scale = min(1.0, 1000 / w, 700 / h)
        disp = cv2.resize(img, (int(w * scale), int(h * scale))) if scale < 1 else img
        rel = os.path.relpath(p, args.data).replace("\\", "/")
        state.update(p1=None, p2=None, drag=False)

        while True:
            canvas = disp.copy()
            if state["p1"] and state["p2"]:
                cv2.rectangle(canvas, state["p1"], state["p2"], (0, 255, 0), 2)
                cx = (state["p1"][0] + state["p2"][0]) // 2
                cy = (state["p1"][1] + state["p2"][1]) // 2
                cv2.drawMarker(canvas, (cx, cy), (0, 255, 0), cv2.MARKER_CROSS, 12, 1)
            cv2.putText(canvas, f"{i}/{len(todo)}  ENTREE=valider  r=effacer  x=absent  s=passer  ESC=quitter",
                        (10, 22), cv2.FONT_HERSHEY_SIMPLEX, 0.55, (0, 255, 255), 2)
            cv2.imshow(win, canvas)
            k = cv2.waitKey(20) & 0xFF

            if k in (13, 32):                                    # ENTREE / ESPACE
                if state["p1"] and state["p2"] and not state["drag"]:
                    xs = sorted([state["p1"][0], state["p2"][0]])
                    ys = sorted([state["p1"][1], state["p2"][1]])
                    if xs[1] - xs[0] > 4 and ys[1] - ys[0] > 4:
                        x1, x2 = [min(max(v / scale, 0), w) for v in xs]
                        y1, y2 = [min(max(v / scale, 0), h) for v in ys]
                        writer.writerow([rel, 1, f"{x1:.1f}", f"{y1:.1f}", f"{x2:.1f}", f"{y2:.1f}", w, h])
                        f_out.flush()
                        break
                print("Dessinez d'abord une boite (au moins 5 px), ou 'x' si le cerceau est absent.")
            elif k == ord("r"):
                state.update(p1=None, p2=None)
            elif k == ord("x"):
                writer.writerow([rel, 0, 0, 0, 0, 0, w, h])
                f_out.flush()
                break
            elif k == ord("s"):
                break
            elif k == 27:
                quit_all = True
                break
        if quit_all:
            break

    f_out.close()
    cv2.destroyAllWindows()
    print("Termine. Annotations dans", csv_path)


if __name__ == "__main__":
    main()
