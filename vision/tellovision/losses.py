"""
Fonction de perte : presence (classification) + ellipse (regression, seulement quand l'ellipse est annotee).

Sortie du reseau : [logit, cx, cy, grand axe, rapport B/A, cos 2theta, sin 2theta]
Cible            :        [cx, cy, grand axe, rapport B/A, cos 2theta, sin 2theta]
"""

import torch
import torch.nn as nn
import torch.nn.functional as F


class HoopLoss(nn.Module):
    def __init__(self, ellipse_weight=5.0, angle_weight=1.0, pos_weight=1.0):
        super().__init__()
        self.ellipse_weight = ellipse_weight
        self.angle_weight = angle_weight
        self.register_buffer("pos_weight", torch.tensor([pos_weight]))

    def forward(self, out, present, target, has_e):
        """Renvoie (perte totale, perte de presence, perte d'ellipse)."""
        l_cls = F.binary_cross_entropy_with_logits(out[:, 0], present, pos_weight=self.pos_weight)
        m = has_e > 0.5                        # images vides et "cordes" : pas de perte d'ellipse
        if not m.any():
            return l_cls, l_cls, out.new_zeros(())
        p, t = out[m, 1:], target[m]
        l_center = F.smooth_l1_loss(p[:, :2], t[:, :2], beta=0.02)
        # grand axe en echelle log : on penalise l'erreur RELATIVE (= erreur relative sur la distance)
        l_major = F.smooth_l1_loss(torch.log(p[:, 2]), torch.log(t[:, 2].clamp(min=1e-3)), beta=0.05)
        l_ratio = F.smooth_l1_loss(p[:, 3], t[:, 3], beta=0.05)
        # l'inclinaison n'a de sens que pour une ellipse aplatie : poids = 1 - B/A (0 pour un cercle)
        w = (1 - t[:, 3]).clamp(min=0)
        l_angle = (w * (p[:, 4:6] - t[:, 4:6]).abs().sum(dim=1)).sum() / w.sum().clamp(min=1e-6)
        l_e = l_center + l_major + l_ratio + self.angle_weight * l_angle
        return l_cls + self.ellipse_weight * l_e, l_cls, l_e
