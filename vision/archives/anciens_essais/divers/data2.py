"""
data2.py : VERSION PEDAGOGIQUE de data.py, avec les bibliotheques deja installees (torchvision, OpenCV, numpy).

    !!! Ce fichier n'est utilise par AUCUN script (entrainement, detection, vol). Il sert seulement a comparer
    !!! avec data.py : meme interface (get_datasets, get_dataloaders, preprocess, ...), autre facon de faire.
    !!! Le modele E2 a ete entraine avec data.py.

Ce qui change par rapport a data.py, et pourquoi
-------------------------------------------------
1. Augmentations PHOTOMETRIQUES (couleur, bruit, masquage, JPEG) -> torchvision.transforms.v2.
   Elles ne modifient que les pixels : l'ellipse ne bouge pas, donc une bibliotheque convient parfaitement.
   On gagne du code teste, et une seule chaine "v2.Compose" lisible d'un coup d'oeil.

2. Augmentations GEOMETRIQUES (miroir, zoom/decalage, rotation de camera) -> on GARDE notre code.
   Aucune bibliotheque ne transforme une ELLIPSE : torchvision/Albumentations savent deplacer des boites,
   des masques ou des points, pas une ellipse. On pourrait passer par des points du contour puis reajuster,
   mais ce serait moins exact (reajustement) et les points hors image sont souvent supprimes, alors que nos
   ellipses sont amodales. La rotation de camera H = K R K^-1 (avec la vraie calibration) n'existe nulle part.

3. Flou de BOUGE (motion blur) -> on garde notre version : torchvision n'a qu'un flou gaussien (isotrope),
   pas le flou directionnel d'un drone qui bouge (Albumentations l'a, mais n'est pas installe).

4. OPTIMISATION : l'image est reduite a la taille du reseau (480x360) DES LA LECTURE, avant les
   augmentations. data.py augmente l'image 960x720 puis la reduit : 4 fois plus de pixels a deformer
   pour rien. L'ellipse est reduite exactement par la meme transformation (affine_ellipse).
   Les images reduites sont gardees en memoire (cache) : on ne relit plus le disque a chaque epoque
   (615 images x 480x360x3 octets ~ 320 Mo).

5. Le reste (geometrie des ellipses, lecture des annotations, decoupage par tranches de temps,
   codage de la cible) est identique : c'est du calcul propre au projet, sans equivalent en bibliotheque.

Differences de comportement a connaitre (si on voulait vraiment l'utiliser) :
   - torchvision travaille en RGB et sur des tenseurs (3, H, W) ; data.py en BGR numpy (H, W, 3).
   - v2.ColorJitter : la teinte est une fraction de tour (0,022 ~ 8 deg), data.py utilise l'echelle
     OpenCV 0..180 (hue: 4 ~ 8 deg).
   - v2.GaussianNoise : ecart-type fixe ; data.py tire l'ecart-type au hasard dans [0, noise_std].
   - Le JPEG est applique a l'image deja reduite (480x360) au lieu de 960x720.
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
from torchvision.transforms import v2

MEAN = [0.485, 0.456, 0.406]   # normalisation ImageNet (backbones pre-entraines)
STD = [0.229, 0.224, 0.225]
N_TARGET = 6


# ------------------------------------------------------------------ #
# Geometrie des ellipses : IDENTIQUE a data.py (aucune bibliotheque ne fait ces calculs)
#   forme parametrique : x = c + M u, avec |u| = 1 et M = R(theta) diag(A, B)
#   forme conique      : [x y 1] C [x y 1]^T = 0  (pour les homographies)
# ------------------------------------------------------------------ #
def ellipse_matrix(e):
    cx, cy, A, B, th = e
    t = math.radians(th)
    R = np.array([[math.cos(t), -math.sin(t)], [math.sin(t), math.cos(t)]])
    return np.array([cx, cy], float), R @ np.diag([A, B])


def ellipse_from_matrix(c, M):
    U, S, _ = np.linalg.svd(M)
    th = math.degrees(math.atan2(U[1, 0], U[0, 0])) % 180
    return float(c[0]), float(c[1]), float(S[0]), float(S[1]), th


def affine_ellipse(e, L, t):
    """Image exacte de l'ellipse par x' = L x + t."""
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
    """Image exacte de l'ellipse par une homographie : C' = H^-T C H^-1."""
    Hi = np.linalg.inv(H)
    return conic_to_ellipse(Hi.T @ ellipse_to_conic(e) @ Hi)


def ellipse_points(e, n=64):
    c, M = ellipse_matrix(e)
    t = np.linspace(0, 2 * np.pi, n, endpoint=False)
    return c + (M @ np.stack([np.cos(t), np.sin(t)])).T


def visible_fraction(e, w, h):
    p = ellipse_points(e)
    return float(np.mean((p[:, 0] >= 0) & (p[:, 0] < w) & (p[:, 1] >= 0) & (p[:, 1] < h)))


def ellipse_bbox(e):
    cx, cy, A, B, th = e
    t = math.radians(th)
    hw = math.hypot(A * math.cos(t), B * math.sin(t))
    hh = math.hypot(A * math.sin(t), B * math.cos(t))
    return np.array([cx - hw, cy - hh, cx + hw, cy + hh])


def scale_ellipse(e, s):
    """Ellipse d'une image redimensionnee d'un facteur s (convention OpenCV : centres de pixels)."""
    return affine_ellipse(e, s * np.eye(2), np.array([0.5 * s - 0.5, 0.5 * s - 0.5]))


# ------------------------------------------------------------------ #
# Lecture des annotations et decoupage : IDENTIQUE a data.py
# ------------------------------------------------------------------ #
def _timestamp(filename):
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
    """Decoupage STABLE par tranches de temps (voir data.py pour l'explication)."""
    train, valid = [], []
    for s in samples:
        key = int(s["ts"] // block_seconds) if s["ts"] is not None else os.path.basename(s["file"])
        h = zlib.crc32(f"{seed}:{key}".encode()) % 10000
        (valid if h < valid_ratio * 10000 else train).append(s)
    return train, valid


def blockiness(img, block=16):
    g = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY).astype(np.float32)
    dx = np.abs(np.diff(g, axis=1)).mean(axis=0)
    on = dx[block - 1::block].mean()
    off = np.delete(dx, np.arange(block - 1, len(dx), block)).mean()
    return float(on / (off + 1e-6))


def camera_matrix(cfg_aug, w, h):
    """Matrice K a la taille (w, h) : la reduction 960x720 -> 480x360 divise simplement K par 2."""
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
# Augmentations GEOMETRIQUES : notre code (l'ellipse doit suivre EXACTEMENT)
# ------------------------------------------------------------------ #
def random_fill():
    return tuple(int(v) for v in np.random.randint(0, 256, 3))


def hflip(img, e):
    w = img.shape[1]
    img = cv2.flip(img, 1)                                   # OpenCV au lieu de img[:, ::-1].copy()
    if e is not None:
        e = affine_ellipse(e, np.diag([-1.0, 1.0]), np.array([w - 1.0, 0.0]))
    return img, e


def random_affine(img, e, scale, translate, min_visible, tries=10):
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
    """Rotation pure de la camera : H = K R K^-1 (aucun equivalent en bibliotheque)."""
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


def motion_blur(img, max_size):
    """Flou de bouge directionnel : pas d'equivalent dans torchvision (seulement un flou gaussien)."""
    k = random.randrange(3, max_size + 1, 2)
    kernel = np.zeros((k, k), np.float32)
    kernel[k // 2] = 1.0 / k
    R = cv2.getRotationMatrix2D((k / 2 - 0.5, k / 2 - 0.5), random.uniform(0, 180), 1)
    kernel = cv2.warpAffine(kernel, R, (k, k))
    return cv2.filter2D(img, -1, kernel / max(kernel.sum(), 1e-6))


# ------------------------------------------------------------------ #
# Augmentations PHOTOMETRIQUES : torchvision.transforms.v2
# ------------------------------------------------------------------ #
def photometric_pipeline(c):
    """
    Remplace color_jitter, gaussian_noise, cutout et jpeg de data.py par une seule chaine torchvision.
    Entree : tenseur uint8 (3, H, W) en RGB. Sortie : tenseur float normalise, pret pour le reseau.
    RandomApply(..., p) applique la transformation avec la probabilite p, comme les "if p() < ..." de data.py.
    """
    cut = c["cutout_max"] ** 2                               # data.py : cote <= 15 % -> aire <= 2,25 %
    return v2.Compose([
        v2.RandomApply([v2.ColorJitter(brightness=c["brightness"], contrast=c["contrast"],
                                       saturation=c["saturation"], hue=c["hue"] / 180)], p=c["p_color"]),
        v2.ToDtype(torch.float32, scale=True),               # uint8 0..255 -> float 0..1
        v2.RandomApply([v2.GaussianNoise(sigma=c["noise_std"] / 255)], p=c["p_noise"]),
        v2.RandomErasing(p=c["p_cutout"], scale=(cut / 50, cut), value="random"),   # = cutout
        v2.ToDtype(torch.uint8, scale=True),                 # JPEG travaille sur des uint8
        v2.RandomApply([v2.JPEG(quality=tuple(c["jpeg_quality"]))], p=c["p_jpeg"]),
        v2.ToDtype(torch.float32, scale=True),
        v2.Normalize(MEAN, STD),                             # normalisation ImageNet
    ])


NORMALIZE_ONLY = v2.Compose([v2.ToDtype(torch.float32, scale=True), v2.Normalize(MEAN, STD)])


def to_tensor_rgb(img_bgr):
    """Image OpenCV BGR (H, W, 3) uint8 -> tenseur RGB (3, H, W) uint8 (format attendu par torchvision)."""
    return torch.from_numpy(cv2.cvtColor(img_bgr, cv2.COLOR_BGR2RGB)).permute(2, 0, 1).contiguous()


class HoopAugment:
    """Geometrie (notre code, sur l'image BGR) puis photometrie (torchvision, sur le tenseur RGB)."""

    def __init__(self, cfg):
        self.c = cfg
        self.photo = photometric_pipeline(cfg)

    def __call__(self, img, e):
        """img BGR deja reduite, e = ellipse a la meme echelle. Renvoie (tenseur normalise, e)."""
        c, p = self.c, random.random
        if p() < c["p_flip"]:
            img, e = hflip(img, e)
        if p() < c["p_rotate"]:
            K = camera_matrix(c, img.shape[1], img.shape[0])
            img, e = random_camera_rotation(img, e, K, c["max_yaw"], c["max_pitch"], c["max_roll"],
                                            c["min_visible"])
        if p() < c["p_affine"]:
            img, e = random_affine(img, e, c["scale"], c["translate"], c["min_visible"])
        if p() < c["p_motion_blur"]:
            size = max(3, int(c["blur_max"] * img.shape[1] / 960) | 1)   # taille du flou a l'echelle de l'image
            img = motion_blur(img, size)
        return self.photo(to_tensor_rgb(img)), e


# ------------------------------------------------------------------ #
# Dataset
# ------------------------------------------------------------------ #
def preprocess(img_bgr, input_size):
    """Meme role que data.preprocess (utilise en vol) : reduction + normalisation."""
    x = cv2.resize(img_bgr, tuple(input_size), interpolation=cv2.INTER_AREA)
    return NORMALIZE_ONLY(to_tensor_rgb(x))


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
    Meme sortie que data.HoopDataset : (image, present, cible, a_une_ellipse).
    Difference : les images sont lues UNE fois, reduites a input_size et gardees en memoire.
    Attention : avec num_workers > 0, chaque processus de chargement a sa propre copie du cache.
    La cible est divisee par la largeur de l'image REDUITE : comme toutes les longueurs sont relatives
    a W, la cible est la meme qu'avec l'image d'origine.
    """

    def __init__(self, samples, input_size, augment=None, repeats=None):
        self.samples = samples
        self.input_size = tuple(input_size)
        self.augment = augment
        repeats = repeats or {}
        self.index = [i for i, s in enumerate(samples)
                      for _ in range(repeats.get("hoop" if s["present"] else "no_hoop", 1))]
        self._cache = {}

    def __len__(self):
        return len(self.index)

    def _read_small(self, i):
        """Image reduite + ellipse a la meme echelle, lues une seule fois (cache)."""
        if i not in self._cache:
            s = self.samples[i]
            img = cv2.imread(s["path"])
            k = self.input_size[0] / img.shape[1]
            small = cv2.resize(img, self.input_size, interpolation=cv2.INTER_AREA)
            e = scale_ellipse(s["ellipse"], k) if s["ellipse"] is not None else None
            self._cache[i] = (small, e)
        return self._cache[i]

    def __getitem__(self, k):
        i = self.index[k]
        img, e = self._read_small(i)
        if self.augment is not None:
            x, e = self.augment(img, e)
        else:
            x = NORMALIZE_ONLY(to_tensor_rgb(img))
        target = encode_ellipse(e, img.shape[1]) if e is not None else np.zeros(N_TARGET, np.float32)
        return (x, torch.tensor(float(self.samples[i]["present"])), torch.from_numpy(target),
                torch.tensor(float(e is not None)))


def _seed_worker(worker_id):
    seed = torch.initial_seed() % 2 ** 32
    np.random.seed(seed)
    random.seed(seed)                                         # torchvision utilise le generateur de torch


def get_datasets(cfg):
    d = cfg["data"]
    samples = read_annotations(d["root_dir"])
    train_s, valid_s = split_by_blocks(samples, d["valid_ratio"], d["block_seconds"], d["seed"])
    # (le collage sur fond, p_background, est desactive dans les configs actuelles : non repris ici)
    train_ds = HoopDataset(train_s, d["input_size"], HoopAugment(cfg["augment"]), d["repeats"])
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
