"""
show_augmentations.py
Affiche une galerie d'images telles que le reseau les verra (augmentations tirees au hasard),
avec l'ellipse annotee dessinee sur une marge grise quand elle deborde de l'image.

Usage :
    python tools/show_augmentations.py configs/detect.yaml               # entrainement (augmente)
    python tools/show_augmentations.py configs/detect.yaml --split valid # validation (brut)
Sortie : logs/augmentations_<split>.jpg
"""

import argparse
import os
import random

import cv2
import numpy as np
import yaml

from tellovision.data import get_datasets


def tile(img, e, present, title, size=(480, 360), margin=0.3):
    """e = ellipse (cx, cy, A, B, theta) en pixels, ou None (image vide ou corde)."""
    h, w = img.shape[:2]
    s = size[0] / w
    img = cv2.resize(img, (size[0], int(h * s)))
    px, py = int(size[0] * margin), int(img.shape[0] * margin)
    img = cv2.copyMakeBorder(img, py, py, px, px, cv2.BORDER_CONSTANT, value=(110, 110, 110))
    if e is not None:
        cx, cy, A, B, th = e
        cv2.ellipse(img, (int(cx * s + px), int(cy * s + py)), (max(int(A * s), 1), max(int(B * s), 1)),
                    th, 0, 360, (0, 255, 0), 2)
    cv2.putText(img, title, (6, 22), cv2.FONT_HERSHEY_SIMPLEX, 0.6, (255, 255, 255), 2)
    return img


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("config")
    ap.add_argument("--split", choices=["train", "valid"], default="train")
    ap.add_argument("--n", type=int, default=24)
    ap.add_argument("--cols", type=int, default=4)
    ap.add_argument("--seed", type=int, default=None)
    args = ap.parse_args()

    cfg = yaml.safe_load(open(args.config))
    if args.seed is not None:
        random.seed(args.seed)
        np.random.seed(args.seed)
    train_ds, valid_ds = get_datasets(cfg)
    ds = train_ds if args.split == "train" else valid_ds

    for name, d in (("train", train_ds), ("valid", valid_ds)):
        n_pos = sum(s["present"] for s in d.samples)
        print(f"{name:5s} : {len(d.samples)} images ({n_pos} hoop, {len(d.samples) - n_pos} no_hoop)"
              f" -> {len(d)} echantillons par epoque")

    idx = random.sample(range(len(ds)), min(args.n, len(ds)))
    tiles = []
    for k in idx:
        img, e, present = ds.load(k)
        name = os.path.basename(ds.samples[ds.index[k]]["file"])[:22]
        title = ("HOOP " if e is not None else "CORDE " if present else "vide ") + name
        tiles.append(tile(img, e, present, title))
    blank = np.zeros_like(tiles[0])
    tiles += [blank] * (-len(tiles) % args.cols)
    grid = np.vstack([np.hstack(tiles[i:i + args.cols]) for i in range(0, len(tiles), args.cols)])

    os.makedirs("logs", exist_ok=True)
    out = f"logs/augmentations_{args.split}.jpg"
    cv2.imwrite(out, grid, [cv2.IMWRITE_JPEG_QUALITY, 85])
    print("Galerie :", out)


if __name__ == "__main__":
    main()
