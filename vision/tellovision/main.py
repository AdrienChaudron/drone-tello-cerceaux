"""
Point d'entree, comme torchtmpl :

    python -m tellovision.main configs/detect.yaml train
    python -m tellovision.main logs/HoopNet_0 test          # evalue + galerie de predictions

Chaque entrainement cree logs/<Classe>_<n>/ contenant : config.yaml, best_model.pt,
les courbes TensorBoard (tensorboard --logdir logs) et, apres test, predictions.jpg.
"""

import argparse
import os
import sys
import time

import cv2
import numpy as np
import torch
import yaml

from tellovision import data, losses, models, seg, utils


def is_seg(cfg):
    return cfg.get("task", "ellipse") == "segmentation"


def build(cfg):
    """Modele + perte selon la tache : regression de l'ellipse (defaut) ou segmentation de l'anneau."""
    if is_seg(cfg):
        return seg.RingSegNet(cfg["model"], cfg["data"]["input_size"]), seg.SegLoss(**cfg["loss"])
    return models.build_model(cfg["model"], cfg["data"]["input_size"]), losses.HoopLoss(**cfg["loss"])


def predict(model, cfg, img, return_prob=False):
    """
    Image BGR -> (probabilite de presence, ellipse en pixels ou None), quelle que soit la tache.
    return_prob=True (segmentation) : renvoie aussi la carte de probabilite "tube" (pour l'affichage).
    """
    x = data.preprocess(img, cfg["data"]["input_size"])[None]
    with torch.no_grad():
        out = model(x)
    h, w = img.shape[:2]
    if is_seg(cfg):
        p = torch.sigmoid(out[0][0, 0]).item()
        prob = torch.sigmoid(out[1][0, 0]).numpy()
        res = (p, seg.mask_to_ellipse(prob, w, h) if p >= 0.5 else None)
        return res + (prob,) if return_prob else res
    out = out[0]
    p = torch.sigmoid(out[0]).item()
    res = (p, data.decode_ellipse(out[1:].numpy(), w) if p >= 0.5 else None)
    return res + (None,) if return_prob else res


def train(cfg):
    utils.set_seed(cfg["data"]["seed"])
    device = torch.device("cuda" if torch.cuda.is_available() else "cpu")
    train_loader, valid_loader = (seg.get_seg_dataloaders if is_seg(cfg) else data.get_dataloaders)(cfg)

    model, loss_fn = build(cfg)
    model, loss_fn = model.to(device), loss_fn.to(device)

    o = cfg["optim"]
    backbone = list(model.backbone.parameters())
    head = list(model.head.parameters())
    optimizer = torch.optim.AdamW([
        {"params": backbone, "lr": o["lr"] * o["backbone_lr_mult"]},  # backbone pre-entraine : petits pas
        {"params": head, "lr": o["lr"]},
    ], weight_decay=o["weight_decay"])
    scheduler = torch.optim.lr_scheduler.CosineAnnealingLR(optimizer, T_max=cfg["nepochs"])

    run_name = cfg["logging"].get("run_name") or cfg["model"]["class"]   # nom explicite de l'experience
    logdir = utils.generate_unique_logpath(cfg["logging"]["logdir"], run_name)
    os.makedirs(logdir)
    with open(os.path.join(logdir, "config.yaml"), "w") as f:
        yaml.safe_dump(cfg, f, sort_keys=False)
    from torch.utils.tensorboard import SummaryWriter
    writer = SummaryWriter(logdir)
    checkpoint = utils.ModelCheckpoint(model, cfg, os.path.join(logdir, "best_model.pt"))

    n_params = sum(p.numel() for p in model.parameters())
    print(f"Logs : {logdir}   |   {n_params / 1e6:.2f} M parametres   |   device : {device}")
    print(f"{len(train_loader.dataset)} echantillons d'entrainement / epoque, "
          f"{len(valid_loader.dataset)} de validation")

    for epoch in range(cfg["nepochs"]):
        t0 = time.time()
        tr = utils.train_one_epoch(model, train_loader, loss_fn, optimizer, device)
        va = utils.evaluate(model, valid_loader, loss_fn, device,
                            metric=seg.SegMetricAccumulator() if is_seg(cfg) else None)
        scheduler.step()

        for k, v in tr.items():
            writer.add_scalar(f"train/{k}", v, epoch)
        for k, v in va.items():
            writer.add_scalar(f"valid/{k}", v, epoch)
        best = checkpoint.update(va["loss"], epoch)

        nan = float("nan")
        print(f"[{epoch:3d}] {time.time() - t0:5.1f}s  train {tr['loss']:.4f}  valid {va['loss']:.4f}  "
              f"acc {va['accuracy']:.2f}  centre {va.get('center_err_px', nan):5.1f}px  "
              f"grand axe {100 * va.get('major_err_rel', nan):4.1f}%  B/A {va.get('ratio_err', nan):.3f}  "
              f"angle {va.get('angle_err_deg', nan):4.1f}deg"
              + (f"  IoU masque {va['mask_iou']:.2f}  centre med {va.get('center_err_med_px', nan):5.1f}px"
                 if is_seg(cfg) else "") + ("  *" if best else ""))

        if checkpoint.epochs_since_best >= cfg["patience"]:
            print(f"Arret anticipe : pas d'amelioration depuis {cfg['patience']} epoques.")
            break
    writer.close()
    print(f"Meilleur modele (valid loss {checkpoint.best:.4f}) : {checkpoint.savepath}")
    return logdir


