"""Figures du rapport E3. Usage : venv/bin/python figures.py <dossier out> (depuis ~/Documents/tello)."""
import json
import os
import pickle
import random
import sys

import cv2
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt  # noqa: E402
import numpy as np  # noqa: E402
import torch  # noqa: E402
import yaml  # noqa: E402

sys.path.insert(0, os.getcwd())
from tellovision import data, seg  # noqa: E402
from tellovision.main import load_checkpoint  # noqa: E402
from tellovision.pose import PoseEstimator, circle_poses  # noqa: E402

OUT = sys.argv[1]
SCR = os.path.dirname(os.path.dirname(OUT.rstrip("/")))
R = json.load(open(os.path.join(OUT, "resultats.json")))
ROWS = pickle.load(open(os.path.join(OUT, "rows.pkl"), "rb"))
plt.rcParams.update({"font.size": 9, "axes.spines.top": False, "axes.spines.right": False})
C3, C2 = "#1f6fb4", "#9a9a9a"


def save(fig, name):
    fig.savefig(os.path.join(OUT, name), dpi=170, bbox_inches="tight")
    plt.close(fig)


def rgb(img):
    return cv2.cvtColor(img, cv2.COLOR_BGR2RGB)


def draw_e(img, e, col, t=3):
    if e is None:
        return img
    cv2.ellipse(img, (int(e[0]), int(e[1])), (int(e[2]), int(e[3])), e[4], 0, 360, col, t, cv2.LINE_AA)
    return img


