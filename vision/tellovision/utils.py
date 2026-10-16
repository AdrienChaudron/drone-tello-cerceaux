"""Boucles d'entrainement / evaluation, sauvegarde du meilleur modele, dossiers de logs."""

import os
import random

import numpy as np
import torch

from tellovision.metrics import MetricAccumulator


def set_seed(seed):
    random.seed(seed)
    np.random.seed(seed)
    torch.manual_seed(seed)


def generate_unique_logpath(logdir, raw_run_name):
    """logs/HoopNet_0, logs/HoopNet_1, ... : un dossier par experience."""
    i = 0
    while True:
        path = os.path.join(logdir, f"{raw_run_name}_{i}")
        if not os.path.isdir(path):
            return path
        i += 1


def train_one_epoch(model, loader, loss_fn, optimizer, device):
    model.train()
    tot = {"loss": 0.0, "loss_cls": 0.0, "loss_ellipse": 0.0}
    n = 0
    for batch in loader:                       # batch = (images, cibles...) : 4 cibles en regression, 6 en segmentation
        x, *targets = (t.to(device) for t in batch)
        out = model(x)
        loss, l_cls, l_ell = loss_fn(out, *targets)
        optimizer.zero_grad()
        loss.backward()
        optimizer.step()
        b = x.shape[0]
        for k, v in zip(tot, (loss, l_cls, l_ell)):
            tot[k] += v.item() * b
        n += b
    return {k: v / n for k, v in tot.items()}


@torch.no_grad()
def evaluate(model, loader, loss_fn, device, threshold=0.5, metric=None):
    model.eval()
    tot = {"loss": 0.0, "loss_cls": 0.0, "loss_ellipse": 0.0}
    n = 0
    acc = metric if metric is not None else MetricAccumulator(threshold)
    for batch in loader:
        x, *targets = (t.to(device) for t in batch)
        out = model(x)
        loss, l_cls, l_ell = loss_fn(out, *targets)
        b = x.shape[0]
        for k, v in zip(tot, (loss, l_cls, l_ell)):
            tot[k] += v.item() * b
        n += b
        acc.update(out, *targets)
    res = {k: v / n for k, v in tot.items()}
    res.update(acc.compute())
    return res


class ModelCheckpoint:
    """Sauvegarde le modele (poids + config) chaque fois que la metrique suivie s'ameliore."""

    def __init__(self, model, cfg, savepath, min_is_best=True):
        self.model, self.cfg, self.savepath = model, cfg, savepath
        self.min_is_best = min_is_best
        self.best = None
        self.epochs_since_best = 0

    def update(self, score, epoch):
        better = (self.best is None or (score < self.best if self.min_is_best else score > self.best))
        if better:
            self.best = score
            self.epochs_since_best = 0
            torch.save({"state_dict": self.model.state_dict(), "config": self.cfg, "epoch": epoch,
                        "score": score}, self.savepath)
        else:
            self.epochs_since_best += 1
        return better
