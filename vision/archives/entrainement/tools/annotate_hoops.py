"""
annotate_hoops.py
Annotation des cerceaux par ELLIPSE (centre, grand axe, petit axe, inclinaison).

    <data>/hoop/*.jpg|png      -> vous ajustez une ellipse sur l'anneau
    <data>/no_hoop/*.jpg|png   -> etiquetees automatiquement "absent"
    <data>/inbox/*.jpg|png     -> (mode --inbox) images non triees : on trie ET on annote en une passe

Sortie : <data>/annotations.csv
    file, present, x1, y1, x2, y2, img_w, img_h, ecx, ecy, ea, eb, eangle
    ecx, ecy : centre (px) ; ea >= eb : longueurs COMPLETES du grand et du petit axe (px) ;
    eangle : inclinaison du grand axe en degres, dans [0, 180) (0 = horizontal, sens horaire a l'ecran).
    x1..y2 : boite englobant l'ellipse, calculee automatiquement (compatibilite).
    partial = 1 : cerceau present mais reduit a un arc (une "corde") : ellipse non annotee.
L'ellipse est "amodale" : elle decrit le cerceau entier, meme la partie hors de l'image
(une marge grise entoure l'image pour cela).

Souris :
    clic sur l'anneau              ajoute un point ; des 5 points l'ellipse est calculee (cv2.fitEllipse)
    clic droit                     retire le dernier point
    glisser l'interieur            deplace toute l'ellipse
    glisser une poignee orange     extremite du grand axe : taille + rotation
    glisser une poignee cyan       extremite du petit axe : aplatissement
    molette                        agrandir / reduire
Clavier :
    fleches                        deplacer finement          u / o     tourner de -2 / +2 degres
    + / -                          agrandir / reduire          [ / ]     petit axe -3 % / +3 %
    p                              reprendre l'ellipse de l'image precedente (puis ajuster)
    ENTREE                         valider et passer a l'image suivante
    r                              tout effacer
    x                              pas de cerceau sur cette image (present = 0)
    c                              cerceau present mais seul un arc est visible : ellipse non annotee
    d                              image inutilisable (mode --inbox) : deplacee dans rejected/
    s                              passer sans modifier
    ESC                            quitter (tout ce qui est valide est deja sauvegarde)

Usage :
    python tools/annotate_hoops.py                   # annoter les nouvelles images de hoop/
    python tools/annotate_hoops.py --inbox           # trier + annoter captures/inbox/
    python tools/annotate_hoops.py --inbox --step 2  # une image sur deux (rafales a 5 i/s)
    python tools/annotate_hoops.py --to-ellipse      # convertir les anciennes boites en ellipses
    python tools/annotate_hoops.py --files liste.txt # revoir les images listees (une par ligne, ex. no_hoop/xxx.jpg) ;
                                                     # elles sont rangees dans hoop/ ou no_hoop/ selon la touche
    python tools/annotate_hoops.py --review          # repasser sur TOUS les cerceaux deja annotes
    python tools/annotate_hoops.py --review --unadjusted   # seulement les ellipses non inclinees (0/90 deg)
"""

import argparse
import csv
import glob
import math
import os
import shutil

import cv2
import numpy as np

FIELDS = ["file", "present", "x1", "y1", "x2", "y2", "img_w", "img_h", "ecx", "ecy", "ea", "eb", "eangle", "partial"]
IMG_EXTS = ("*.jpg", "*.jpeg", "*.png")
MAX_WIN = (1300, 850)   # taille max de la fenetre (image + marges), en px ecran
GREY = (110, 110, 110)
HANDLE_PX = 11          # rayon de saisie des poignees, en px ecran

# codes des fleches selon le backend d'affichage d'OpenCV (GTK, Windows, Qt sous Linux)
KEY_LEFT = (65361, 2424832, 0x01000012)
KEY_UP = (65362, 2490368, 0x01000013)
KEY_RIGHT = (65363, 2555904, 0x01000014)
KEY_DOWN = (65364, 2621440, 0x01000015)


# ------------------------------------------------------------------ #
# Geometrie de l'ellipse : (cx, cy, A, B, theta) avec A, B demi-axes, theta en degres
# ------------------------------------------------------------------ #
def normalize(e):
    cx, cy, A, B, th = e
    A, B = abs(A), abs(B)
    if B > A:
        A, B, th = B, A, th + 90
    return cx, cy, A, B, th % 180