cfg0 = yaml.safe_load(open("configs/E3_segmentation480_couleur.yaml"))
train_ds, valid_ds = data.get_datasets(cfg0)
VA = valid_ds.samples
cage = [s for s in VA if s["ellipse"] is not None and not os.path.basename(s["file"]).split("_")[2].startswith("17905")]
ex = sorted(cage, key=lambda s: -s["ellipse"][2])[len(cage) // 3]       # cerceau de cage, taille moyenne

# 1. masque cible
img = cv2.imread(ex["path"])
tgt = seg.ring_target(ex["ellipse"], 960, 720, 240, 180, 0.04)
fig, ax = plt.subplots(1, 2, figsize=(8, 3))
ax[0].imshow(rgb(draw_e(img.copy(), ex["ellipse"], (0, 255, 0), 2))); ax[0].set_title("Image + ellipse annotée")
ax[1].imshow(tgt, cmap="gray"); ax[1].set_title("Masque cible 240×180 (tube 4 % du diamètre)")
for a in ax: a.axis("off")
save(fig, "fig1_masque.png")

# 2. augmentations (dont couleur)
random.seed(4); np.random.seed(4)
fig, ax = plt.subplots(3, 4, figsize=(9, 5.2))
k = 0
while k < 12:
    out = train_ds.load(random.randrange(len(train_ds)))
    if out[1] is None:
        continue
    ax.flat[k].imshow(rgb(out[0])); ax.flat[k].axis("off"); k += 1
fig.subplots_adjust(wspace=0.03, hspace=0.03)
save(fig, "fig2_augmentations.png")

# 2b. les trois augmentations de couleur sur la meme image
im0 = cv2.imread(ex["path"])
hsv = cv2.cvtColor(im0, cv2.COLOR_BGR2HSV); hsv[..., 0] = (hsv[..., 0].astype(int) + 60) % 180
v1 = cv2.cvtColor(hsv.astype(np.uint8), cv2.COLOR_HSV2BGR)
v2 = np.ascontiguousarray(im0[..., [1, 2, 0]])
v3 = cv2.cvtColor(cv2.cvtColor(im0, cv2.COLOR_BGR2GRAY), cv2.COLOR_GRAY2BGR)
fig, ax = plt.subplots(1, 4, figsize=(10, 2.2))
for a, im, t in zip(ax, (im0, v1, v2, v3), ("origine", "teinte tournée (+120°)", "canaux permutés", "niveaux de gris")):
    a.imshow(rgb(im)); a.set_title(t); a.axis("off")
save(fig, "fig2b_couleur.png")

# 3. courbes d'apprentissage E3 (E2 en gris)
from tensorboard.backend.event_processing.event_accumulator import EventAccumulator  # noqa: E402
ea = {}
for k_, run in (("E3", "logs/E3_segmentation480_couleur_0"), ("E2", "logs/E2_segmentation480_0")):
    a = EventAccumulator(run); a.Reload(); ea[k_] = a
sc = lambda k_, t: ([s.step for s in ea[k_].Scalars(t)], [s.value for s in ea[k_].Scalars(t)])
fig, ax = plt.subplots(1, 3, figsize=(10, 2.8))
for k_, c, ls in (("E2", C2, "--"), ("E3", C3, "-")):
    x, y = sc(k_, "train/loss"); ax[0].plot(x, y, color=c, ls=":", lw=1)
    x, y = sc(k_, "valid/loss"); ax[0].plot(x, y, color=c, ls=ls, label=f"{k_} validation")
    x, y = sc(k_, "valid/center_err_med_px"); ax[1].plot(x, y, color=c, ls=ls, label=k_)
    x, y = sc(k_, "valid/mask_iou"); ax[2].plot(x, y, color=c, ls=ls, label=k_)
for a in ax:
    a.axvline(23, color=C3, lw=0.8, ls=":"); a.set_xlabel("époque")
ax[0].set_title("Perte (pointillés fins : entraînement)"); ax[0].legend(fontsize=7)
ax[1].set_title("Centre 2D, médiane (px)"); ax[1].set_ylim(0, 60); ax[1].legend(fontsize=7)
ax[2].set_title("IoU du masque"); ax[2].legend(fontsize=7)
save(fig, "fig3_courbes.png")

# 4. confusion, P/R, IoU
P = R["E3"]["presence"]; B = R["E3"]["boites"]
fig, ax = plt.subplots(1, 3, figsize=(10, 2.9))
M = np.array([[P["VN"], P["FP"]], [P["FN"], P["VP"]]])
ax[0].imshow(M, cmap="Blues")
for i in range(2):
    for j in range(2):
        ax[0].text(j, i, M[i, j], ha="center", va="center", color="white" if M[i, j] > 40 else "black", fontsize=12)
ax[0].set_xticks([0, 1], ["prédit vide", "prédit cerceau"]); ax[0].set_yticks([0, 1], ["vide", "cerceau"])
ax[0].set_title("Matrice de confusion (seuil 0,5)")
ax[1].plot(R["E2"]["presence"]["pr_rec"], R["E2"]["presence"]["pr_prec"], color=C2, ls="--", label=f"E2 AP {R['E2']['presence']['AP']:.3f}")
ax[1].plot(P["pr_rec"], P["pr_prec"], color=C3, label=f"E3 AP {P['AP']:.3f}")
ax[1].plot(*P["seuil05"], "o", color="red"); ax[1].set_xlabel("rappel"); ax[1].set_ylabel("précision")
ax[1].set_ylim(0.5, 1.02); ax[1].legend(fontsize=7); ax[1].set_title("Précision / rappel")
bins = np.linspace(0, 1, 11)
ax[2].hist([B["iou_visible"], B["iou_ellipse"]], bins=bins, color=[C3, "#7fb3e0"], label=["boîte", "ellipse"])
ax[2].legend(fontsize=7); ax[2].set_xlabel("IoU"); ax[2].set_title("IoU sur les 90 cerceaux (E3)")
save(fig, "fig4_presence.png")

# 5. chaine masque -> ellipse
model, cfg, _ = load_checkpoint("logs/E3_segmentation480_couleur_0")
img = cv2.imread(ex["path"])
x = data.preprocess(img, cfg["data"]["input_size"])[None]
with torch.no_grad():
    out = model(x)
prob = torch.sigmoid(out[1][0, 0]).numpy()
e = seg.mask_to_ellipse(prob, 960, 720)
binary = (prob >= 0.5).astype(np.uint8)
n, lab, stats, _ = cv2.connectedComponentsWithStats(binary)
comp = lab == (1 + int(np.argmax(stats[1:, cv2.CC_STAT_AREA])))
ys, xs = np.nonzero(comp)
a = seg.ransac_ellipse(np.stack([xs, ys], 1).astype(np.float64))
zone = np.dstack([np.zeros_like(prob), np.zeros_like(prob), np.zeros_like(prob)])
zone[comp] = (1, 0.85, 0)
zone = (zone * 255).astype(np.uint8)
if a is not None:
    cv2.ellipse(zone, (int(a[0]), int(a[1])), (int(a[2]), int(a[3])), a[4], 0, 360, (255, 0, 255), 1)
fig, ax = plt.subplots(1, 4, figsize=(11, 2.3))
ax[0].imshow(rgb(img)); ax[0].set_title("1. image")
ax[1].imshow(prob, cmap="inferno"); ax[1].set_title("2. probabilité « tube »")
ax[2].imshow(zone); ax[2].set_title("3. zone retenue + ellipse RANSAC")
ax[3].imshow(rgb(draw_e(img.copy(), e, (255, 0, 255), 3))); ax[3].set_title("4. ellipse finale")
for a_ in ax: a_.axis("off")
save(fig, "fig5_chaine.png")

# 6. ambiguite double (frame 0459)
cand = [s for s in VA + train_ds.samples if "frame_0459_" in s["file"] and s["ellipse"] is not None]
if cand:
    s = cand[0]
    img = cv2.imread(s["path"])
    with torch.no_grad():
        out = model(data.preprocess(img, cfg["data"]["input_size"])[None])
    e = seg.mask_to_ellipse(torch.sigmoid(out[1][0, 0]).numpy(), 960, 720)
    PE = PoseEstimator()
    poses = circle_poses(e, PE.K, PE.radius, PE.dist) if e is not None else []
    fig, ax = plt.subplots(1, len(poses) or 1, figsize=(8, 3))
    ax = np.atleast_1d(ax)
    for a_, p in zip(ax, poses):
        v = draw_e(img.copy(), e, (255, 0, 255), 2)
        c = p.center
        tip = c + 0.35 * p.normal
        px = lambda X: tuple(int(t) for t in cv2.projectPoints(np.asarray(X, float).reshape(1, 3), np.zeros(3), np.zeros(3), PE.K, PE.dist)[0].reshape(2))
        cv2.arrowedLine(v, px(c), px(tip), (0, 255, 255), 4, tipLength=0.25)
        a_.imshow(rgb(v)); a_.axis("off")
        a_.set_title(f"distance {p.distance:.2f} m\nlacet vers la normale {np.degrees(np.arctan2(p.normal[0], p.normal[2])):+.0f}°")
    save(fig, "fig6_ambiguite.png")

# 7. robustesse a la couleur
T = [t for t in R["couleur"]["tests"] if not t["test"].startswith("cerceau vert")]
lab = [t["test"].replace("teinte ", "teinte\n").replace("canaux ", "canaux\n").replace("niveaux de gris", "gris") for t in T]
xx = np.arange(len(T))
fig, ax = plt.subplots(1, 2, figsize=(10, 2.8))
ax[0].bar(xx - 0.2, [100 * t["E2"]["rappel"] for t in T], 0.4, color=C2, label="E2")
ax[0].bar(xx + 0.2, [100 * t["E3"]["rappel"] for t in T], 0.4, color=C3, label="E3")
ax[0].set_ylim(80, 100); ax[0].set_ylabel("rappel (%)"); ax[0].set_title("Cerceaux trouvés (sur 90)")
ax[1].bar(xx - 0.2, [t["E2"]["FP"] for t in T], 0.4, color=C2, label="E2")
ax[1].bar(xx + 0.2, [t["E3"]["FP"] for t in T], 0.4, color=C3, label="E3")
ax[1].set_ylabel("fausses alarmes (sur 30)"); ax[1].set_title("Faux positifs")
for a_ in ax:
    a_.set_xticks(xx, lab, fontsize=7); a_.legend(fontsize=7)
save(fig, "fig7_couleur.png")

# 8. essais en vol avec le cerceau vert (captures d'ecran de l'IHM)
def crops(video, times, box, size):
    c = cv2.VideoCapture(video); f = c.get(5); res = []
    for t in times:
        c.set(1, int(t * f)); ok, im = c.read()
        y0, y1, x0, x1 = box
        res.append(cv2.resize(im[y0:y1, x0:x1], size))
    return res


v1 = os.path.join(SCR, "vert", "vert.mp4")
if os.path.exists(v1):
    ims = crops(v1, [57.5, 60.2, 62.0, 64.0], (128, 500, 30, 528), (498, 372))
    fig, ax = plt.subplots(1, 4, figsize=(11, 2.3))
    for a_, im, t in zip(ax, ims, ("57 s : ellipse sur la main", "60 s : ellipse sur la main", "62 s : cerceau vert, p = 0,97", "64 s : cerceau vert, p = 1,00")):
        a_.imshow(rgb(im)); a_.set_title(t, fontsize=8); a_.axis("off")
    save(fig, "fig8_vert.png")
v2 = os.path.join(SCR, "plafond", "v.mp4")
if os.path.exists(v2):
    ims = crops(v2, [48.0, 50.0, 52.0, 53.0], (128, 500, 30, 528), (498, 372))
    fig, ax = plt.subplots(1, 4, figsize=(11, 2.3))
    for a_, im, t in zip(ax, ims, ("48 s : ellipse sur perche + cerceau", "50 s : idem, distance 1,2 m (fausse)", "52 s : ellipse sur la perche", "53 s : cerceau vert bien trouvé")):
        a_.imshow(rgb(im)); a_.set_title(t, fontsize=8); a_.axis("off")
    save(fig, "fig9_perche.png")
print("figures ok")
