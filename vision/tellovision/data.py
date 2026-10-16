"""
Chargement du dataset de cerceaux, decoupage entrainement / validation et augmentations.

Annotation d'un cerceau = ELLIPSE (projection du cercle reel par la camera), en pixels de l'image d'origine :
    e = (cx, cy, A, B, theta)   centre, demi-grand axe A >= demi-petit axe B, inclinaison du grand axe
                                en degres dans [0, 180) (sens horaire a l'ecran, y vers le bas).
L'ellipse est amodale (elle decrit le cerceau entier, meme hors champ).
Cas "corde" (partial = 1) : cerceau present mais seul un arc est visible -> pas d'ellipse.

Cible donnee au reseau (toutes les longueurs divisees par la LARGEUR W de l'image, pour ne pas
deformer les ellipses) :
    [cx / W, cy / W, 2A / W, B / A, cos 2theta, sin 2theta]
     centre    grand axe   rapport des axes (~ cos de l'angle de vue)   inclinaison
L'angle est code par (cos 2theta, sin 2theta) : une ellipse tournee de 180 deg est identique,
et ce codage n'a pas de discontinuite (contrairement a theta seul qui saute de 179 a 0).

Les images sont lues et traitees en BGR (OpenCV) ; preprocess() passe en RGB pour le reseau.
"""

import csv
import math
import os
import random
import re
import zlib

import cv2
import numpy as np
import torch
import yaml
from torch.utils.data import DataLoader, Dataset

MEAN = np.array([0.485, 0.456, 0.406], np.float32)   # normalisation ImageNet (backbones pre-entraines)
STD = np.array([0.229, 0.224, 0.225], np.float32)
N_TARGET = 6


# ------------------------------------------------------------------ #
# Geometrie des ellipses
#   forme parametrique : x = c + M u, avec |u| = 1 et M = R(theta) diag(A, B)
#   forme conique      : [x y 1] C [x y 1]^T = 0  (pour les homographies)
# ------------------------------------------------------------------ #
def ellipse_matrix(e):
    cx, cy, A, B, th = e
    t = math.radians(th)
    R = np.array([[math.cos(t), -math.sin(t)], [math.sin(t), math.cos(t)]])
    return np.array([cx, cy], float), R @ np.diag([A, B])


def ellipse_from_matrix(c, M):
    """Retrouve (cx, cy, A, B, theta) depuis x = c + M u (decomposition en valeurs singulieres)."""
    U, S, _ = np.linalg.svd(M)
    th = math.degrees(math.atan2(U[1, 0], U[0, 0])) % 180
    return float(c[0]), float(c[1]), float(S[0]), float(S[1]), th


def affine_ellipse(e, L, t):
    """Image de l'ellipse par x' = L x + t (exact : une transformation affine garde les ellipses)."""
    c, M = ellipse_matrix(e)
    return ellipse_from_matrix(L @ c + t, L @ M)


def ellipse_to_conic(e):
    c, M = ellipse_matrix(e)
    Q = np.linalg.inv(M @ M.T)
    C = np.zeros((3, 3))
    C[:2, :2], C[:2, 2], C[2, :2] = Q, -Q @ c, -c @ Q
    C[2, 2] = c @ Q @ c - 1
    return C


def conic_to_ellipse(C):
    """Conique -> ellipse, ou None si ce n'est plus une ellipse (cerceau passe derriere la camera)."""
    C = (C + C.T) / 2
    Q, q, s = C[:2, :2], C[:2, 2], C[2, 2]
    try:
        c = -np.linalg.solve(Q, q)
    except np.linalg.LinAlgError:
        return None
    k = c @ Q @ c - s
    if abs(k) < 1e-12:
        return None
    vals, vecs = np.linalg.eigh(Q / k)
    if vals[0] <= 0:
        return None
    A, B = 1 / math.sqrt(vals[0]), 1 / math.sqrt(vals[1])
    th = math.degrees(math.atan2(vecs[1, 0], vecs[0, 0])) % 180
    return float(c[0]), float(c[1]), A, B, th


def homography_ellipse(e, H):
    """Image de l'ellipse par une homographie : C' = H^-T C H^-1 (une conique reste une conique)."""
    Hi = np.linalg.inv(H)
    return conic_to_ellipse(Hi.T @ ellipse_to_conic(e) @ Hi)