def ellipse_bbox(e):
    cx, cy, A, B, th = e
    t = math.radians(th)
    hw = math.sqrt((A * math.cos(t)) ** 2 + (B * math.sin(t)) ** 2)
    hh = math.sqrt((A * math.sin(t)) ** 2 + (B * math.cos(t)) ** 2)
    return cx - hw, cy - hh, cx + hw, cy + hh


def fit_points(pts):
    (cx, cy), (w, h), th = cv2.fitEllipse(np.array(pts, np.float32))
    return normalize((cx, cy, w / 2, h / 2, th))


def handles(e):
    """Poignees : centre, 2 extremites du grand axe, 2 du petit axe."""
    cx, cy, A, B, th = e
    t = math.radians(th)
    ux, uy = math.cos(t), math.sin(t)          # direction du grand axe
    vx, vy = -uy, ux                           # direction du petit axe
    return {"center": (cx, cy),
            "major1": (cx + A * ux, cy + A * uy), "major2": (cx - A * ux, cy - A * uy),
            "minor1": (cx + B * vx, cy + B * vy), "minor2": (cx - B * vx, cy - B * vy)}


def inside(e, x, y, r=0.8):
    cx, cy, A, B, th = e
    t = math.radians(th)
    dx, dy = x - cx, y - cy
    u = dx * math.cos(t) + dy * math.sin(t)
    v = -dx * math.sin(t) + dy * math.cos(t)
    return (u / max(A, 1e-6)) ** 2 + (v / max(B, 1e-6)) ** 2 < r * r


def row_ellipse(row):
    """Ellipse d'une ligne CSV : l'ellipse annotee, ou a defaut celle inscrite dans l'ancienne boite."""
    if row.get("ea"):
        return (float(row["ecx"]), float(row["ecy"]), float(row["ea"]) / 2, float(row["eb"]) / 2,
                float(row["eangle"]))
    x1, y1, x2, y2 = (float(row[k]) for k in ("x1", "y1", "x2", "y2"))
    return normalize(((x1 + x2) / 2, (y1 + y2) / 2, (x2 - x1) / 2, (y2 - y1) / 2, 0.0))


# ------------------------------------------------------------------ #
# CSV
# ------------------------------------------------------------------ #
def list_images(folder):
    return sorted(p for ext in IMG_EXTS for p in glob.glob(os.path.join(folder, ext)))


def load_rows(csv_path):
    if not os.path.exists(csv_path):
        return {}
    with open(csv_path, newline="") as f:
        return {row["file"]: row for row in csv.DictReader(f)}


def save_rows(csv_path, rows):
    """Reecrit tout le CSV via un fichier temporaire (les colonnes absentes restent vides)."""
    tmp = csv_path + ".tmp"
    with open(tmp, "w", newline="") as f:
        w = csv.DictWriter(f, fieldnames=FIELDS, restval="", extrasaction="ignore")
        w.writeheader()
        w.writerows(rows.values())
    os.replace(tmp, csv_path)


