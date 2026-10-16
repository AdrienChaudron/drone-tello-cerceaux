"""
seg.py : approche par SEGMENTATION de l'anneau.

Au lieu de predire 6 nombres pour toute l'image (regression), le reseau colorie, pixel par pixel,
ce qui appartient au tube du cerceau. On ajuste ensuite l'ellipse sur ces pixels (cv2.fitEllipse + RANSAC).
Le reseau fait ce qu'il fait bien (reconnaitre localement des pixels de tube), la geometrie exacte fait
le reste ; un arc partiel suffit a fitEllipse.

    image (3, H, W) -> encodeur MobileNetV3-small (pre-entraine) -> decodeur type U-Net
                    -> masque (1, H/2, W/2) : probabilite "tube" par pixel
                    -> + tete de presence (le cerceau est-il dans l'image ?)

Les masques d'entrainement sont dessines automatiquement a partir des ellipses annotees : aucune
nouvelle annotation n'est necessaire.
"""

import math

import cv2
import numpy as np
import torch
import torch.nn as nn
import torch.nn.functional as F
import torchvision

from tellovision import data


# ------------------------------------------------------------------ #
# Donnees : on ajoute le masque de l'anneau
# ------------------------------------------------------------------ #
def ring_target(e, img_w, img_h, mask_w, mask_h, thickness):
    """Masque de l'anneau a la resolution du masque predit (epaisseur relative au diametre)."""
    m = np.zeros((mask_h, mask_w), np.uint8)
    if e is None:
        return m
    sx, sy = mask_w / img_w, mask_h / img_h
    cx, cy, A, B, th = e
    t = max(2, int(round(thickness * 2 * A * sx)))
    # ellipse transformee par la mise a l'echelle (sx ~ sy car meme rapport 4:3)
    ee = data.affine_ellipse(e, np.diag([sx, sy]), np.zeros(2))
    cv2.ellipse(m, (int(round(ee[0])), int(round(ee[1]))), (max(int(ee[2]), 1), max(int(ee[3]), 1)),
                ee[4], 0, 360, 1, t)
    return m