def ellipse_points(e, n=64):
    c, M = ellipse_matrix(e)
    t = np.linspace(0, 2 * np.pi, n, endpoint=False)
    return c + (M @ np.stack([np.cos(t), np.sin(t)])).T


def visible_fraction(e, w, h):
    """Part du contour de l'ellipse qui tombe dans l'image."""
    p = ellipse_points(e)
    return float(np.mean((p[:, 0] >= 0) & (p[:, 0] < w) & (p[:, 1] >= 0) & (p[:, 1] < h)))


def ellipse_bbox(e):
    cx, cy, A, B, th = e
    t = math.radians(th)
    hw = math.hypot(A * math.cos(t), B * math.sin(t))
    hh = math.hypot(A * math.sin(t), B * math.cos(t))
    return np.array([cx - hw, cy - hh, cx + hw, cy + hh])


# ------------------------------------------------------------------ #
# Lecture des annotations
# ------------------------------------------------------------------ #
def _timestamp(filename):
    """Horodatage (s) contenu dans le nom 'frame_0012_1790587386373.jpg', ou None."""
    m = re.search(r"_(\d{10,})\.\w+$", filename)
    return int(m.group(1)) / 1000 if m else None


def read_annotations(root_dir):
    samples = []
    with open(os.path.join(root_dir, "annotations.csv"), newline="") as f:
        for r in csv.DictReader(f):
            path = os.path.join(root_dir, r["file"])
            if not os.path.exists(path):
                continue
            present = int(r["present"])
            ellipse = None
            if present and r.get("ea") and r.get("partial") != "1":
                ellipse = (float(r["ecx"]), float(r["ecy"]), float(r["ea"]) / 2, float(r["eb"]) / 2,
                           float(r["eangle"]))
            samples.append({"file": r["file"], "path": path, "present": present,
                            "ellipse": ellipse, "ts": _timestamp(r["file"])})
    return samples


def split_by_blocks(samples, valid_ratio, block_seconds, seed):
    """
    Decoupe entrainement / validation STABLE par tranches de temps.
    Les images prises a quelques dixiemes de seconde d'intervalle sont presque identiques : elles doivent
    aller du meme cote, sinon la validation contient des quasi-doublons de l'entrainement (fuite de donnees).
    Chaque image appartient a la tranche floor(t / block_seconds) ; le cote de la tranche est fixe par un
    hachage de (seed, tranche). Consequence importante : reetiqueter ou deplacer une image (hoop <-> no_hoop)
    ne change PAS le cote des autres images, donc les experiences successives restent comparables.
    """
    train, valid = [], []
    for s in samples:
        key = int(s["ts"] // block_seconds) if s["ts"] is not None else os.path.basename(s["file"])
        h = zlib.crc32(f"{seed}:{key}".encode()) % 10000
        (valid if h < valid_ratio * 10000 else train).append(s)
    return train, valid


def blockiness(img, block=16):
    """
    Score d'artefacts de compression par blocs (images corrompues par des pertes Wi-Fi) :
    rapport du gradient horizontal sur les frontieres de blocs / ailleurs. ~1.2 = normal, > 2.5 = corrompu.
    """
    g = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY).astype(np.float32)
    dx = np.abs(np.diff(g, axis=1)).mean(axis=0)
    on = dx[block - 1::block].mean()
    off = np.delete(dx, np.arange(block - 1, len(dx), block)).mean()
    return float(on / (off + 1e-6))


def camera_matrix(cfg_aug, w, h):
    """Matrice K : calibration (configs/camera.yaml) si elle existe, sinon focale deduite du champ de vision."""
    path = cfg_aug.get("camera_yaml")
    if path and os.path.exists(path):
        with open(path) as f:
            cam = yaml.safe_load(f)
        K = np.array(cam["camera_matrix"], float)
        sx, sy = w / cam["image_size"][0], h / cam["image_size"][1]
        return np.diag([sx, sy, 1.0]) @ K
    f = math.hypot(w, h) / 2 / math.tan(math.radians(cfg_aug["fov_diag_deg"]) / 2)
    return np.array([[f, 0, w / 2], [0, f, h / 2], [0, 0, 1.0]])