# ------------------------------------------------------------------ #
# Programme
# ------------------------------------------------------------------ #
def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--data", default="captures")
    ap.add_argument("--margin", type=float, default=0.35,
                    help="marge grise autour de l'image, en fraction de sa taille")
    ap.add_argument("--inbox", action="store_true",
                    help="trier et annoter les images non triees de <data>/inbox/")
    ap.add_argument("--step", type=int, default=1,
                    help="(--inbox) ne presenter qu'une image sur N ; les autres restent dans inbox/")
    ap.add_argument("--to-ellipse", action="store_true",
                    help="reprendre les cerceaux annotes en boite (sans ellipse)")
    ap.add_argument("--review", action="store_true",
                    help="repasser sur les cerceaux deja annotes (ellipse actuelle chargee, a ajuster)")
    ap.add_argument("--unadjusted", action="store_true",
                    help="(--review) seulement les ellipses d'angle 0 ou 90 deg, jamais inclinees")
    ap.add_argument("--files", help="fichier texte : images a revoir (chemins relatifs a --data), une par ligne")
    args = ap.parse_args()

    csv_path = os.path.join(args.data, "annotations.csv")
    rows = load_rows(csv_path)
    backup = csv_path + ".avant_ellipses"
    if rows and not os.path.exists(backup):
        shutil.copy(csv_path, backup)
        print("Sauvegarde du CSV actuel :", backup)

    def rel(p):
        return os.path.relpath(p, args.data).replace("\\", "/")

    # ---- negatifs : etiquetage automatique ---- #
    n_neg = 0
    for p in list_images(os.path.join(args.data, "no_hoop")):
        if rel(p) in rows:
            continue
        h, w = cv2.imread(p).shape[:2]
        rows[rel(p)] = dict(zip(FIELDS, [rel(p), 0, 0, 0, 0, 0, w, h]))
        n_neg += 1
    if n_neg:
        save_rows(csv_path, rows)
        print(f"{n_neg} images no_hoop etiquetees automatiquement (absent).")

    # ---- images a traiter ---- #
    if args.files:
        names = [l.strip() for l in open(args.files) if l.strip() and not l.startswith("#")]
        todo = [os.path.join(args.data, f) for f in names if os.path.exists(os.path.join(args.data, f))]
        print(f"{len(todo)} images a revoir (ellipse ou c -> hoop/, x -> no_hoop/).")
    elif args.inbox:
        todo = list_images(os.path.join(args.data, "inbox"))[::max(args.step, 1)]
        print(f"{len(todo)} images de inbox/ a trier (ellipse -> hoop/, x -> no_hoop/, d -> rejected/).")
    elif args.review:
        def unadjusted(r):
            a = float(r["eangle"]) % 90 if r.get("ea") else 0.0
            return min(a, 90 - a) < 0.5
        todo = [os.path.join(args.data, f) for f, r in rows.items()
                if r["present"] == "1" and (not args.unadjusted or unadjusted(r))]
        print(f"{len(todo)} cerceaux a revoir (ellipse actuelle chargee ; ENTREE si elle convient).")
    elif args.to_ellipse:
        todo = [os.path.join(args.data, f) for f, r in rows.items()
                if r["present"] == "1" and not r.get("ea") and r.get("partial") != "1"]
        print(f"{len(todo)} cerceaux annotes en boite a convertir (ellipse de depart = boite).")
    else:
        todo = [p for p in list_images(os.path.join(args.data, "hoop")) if rel(p) not in rows]
        print(f"{len(todo)} images de cerceau a annoter.")

    def store(p, e, w, h, partial=False):
        """e = ellipse (image px) ou None si absent / corde. En mode inbox, deplace l'image avant."""
        if args.inbox or args.files:
            dest = os.path.join(args.data, "hoop" if (e or partial) else "no_hoop", os.path.basename(p))
            rows.pop(rel(p), None)               # l'ancienne ligne (ancien dossier) est remplacee
            if os.path.abspath(dest) != os.path.abspath(p):
                shutil.move(p, dest)
            p = dest
        if partial:
            rows[rel(p)] = dict(zip(FIELDS, [rel(p), 1, "", "", "", "", w, h, "", "", "", "", "", 1]))
        elif e is None:
            rows[rel(p)] = dict(zip(FIELDS, [rel(p), 0, 0, 0, 0, 0, w, h]))
        else:
            cx, cy, A, B, th = normalize(e)
            x1, y1, x2, y2 = ellipse_bbox((cx, cy, A, B, th))
            rows[rel(p)] = dict(zip(FIELDS, [rel(p), 1] + [f"{v:.1f}" for v in (x1, y1, x2, y2)] + [w, h] +
                                    [f"{v:.1f}" for v in (cx, cy, 2 * A, 2 * B, th)]))
        save_rows(csv_path, rows)

    # etat de l'edition, en coordonnees IMAGE
    S = {"pts": [], "e": None, "drag": None, "press": None, "e0": None, "moved": False}
    view = {"scale": 1.0, "px": 0, "py": 0}

    def to_img(x, y):
        return (x - view["px"]) / view["scale"], (y - view["py"]) / view["scale"]

    def to_scr(x, y):
        return int(round(x * view["scale"] + view["px"])), int(round(y * view["scale"] + view["py"]))

    def on_mouse(event, x, y, flags, _):
        ix, iy = to_img(x, y)
        e = S["e"]
        if event == cv2.EVENT_LBUTTONDOWN:
            S["press"], S["moved"], S["e0"] = (ix, iy), False, e
            S["drag"] = None
            if e is not None:
                for name, (hx, hy) in handles(e).items():
                    sx, sy = to_scr(hx, hy)
                    if (sx - x) ** 2 + (sy - y) ** 2 <= HANDLE_PX ** 2:
                        S["drag"] = name
                        break
                if S["drag"] is None and inside(e, ix, iy):
                    S["drag"] = "body"
        elif event == cv2.EVENT_MOUSEMOVE and S["press"] is not None and S["drag"] is not None:
            S["moved"] = True
            cx, cy, A, B, th = S["e0"]
            if S["drag"] in ("body", "center"):
                S["e"] = (cx + ix - S["press"][0], cy + iy - S["press"][1], A, B, th)
            elif S["drag"].startswith("major"):
                sign = 1 if S["drag"] == "major1" else -1
                dx, dy = (ix - cx) * sign, (iy - cy) * sign
                S["e"] = (cx, cy, math.hypot(dx, dy), B, math.degrees(math.atan2(dy, dx)))
            else:   # minor
                S["e"] = (cx, cy, A, math.hypot(ix - cx, iy - cy), th)
            S["pts"] = []            # ajustement manuel : les points ne decrivent plus l'ellipse
        elif event == cv2.EVENT_LBUTTONUP and S["press"] is not None:
            if not S["moved"] and S["drag"] in (None, "body"):
                S["pts"].append((ix, iy))           # simple clic : nouveau point sur l'anneau
                if len(S["pts"]) >= 5:
                    S["e"] = fit_points(S["pts"])
            elif S["e"] is not None:
                S["e"] = normalize(S["e"])
            S["press"], S["drag"] = None, None
        elif event == cv2.EVENT_RBUTTONDOWN and S["pts"]:
            S["pts"].pop()
            S["e"] = fit_points(S["pts"]) if len(S["pts"]) >= 5 else S["e"]
        elif event == cv2.EVENT_MOUSEWHEEL and e is not None:
            f = 1.03 if cv2.getMouseWheelDelta(flags) > 0 else 1 / 1.03
            S["e"] = (e[0], e[1], e[2] * f, e[3] * f, e[4])

    win = "Annotation cerceau (ellipse)"
    # GUI_NORMAL : sans barre d'outils Qt, sinon Qt capture le clic droit (menu) et la molette (zoom)
    cv2.namedWindow(win, cv2.WINDOW_AUTOSIZE | cv2.WINDOW_GUI_NORMAL)
    cv2.setMouseCallback(win, on_mouse)

    prev_e = None
    counts = {"hoop": 0, "no_hoop": 0, "rejected": 0}
    for i, p in enumerate(todo, 1):
        img = cv2.imread(p)
        h, w = img.shape[:2]
        k_m = 1 + 2 * args.margin
        scale = min(1.0, MAX_WIN[0] / (w * k_m), MAX_WIN[1] / (h * k_m))
        dw, dh = int(w * scale), int(h * scale)
        view.update(scale=scale, px=int(dw * args.margin), py=int(dh * args.margin))
        base = cv2.copyMakeBorder(cv2.resize(img, (dw, dh)), view["py"], view["py"], view["px"], view["px"],
                                  cv2.BORDER_CONSTANT, value=GREY)
        cv2.rectangle(base, (view["px"] - 1, view["py"] - 1), (view["px"] + dw, view["py"] + dh),
                      (255, 255, 255), 1)

        old = rows.get(rel(p))
        start = (row_ellipse(old) if (old is not None and old["present"] == "1" and old.get("partial") != "1")
                 else None)
        S.update(pts=[], e=start, drag=None, press=None, e0=None, moved=False)
        step_px = 2 / scale                          # deplacement clavier : 2 px ecran

        while True:
            canvas = base.copy()
            e = S["e"]
            if e is not None:
                cx, cy, A, B, th = e
                c = to_scr(cx, cy)
                axes = (max(int(A * scale), 1), max(int(B * scale), 1))
                x1, y1, x2, y2 = ellipse_bbox(e)
                cv2.rectangle(canvas, to_scr(x1, y1), to_scr(x2, y2), (90, 90, 90), 1)
                cv2.ellipse(canvas, c, axes, th, 0, 360, (0, 255, 0), 2)
                hs = handles(e)
                cv2.line(canvas, to_scr(*hs["major1"]), to_scr(*hs["major2"]), (0, 165, 255), 1)
                cv2.line(canvas, to_scr(*hs["minor1"]), to_scr(*hs["minor2"]), (255, 255, 0), 1)
                cv2.rectangle(canvas, (c[0] - 4, c[1] - 4), (c[0] + 4, c[1] + 4), (0, 255, 0), -1)
                for name in ("major1", "major2"):
                    cv2.circle(canvas, to_scr(*hs[name]), 6, (0, 165, 255), -1)
                for name in ("minor1", "minor2"):
                    cv2.circle(canvas, to_scr(*hs[name]), 6, (255, 255, 0), -1)
            for (x, y) in S["pts"]:
                cv2.circle(canvas, to_scr(x, y), 4, (0, 0, 255), -1)
            cv2.putText(canvas, f"{i}/{len(todo)}  clic=point  glisser=deplacer  poignees=taille/rotation  "
                                f"molette=zoom  u/o=tourner", (10, 20), cv2.FONT_HERSHEY_SIMPLEX, 0.45,
                        (0, 255, 255), 1)
            status = (f"points: {len(S['pts'])}" + ("" if e is not None else " (5 min.)") +
                      "   ENTREE=valider  p=precedente  x=absent  c=corde  " + ("d=rejeter  " if args.inbox else "") +
                      "r=effacer  s=passer  ESC=quitter")
            cv2.putText(canvas, status, (10, 42), cv2.FONT_HERSHEY_SIMPLEX, 0.45, (0, 255, 255), 1)
            cv2.imshow(win, canvas)
            k = cv2.waitKeyEx(20)
            if k == -1:
                continue
            c = k & 0xFF if k < 256 else None

            if e is not None and k in KEY_LEFT + KEY_RIGHT + KEY_UP + KEY_DOWN:
                dx = -step_px if k in KEY_LEFT else step_px if k in KEY_RIGHT else 0
                dy = -step_px if k in KEY_UP else step_px if k in KEY_DOWN else 0
                S["e"] = (e[0] + dx, e[1] + dy, e[2], e[3], e[4])
            elif e is not None and c in (ord("u"), ord("o")):
                S["e"] = normalize((e[0], e[1], e[2], e[3], e[4] + (-2 if c == ord("u") else 2)))
            elif e is not None and c in (ord("+"), ord("="), ord("-")):
                f = 1.03 if c != ord("-") else 1 / 1.03
                S["e"] = (e[0], e[1], e[2] * f, e[3] * f, e[4])
            elif e is not None and c in (ord("["), ord("]")):
                S["e"] = normalize((e[0], e[1], e[2], e[3] * (0.97 if c == ord("[") else 1.03), e[4]))
            elif c in (13, 10):                                   # ENTREE (pas ESPACE : trop facile a presser)
                if e is not None:
                    x1, y1, x2, y2 = ellipse_bbox(e)
                    if x2 > 0 and y2 > 0 and x1 < w and y1 < h and e[3] > 1:
                        prev_e = normalize(e)
                        store(p, prev_e, w, h)
                        counts["hoop"] += 1
                        break
                print("Placez d'abord une ellipse qui recouvre l'image (5 clics sur l'anneau, ou 'p'), "
                      "ou 'x' si le cerceau est absent.")
            elif c == ord("p"):
                if prev_e is not None:
                    S.update(e=prev_e, pts=[])
                else:
                    print("Pas encore d'ellipse precedente.")
            elif c == ord("r"):
                S.update(e=None, pts=[])
            elif c == ord("x"):
                store(p, None, w, h)
                counts["no_hoop"] += 1
                break
            elif c == ord("c"):
                store(p, None, w, h, partial=True)
                counts["hoop"] += 1
                break
            elif c == ord("d") and args.inbox:
                os.makedirs(os.path.join(args.data, "rejected"), exist_ok=True)
                shutil.move(p, os.path.join(args.data, "rejected", os.path.basename(p)))
                counts["rejected"] += 1
                break
            elif c == ord("s"):
                break
            elif c == 27:
                cv2.destroyAllWindows()
                print(f"Interrompu ({counts}). Annotations dans", csv_path)
                return

    cv2.destroyAllWindows()
    print(f"Termine ({counts}). Annotations dans", csv_path)


if __name__ == "__main__":
    main()
