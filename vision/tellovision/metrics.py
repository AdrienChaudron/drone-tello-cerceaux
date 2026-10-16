"""
Metriques d'evaluation, pensees pour le guidage :
    - presence : exactitude, precision, rappel
    - ellipse (cerceaux presents, annotes en ellipse et detectes) :
        center_err_px   erreur du centre, en px d'une image 960 de large  -> cap / altitude
        major_err_rel   erreur relative sur le grand axe                  -> erreur relative de distance
        ratio_err       erreur absolue sur B/A (~ cos de l'angle de vue)  -> alignement sur la normale
        angle_err_deg   erreur d'inclinaison, seulement si B/A < 0.85     -> sens de rotation du cerceau
"""

import math

import torch

REF_W = 960   # largeur des images du Tello, pour exprimer l'erreur du centre en pixels


class MetricAccumulator:
    def __init__(self, threshold=0.5):
        self.threshold = threshold
        self.batches = []

    def update(self, out, present, target, has_e):
        self.batches.append(tuple(x.detach().cpu() for x in (out, present, target, has_e)))

    def compute(self):
        out, present, target, has_e = (torch.cat(x) for x in zip(*self.batches))
        pred = torch.sigmoid(out[:, 0]) >= self.threshold
        true = present > 0.5
        tp, fp, fn = (pred & true).sum().item(), (pred & ~true).sum().item(), (~pred & true).sum().item()
        m = {
            "accuracy": (pred == true).float().mean().item(),
            "precision": tp / max(tp + fp, 1),
            "recall": tp / max(tp + fn, 1),
        }
        hit = pred & true & (has_e > 0.5)
        if hit.any():
            p, t = out[hit, 1:], target[hit]
            m["center_err_px"] = ((p[:, :2] - t[:, :2]).norm(dim=1) * REF_W).mean().item()
            m["major_err_rel"] = ((p[:, 2] - t[:, 2]).abs() / t[:, 2]).mean().item()
            m["ratio_err"] = (p[:, 3] - t[:, 3]).abs().mean().item()
            flat = t[:, 3] < 0.85
            if flat.any():
                a_p = torch.atan2(p[flat, 5], p[flat, 4]) / 2
                a_t = torch.atan2(t[flat, 5], t[flat, 4]) / 2
                d = (a_p - a_t).abs() % math.pi
                m["angle_err_deg"] = torch.rad2deg(torch.minimum(d, math.pi - d)).mean().item()
        return m