# ------------------------------------------------------------------ #
# Augmentations (numpy / OpenCV) : l'ellipse suit EXACTEMENT les transformations geometriques
# ------------------------------------------------------------------ #
def ring_mask(shape, e, thickness):
    """Masque de l'anneau annote (epaisseur proportionnelle au grand axe)."""
    m = np.zeros(shape[:2], np.uint8)
    cx, cy, A, B, th = e
    t = max(3, int(thickness * 2 * A))
    axes = (max(int(A - t / 2), 1), max(int(B - t / 2), 1))
    cv2.ellipse(m, (int(round(cx)), int(round(cy))), axes, th, 0, 360, 255, t)
    return m


def paste_on_background(img, e, background, thickness):
    """Decoupe l'anneau et le colle sur une autre image : le fond et le support disparaissent."""
    bg = cv2.resize(background, (img.shape[1], img.shape[0]))
    if random.random() < 0.5:
        bg = bg[:, ::-1]
    m = ring_mask(img.shape, e, thickness) > 0
    out = bg.copy()
    out[m] = img[m]
    return out


def hflip(img, e):
    w = img.shape[1]
    img = img[:, ::-1].copy()
    if e is not None:
        e = affine_ellipse(e, np.diag([-1.0, 1.0]), np.array([w - 1.0, 0.0]))
    return img, e


def random_fill():
    return tuple(int(v) for v in np.random.randint(0, 256, 3))


def random_affine(img, e, scale, translate, min_visible, tries=10):
    """Zoom + decalage (= cerceau plus ou moins loin, ailleurs dans l'image)."""
    h, w = img.shape[:2]
    for _ in range(tries):
        s = random.uniform(*scale)
        t = np.array([(1 - s) * w / 2 + random.uniform(-translate, translate) * w,
                      (1 - s) * h / 2 + random.uniform(-translate, translate) * h])
        new_e = affine_ellipse(e, s * np.eye(2), t) if e is not None else None
        if new_e is None or visible_fraction(new_e, w, h) >= min_visible:
            M = np.hstack([s * np.eye(2), t[:, None]]).astype(np.float32)
            img = cv2.warpAffine(img, M, (w, h), borderMode=cv2.BORDER_CONSTANT, borderValue=random_fill())
            return img, new_e
    return img, e


def random_camera_rotation(img, e, K, max_yaw, max_pitch, max_roll, min_visible, tries=10):
    """
    Simule une rotation du drone (lacet, tangage, roulis) : H = K R K^-1.
    Une rotation PURE de la camera ne cree pas de parallaxe : toute l'image (cerceau ET fond) est
    transformee exactement, et l'ellipse aussi (par sa conique). Le point de vue sur le cerceau change :
    le reseau voit le meme cercle sous d'autres ellipses.
    """
    h, w = img.shape[:2]
    Ki = np.linalg.inv(K)
    for _ in range(tries):
        ang = np.radians([random.uniform(-max_pitch, max_pitch), random.uniform(-max_yaw, max_yaw),
                          random.uniform(-max_roll, max_roll)])
        R = cv2.Rodrigues(np.array([ang[0], 0, 0]))[0] @ cv2.Rodrigues(np.array([0, ang[1], 0]))[0] \
            @ cv2.Rodrigues(np.array([0, 0, ang[2]]))[0]
        H = K @ R @ Ki
        new_e = homography_ellipse(e, H) if e is not None else None
        if e is not None and (new_e is None or visible_fraction(new_e, w, h) < min_visible):
            continue
        img = cv2.warpPerspective(img, H, (w, h), borderMode=cv2.BORDER_CONSTANT, borderValue=random_fill())
        return img, new_e
    return img, e


def color_jitter(img, brightness, contrast, saturation, hue):
    hsv = cv2.cvtColor(img, cv2.COLOR_BGR2HSV).astype(np.float32)
    hsv[..., 0] = (hsv[..., 0] + random.uniform(-hue, hue)) % 180
    hsv[..., 1] *= random.uniform(1 - saturation, 1 + saturation)
    img = cv2.cvtColor(np.clip(hsv, 0, 255).astype(np.uint8), cv2.COLOR_HSV2BGR).astype(np.float32)
    mean = img.mean()
    img = (img - mean) * random.uniform(1 - contrast, 1 + contrast) + mean   # contraste
    img = img * random.uniform(1 - brightness, 1 + brightness)               # luminosite
    return np.clip(img, 0, 255).astype(np.uint8)