def load_checkpoint(path, device="cpu"):
    """Accepte un dossier de run (logs/HoopNet_0) ou directement un fichier .pt."""
    if os.path.isdir(path):
        path = os.path.join(path, "best_model.pt")
    ckpt = torch.load(path, map_location=device, weights_only=False)
    cfg = ckpt["config"]
    model = build(cfg)[0].to(device)
    model.load_state_dict(ckpt["state_dict"])
    model.eval()
    return model, cfg, ckpt


def draw_ellipse(img, target, color, w, offset):
    cx, cy, A, B, th = data.decode_ellipse(target, w)
    cv2.ellipse(img, (int(cx + offset), int(cy + offset)), (max(int(A), 1), max(int(B), 1)), th,
                0, 360, color, 3)


def test(run_path):
    device = torch.device("cpu")
    model, cfg, ckpt = load_checkpoint(run_path, device)
    cfg["data"]["num_workers"] = 0
    _, valid_loader = (seg.get_seg_dataloaders if is_seg(cfg) else data.get_dataloaders)(cfg)
    loss_fn = build(cfg)[1]
    res = utils.evaluate(model, valid_loader, loss_fn, device,
                         metric=seg.SegMetricAccumulator() if is_seg(cfg) else None)
    print(f"Modele de l'epoque {ckpt['epoch']}  --  validation :")
    for k, v in res.items():
        print(f"  {k:14s} {v:.4f}")

    # Galerie : verite terrain en vert, prediction en rouge (marge grise pour les boites hors champ)
    ds = valid_loader.dataset
    tiles = []
    with torch.no_grad():
        for k in range(len(ds)):
            img, e, present = ds.load(k)
            h, w = img.shape[:2]
            p, e_pred = predict(model, cfg, img)
            m = int(0.3 * w)
            canvas = cv2.copyMakeBorder(img, m, m, m, m, cv2.BORDER_CONSTANT, value=(110, 110, 110))
            if e is not None:
                draw_ellipse(canvas, data.encode_ellipse(e, w), (0, 255, 0), w, m)
            if e_pred is not None:
                draw_ellipse(canvas, data.encode_ellipse(e_pred, w), (0, 0, 255), w, m)
            ok = (p >= 0.5) == bool(present)
            cv2.putText(canvas, f"p={p:.2f} {'OK' if ok else 'ERREUR'}", (10, 50),
                        cv2.FONT_HERSHEY_SIMPLEX, 1.6, (255, 255, 255) if ok else (0, 0, 255), 3)
            tiles.append(cv2.resize(canvas, (400, 340)))
    cols = 5
    tiles += [np.zeros_like(tiles[0])] * (-len(tiles) % cols)
    grid = np.vstack([np.hstack(tiles[i:i + cols]) for i in range(0, len(tiles), cols)])
    run_dir = run_path if os.path.isdir(run_path) else os.path.dirname(run_path)
    out_path = os.path.join(run_dir, "predictions.jpg")
    cv2.imwrite(out_path, grid, [cv2.IMWRITE_JPEG_QUALITY, 85])
    print("Galerie (vert = ellipse annotee, rouge = prediction) :", out_path)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("path", help="config .yaml (train) ou dossier de run / .pt (test)")
    ap.add_argument("command", choices=["train", "test"])
    args = ap.parse_args()
    if args.command == "train":
        with open(args.path) as f:
            cfg = yaml.safe_load(f)
        logdir = train(cfg)
        test(logdir)
    else:
        test(args.path)


if __name__ == "__main__":
    sys.exit(main())