class SegDataset(data.HoopDataset):
    """Comme HoopDataset, plus le masque de l'anneau. mask_valid = 0 pour les cordes (masque inconnu)."""

    def __init__(self, samples, input_size, augment=None, repeats=None, mask_stride=2, ring_thickness=0.04):
        super().__init__(samples, input_size, augment, repeats)
        self.mask_size = (input_size[0] // mask_stride, input_size[1] // mask_stride)
        self.ring_thickness = ring_thickness

    def __getitem__(self, k):
        img, e, present = self.load(k)
        h, w = img.shape[:2]
        target = data.encode_ellipse(e, w) if e is not None else np.zeros(data.N_TARGET, np.float32)
        mask = ring_target(e, w, h, *self.mask_size, self.ring_thickness)
        mask_valid = float(not (present and e is None))                    # corde : masque inconnu
        return (data.preprocess(img, self.input_size), torch.tensor(float(present)),
                torch.from_numpy(target), torch.tensor(float(e is not None)),
                torch.from_numpy(mask.astype(np.float32))[None], torch.tensor(mask_valid))


def get_seg_dataloaders(cfg):
    d, s = cfg["data"], cfg["seg"]
    train_ds, valid_ds = data.get_datasets(cfg)
    kw = dict(mask_stride=s["mask_stride"], ring_thickness=s["ring_thickness"])
    train_ds = SegDataset(train_ds.samples, d["input_size"], train_ds.augment, d["repeats"], **kw)
    valid_ds = SegDataset(valid_ds.samples, d["input_size"], None, None, **kw)
    g = torch.Generator().manual_seed(d["seed"])
    train_loader = torch.utils.data.DataLoader(train_ds, batch_size=d["batch_size"], shuffle=True, generator=g,
                                               num_workers=d["num_workers"], worker_init_fn=data._seed_worker,
                                               persistent_workers=d["num_workers"] > 0)
    valid_loader = torch.utils.data.DataLoader(valid_ds, batch_size=d["batch_size"], shuffle=False,
                                               num_workers=d["num_workers"])
    return train_loader, valid_loader


# ------------------------------------------------------------------ #
# Modele : encodeur MobileNetV3-small + decodeur U-Net
# ------------------------------------------------------------------ #
def conv_bn(cin, cout):
    return nn.Sequential(nn.Conv2d(cin, cout, 3, padding=1, bias=False), nn.BatchNorm2d(cout), nn.ReLU(inplace=True))


class UpBlock(nn.Module):
    """Double la resolution, concatene la "connexion de saut" de l'encodeur, puis deux convolutions."""

    def __init__(self, cin, cskip, cout):
        super().__init__()
        self.conv = nn.Sequential(conv_bn(cin + cskip, cout), conv_bn(cout, cout))

    def forward(self, x, skip):
        x = F.interpolate(x, size=skip.shape[2:], mode="bilinear", align_corners=False)
        return self.conv(torch.cat([x, skip], dim=1))


class RingSegNet(nn.Module):
    """
    Encodeur : les blocs de MobileNetV3-small, dont on garde les sorties a 1/2, 1/4, 1/8, 1/16 et 1/32.
    Decodeur : on remonte de 1/32 a 1/2 en reutilisant ces sorties (U-Net) pour retrouver le detail fin.
    Sorties : (logit de presence (B, 1), logits du masque (B, 1, H/2, W/2)).
    """

    TAPS = (0, 1, 3, 8, 12)        # indices des blocs de mobilenet_v3_small.features : pas 2, 4, 8, 16, 32

    def __init__(self, cfg, input_size):
        super().__init__()
        net = torchvision.models.mobilenet_v3_small(weights="IMAGENET1K_V1" if cfg.get("pretrained", True) else None)
        self.backbone = net.features
        with torch.no_grad():
            chans = [f.shape[1] for f in self._encode(torch.zeros(1, 3, input_size[1], input_size[0]))]
        c = cfg.get("decoder_channels", [96, 48, 32, 24])
        self.up1 = UpBlock(chans[4], chans[3], c[0])    # 1/32 -> 1/16
        self.up2 = UpBlock(c[0], chans[2], c[1])         # 1/16 -> 1/8
        self.up3 = UpBlock(c[1], chans[1], c[2])         # 1/8  -> 1/4
        self.up4 = UpBlock(c[2], chans[0], c[3])         # 1/4  -> 1/2
        self.mask_head = nn.Conv2d(c[3], 1, 1)
        self.presence_head = nn.Sequential(nn.AdaptiveAvgPool2d(1), nn.Flatten(), nn.Dropout(cfg.get("dropout", 0.2)),
                                           nn.Linear(chans[4], 1))

    def _encode(self, x):
        feats = []
        for i, block in enumerate(self.backbone):
            x = block(x)
            if i in self.TAPS:
                feats.append(x)
        return feats

    @property
    def head(self):               # pour l'optimiseur : tout ce qui n'est pas le backbone pre-entraine
        return nn.ModuleList([self.up1, self.up2, self.up3, self.up4, self.mask_head, self.presence_head])

    def forward(self, x):
        f = self._encode(x)
        y = self.up1(f[4], f[3])
        y = self.up2(y, f[2])
        y = self.up3(y, f[1])
        y = self.up4(y, f[0])
        return self.presence_head(f[4]), self.mask_head(y)


# ------------------------------------------------------------------ #
# Perte : presence + masque (BCE ponderee + Dice)
# ------------------------------------------------------------------ #
class SegLoss(nn.Module):
    """
    L'anneau ne couvre que ~1 % des pixels : une BCE simple apprendrait a tout predire "fond".
    On pondere donc les pixels d'anneau (pos_weight) et on ajoute la perte de Dice, qui mesure le
    recouvrement entre masque predit et masque vrai independamment du nombre de pixels de fond.
    """

    def __init__(self, mask_weight=1.0, dice_weight=1.0, ring_pos_weight=10.0, pos_weight=1.0):
        super().__init__()
        self.mask_weight, self.dice_weight = mask_weight, dice_weight
        self.register_buffer("ring_pos_weight", torch.tensor([ring_pos_weight]))
        self.register_buffer("pos_weight", torch.tensor([pos_weight]))

    def forward(self, out, present, target, has_e, mask, mask_valid):
        logit, mlog = out
        l_cls = F.binary_cross_entropy_with_logits(logit[:, 0], present, pos_weight=self.pos_weight)
        v = mask_valid > 0.5
        if not v.any():
            return l_cls, l_cls, logit.new_zeros(())
        ml, mt = mlog[v], mask[v]
        l_bce = F.binary_cross_entropy_with_logits(ml, mt, pos_weight=self.ring_pos_weight)
        p = torch.sigmoid(ml)
        inter = (p * mt).sum(dim=(1, 2, 3))
        dice = 1 - (2 * inter + 1) / (p.sum(dim=(1, 2, 3)) + mt.sum(dim=(1, 2, 3)) + 1)
        has_ring = mt.sum(dim=(1, 2, 3)) > 0
        l_dice = dice[has_ring].mean() if has_ring.any() else logit.new_zeros(())
        l_mask = self.mask_weight * l_bce + self.dice_weight * l_dice
        return l_cls + l_mask, l_cls, l_mask


# ------------------------------------------------------------------ #
# Du masque a l'ellipse
# ------------------------------------------------------------------ #
def ransac_ellipse(pts, tol=0.04, iters=150, min_points=20, seed=0):
    """Ellipse robuste sur un nuage de points (x, y) : RANSAC sur 5 points puis reajustement sur les points proches."""
    from tellovision.refine import fit_ellipse_pts, normalized_radius
    if len(pts) < min_points:
        return None
    rng = np.random.default_rng(seed)
    if len(pts) > 3000:
        pts = pts[rng.choice(len(pts), 3000, replace=False)]
    best, best_n = None, 0
    for _ in range(iters):
        try:
            cand = fit_ellipse_pts(pts[rng.choice(len(pts), 5, replace=False)])
        except cv2.error:
            continue
        if not np.all(np.isfinite(cand)) or cand[3] < 2 or cand[2] > 5000:
            continue
        n = int(np.sum(np.abs(normalized_radius(cand, pts[:, 0], pts[:, 1]) - 1) < tol))
        if n > best_n:
            best, best_n = cand, n
    if best is None or best_n < min_points:
        return None
    inl = pts[np.abs(normalized_radius(best, pts[:, 0], pts[:, 1]) - 1) < tol]
    return fit_ellipse_pts(inl)


def ellipse_support(prob, e, n=128):
    """Probabilite moyenne du masque le long de l'ellipse e (coordonnees du masque) : 'colle-t-elle' au masque ?"""
    pts = data.ellipse_points(e, n)
    h, w = prob.shape
    ok = (pts[:, 0] >= 0) & (pts[:, 0] < w - 0.5) & (pts[:, 1] >= 0) & (pts[:, 1] < h - 0.5)
    if ok.sum() < n * 0.2:
        return 0.0
    p = pts[ok]
    return float(prob[np.round(p[:, 1]).astype(int), np.round(p[:, 0]).astype(int)].mean())


def contour_coverage(prob, e, img_w, img_h, threshold=0.5, n=128):
    """
    Part du contour de l'ellipse e (pixels de l'image img_w x img_h) qui passe sur des pixels "tube" du masque
    (probabilite >= threshold), parmi les points du contour situes dans l'image. Un vrai cerceau : ~1 ;
    une ellipse ajustee sur un fragment (main, perche) : le contour traverse du vide.
    """
    h, w = prob.shape
    sx, sy = w / img_w, h / img_h                        # image -> masque (centres de pixels)
    em = (e[0] * sx + 0.5 * sx - 0.5, e[1] * sy + 0.5 * sy - 0.5, e[2] * sx, e[3] * sy, e[4])
    pts = data.ellipse_points(em, n)
    ok = (pts[:, 0] >= 0) & (pts[:, 0] < w - 0.5) & (pts[:, 1] >= 0) & (pts[:, 1] < h - 0.5)
    if not ok.any():
        return 0.0
    p = pts[ok]
    return float(np.mean(prob[np.round(p[:, 1]).astype(int), np.round(p[:, 0]).astype(int)] >= threshold))


def mask_to_ellipse(prob, img_w, img_h, threshold=0.5, ring_thickness=0.04, **kw):
    """
    Carte de probabilite (h, w) -> ellipse en pixels de l'image d'origine (ou None).
      1) on garde la plus grande zone connexe du masque (les taches isolees sont du bruit) ;
      2) candidat A : RANSAC sur tous les pixels de la zone (bon quand le masque est un anneau ou un arc) ;
         candidat B : ellipse du contour exterieur de la zone, reduite d'une demi-epaisseur de tube
         (bon pour les petits cerceaux, dont le masque est une tache pleine) ;
      3) on garde le candidat qui passe sur les pixels les plus probables du masque.
    """
    binary = (prob >= threshold).astype(np.uint8)
    n, lab, stats, _ = cv2.connectedComponentsWithStats(binary)
    if n < 2:
        return None
    k = 1 + int(np.argmax(stats[1:, cv2.CC_STAT_AREA]))
    comp = (lab == k)
    cands = []
    ys, xs = np.nonzero(comp)
    pts = np.stack([xs, ys], 1).astype(np.float64)
    a = ransac_ellipse(pts, **kw)
    if a is not None:
        cands.append(a)
    contours, _ = cv2.findContours(comp.astype(np.uint8), cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_NONE)
    c = max(contours, key=len)
    if len(c) >= 5:
        from tellovision.refine import fit_ellipse_pts
        bx = fit_ellipse_pts(c.reshape(-1, 2).astype(np.float64))
        half = ring_thickness * bx[2]                      # demi-epaisseur ~ 0.04 * diametre / 2
        cands.append((bx[0], bx[1], max(bx[2] - half, 1), max(bx[3] - half, 1), bx[4]))
    cands = [e for e in cands if np.all(np.isfinite(e)) and e[3] > 1]
    if not cands:
        return None
    best = max(cands, key=lambda e: ellipse_support(prob, e))
    sx, sy = img_w / prob.shape[1], img_h / prob.shape[0]
    # du repere du masque (centres de pixels) au repere de l'image
    return data.affine_ellipse(best, np.diag([sx, sy]), np.array([0.5 * sx - 0.5, 0.5 * sy - 0.5]))


class SegMetricAccumulator:
    """Memes metriques que la regression (pour comparer), l'ellipse etant ajustee sur le masque predit."""

    def __init__(self, threshold=0.5, img_size=(960, 720)):
        self.threshold, self.img_size = threshold, img_size
        self.rows = []
        self.inter = self.union = 0.0

    def update(self, out, present, target, has_e, mask, mask_valid):
        logit, mlog = (t.detach().cpu() for t in out)
        prob = torch.sigmoid(mlog)[:, 0].numpy()
        pm, tm = prob >= 0.5, mask[:, 0].numpy() > 0.5
        v = mask_valid.numpy() > 0.5
        self.inter += float((pm & tm)[v].sum())
        self.union += float((pm | tm)[v].sum())
        for i in range(len(logit)):
            self.rows.append((torch.sigmoid(logit[i, 0]).item(), present[i].item(), has_e[i].item(),
                              target[i].numpy(), prob[i]))

    def compute(self):
        W, H = self.img_size
        pred = np.array([r[0] >= self.threshold for r in self.rows])
        true = np.array([r[1] > 0.5 for r in self.rows])
        tp, fp, fn = int(np.sum(pred & true)), int(np.sum(pred & ~true)), int(np.sum(~pred & true))
        m = {"accuracy": float(np.mean(pred == true)), "precision": tp / max(tp + fp, 1),
             "recall": tp / max(tp + fn, 1), "mask_iou": self.inter / max(self.union, 1)}
        ce, me, re, fails = [], [], [], 0
        for (p, pres, he, tgt, prob), pr in zip(self.rows, pred):
            if not (pr and pres > 0.5 and he > 0.5):
                continue
            e = mask_to_ellipse(prob, W, H)
            if e is None:
                fails += 1
                continue
            g = data.decode_ellipse(tgt, W)
            ce.append(math.hypot(e[0] - g[0], e[1] - g[1]))
            me.append(abs(e[2] - g[2]) / g[2])
            re.append(abs(e[3] / e[2] - g[3] / g[2]))
        if ce:
            m.update(center_err_px=float(np.mean(ce)), center_err_med_px=float(np.median(ce)),
                     major_err_rel=float(np.mean(me)), ratio_err=float(np.mean(re)))
        m["fit_failures"] = fails
        return m