def hue_rotate(img):
    """Teinte de toute l'image tournee au hasard sur tout le cercle : le cerceau change de couleur (vert, bleu...)."""
    hsv = cv2.cvtColor(img, cv2.COLOR_BGR2HSV)
    hsv[..., 0] = ((hsv[..., 0].astype(np.int16) + random.randrange(180)) % 180).astype(np.uint8)
    return cv2.cvtColor(hsv, cv2.COLOR_HSV2BGR)


def channel_shuffle(img):
    """Canaux B, G, R permutes au hasard (autre facon de changer la couleur du cerceau)."""
    return np.ascontiguousarray(img[..., np.random.permutation(3)])


def grayscale(img):
    """Niveaux de gris (3 canaux identiques) : le reseau doit reconnaitre le cerceau a sa forme seule."""
    return cv2.cvtColor(cv2.cvtColor(img, cv2.COLOR_BGR2GRAY), cv2.COLOR_GRAY2BGR)


def motion_blur(img, max_size):
    k = random.randrange(3, max_size + 1, 2)
    kernel = np.zeros((k, k), np.float32)
    kernel[k // 2] = 1.0 / k
    R = cv2.getRotationMatrix2D((k / 2 - 0.5, k / 2 - 0.5), random.uniform(0, 180), 1)
    kernel = cv2.warpAffine(kernel, R, (k, k))
    return cv2.filter2D(img, -1, kernel / max(kernel.sum(), 1e-6))


def gaussian_noise(img, std):
    noise = np.random.normal(0, random.uniform(0, std), img.shape)
    return np.clip(img + noise, 0, 255).astype(np.uint8)


def cutout(img, max_frac):
    h, w = img.shape[:2]
    ch = random.randint(1, max(1, int(max_frac * h)))
    cw = random.randint(1, max(1, int(max_frac * w)))
    y, x = random.randint(0, h - ch), random.randint(0, w - cw)
    img = img.copy()
    img[y:y + ch, x:x + cw] = np.random.randint(0, 256, 3)
    return img


def jpeg(img, quality):
    q = random.randint(*quality)
    ok, enc = cv2.imencode(".jpg", img, [cv2.IMWRITE_JPEG_QUALITY, q])
    return cv2.imdecode(enc, cv2.IMREAD_COLOR) if ok else img


class HoopAugment:
    """Chaine d'augmentations tirees au hasard a chaque lecture d'une image (entrainement seulement)."""

    def __init__(self, cfg, backgrounds):
        self.c = cfg
        self.backgrounds = backgrounds        # chemins d'images no_hoop propres (du jeu d'entrainement)

    def __call__(self, img, e):
        """img BGR, e = ellipse (ou None si absent / corde). Renvoie (img, e) transformes."""
        c, p = self.c, random.random
        if e is not None and self.backgrounds and p() < c["p_background"]:
            img = paste_on_background(img, e, cv2.imread(random.choice(self.backgrounds)), c["ring_thickness"])
        if p() < c["p_flip"]:
            img, e = hflip(img, e)
        if p() < c["p_rotate"]:
            K = camera_matrix(c, img.shape[1], img.shape[0])
            img, e = random_camera_rotation(img, e, K, c["max_yaw"], c["max_pitch"], c["max_roll"],
                                            c["min_visible"])
        if p() < c["p_affine"]:
            img, e = random_affine(img, e, c["scale"], c["translate"], c["min_visible"])
        if p() < c["p_color"]:
            img = color_jitter(img, c["brightness"], c["contrast"], c["saturation"], c["hue"])
        # insensibilite a la couleur du cerceau (absentes de la config : desactivees, comme pour E0-E2)
        if p() < c.get("p_hue_rotate", 0.0):
            img = hue_rotate(img)
        if p() < c.get("p_channel_shuffle", 0.0):
            img = channel_shuffle(img)
        if p() < c.get("p_gray", 0.0):
            img = grayscale(img)
        if p() < c["p_motion_blur"]:
            img = motion_blur(img, c["blur_max"])
        if p() < c["p_noise"]:
            img = gaussian_noise(img, c["noise_std"])
        if p() < c["p_cutout"]:
            img = cutout(img, c["cutout_max"])
        if p() < c["p_jpeg"]:
            img = jpeg(img, c["jpeg_quality"])
        return img, e


# ------------------------------------------------------------------ #
# Dataset
# ------------------------------------------------------------------ #
def preprocess(img_bgr, input_size):
    """Image BGR (OpenCV) -> tenseur (3, H, W) normalise. A utiliser aussi en vol (detector)."""
    x = cv2.resize(img_bgr, tuple(input_size), interpolation=cv2.INTER_AREA)
    x = cv2.cvtColor(x, cv2.COLOR_BGR2RGB).astype(np.float32) / 255.0
    x = (x - MEAN) / STD
    return torch.from_numpy(x.transpose(2, 0, 1).copy())


def encode_ellipse(e, w):
    cx, cy, A, B, th = e
    t = math.radians(2 * th)
    return np.array([cx / w, cy / w, 2 * A / w, B / A, math.cos(t), math.sin(t)], np.float32)


def decode_ellipse(target, w):
    cx, cy, major, ratio, c2, s2 = (float(v) for v in target)
    A = major * w / 2
    return cx * w, cy * w, A, ratio * A, math.degrees(math.atan2(s2, c2)) / 2 % 180


class HoopDataset(Dataset):
    """
    Renvoie (image, present, cible, a_une_ellipse) :
        cible = [cx/W, cy/W, 2A/W, B/A, cos 2theta, sin 2theta] (zeros s'il n'y a pas d'ellipse)
        a_une_ellipse = 0 pour une image vide ou une "corde" (pas de perte d'ellipse sur ces images)
    repeats = {"hoop": n, "no_hoop": m} : chaque image apparait n (ou m) fois par epoque,
    avec a chaque fois une augmentation differente -> duplication sans rien ecrire sur le disque.
    """

    def __init__(self, samples, input_size, augment=None, repeats=None):
        self.samples = samples
        self.input_size = input_size
        self.augment = augment
        repeats = repeats or {}
        self.index = [i for i, s in enumerate(samples)
                      for _ in range(repeats.get("hoop" if s["present"] else "no_hoop", 1))]

    def __len__(self):
        return len(self.index)

    def load(self, k):
        """Image BGR augmentee + ellipse en pixels (ou None) + presence (utile pour la visualisation)."""
        s = self.samples[self.index[k]]
        img, e = cv2.imread(s["path"]), s["ellipse"]
        if self.augment is not None:
            img, e = self.augment(img, e)
        return img, e, s["present"]

    def __getitem__(self, k):
        img, e, present = self.load(k)
        w = img.shape[1]
        target = encode_ellipse(e, w) if e is not None else np.zeros(N_TARGET, np.float32)
        return (preprocess(img, self.input_size),
                torch.tensor(float(present)),
                torch.from_numpy(target),
                torch.tensor(float(e is not None)))


def _seed_worker(worker_id):
    seed = torch.initial_seed() % 2 ** 32
    np.random.seed(seed)
    random.seed(seed)


def get_datasets(cfg):
    d = cfg["data"]
    samples = read_annotations(d["root_dir"])
    train_s, valid_s = split_by_blocks(samples, d["valid_ratio"], d["block_seconds"], d["seed"])
    backgrounds = [s["path"] for s in train_s if not s["present"]
                   and blockiness(cv2.imread(s["path"])) <= d["max_blockiness"]]   # pas de fond corrompu
    train_ds = HoopDataset(train_s, d["input_size"], HoopAugment(cfg["augment"], backgrounds), d["repeats"])
    valid_ds = HoopDataset(valid_s, d["input_size"])
    return train_ds, valid_ds


def get_dataloaders(cfg):
    d = cfg["data"]
    train_ds, valid_ds = get_datasets(cfg)
    g = torch.Generator().manual_seed(d["seed"])
    train_loader = DataLoader(train_ds, batch_size=d["batch_size"], shuffle=True, generator=g,
                              num_workers=d["num_workers"], worker_init_fn=_seed_worker,
                              persistent_workers=d["num_workers"] > 0)
    valid_loader = DataLoader(valid_ds, batch_size=d["batch_size"], shuffle=False,
                              num_workers=d["num_workers"])
    return train_loader, valid_loader
