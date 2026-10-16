"""
Architectures du detecteur. Sortie commune : tenseur (B, 7) =
    [logit de presence, cx, cy, grand axe, rapport B/A, cos 2theta, sin 2theta]
Toutes les longueurs sont divisees par la largeur W de l'image (voir data.py).

Plages imposees par les activations de sortie :
    cx, cy dans [-0.5, 1.5]   (le centre peut sortir de l'image)
    grand axe dans ]0, 2.5]   (cerceau tres proche : plus large que l'image)
    rapport B/A dans ]0, 1[   (B <= A par construction)
    cos 2theta, sin 2theta dans [-1, 1]
"""

import torch
import torch.nn as nn
import torchvision


class EllipseHead(nn.Module):
    """
    Tete de detection. On ne fait PAS de moyenne globale (global average pooling) :
    elle effacerait l'information "ou" dans l'image, indispensable pour la position de l'ellipse.
    On reduit les canaux (conv 1x1) puis on aplatit la carte spatiale.
    """

    def __init__(self, in_channels, feat_hw, head_channels, dropout):
        super().__init__()
        h, w = feat_hw
        self.reduce = nn.Sequential(
            nn.Conv2d(in_channels, head_channels, 1, bias=False),
            nn.BatchNorm2d(head_channels),
            nn.ReLU(inplace=True),
        )
        self.fc = nn.Sequential(
            nn.Flatten(),
            nn.Dropout(dropout),
            nn.Linear(head_channels * h * w, 256),
            nn.ReLU(inplace=True),
            nn.Dropout(dropout),
            nn.Linear(256, 7),
        )

    def forward(self, f):
        out = self.fc(self.reduce(f))
        logit = out[:, :1]
        center = 2 * torch.sigmoid(out[:, 1:3]) - 0.5
        major = 2.5 * torch.sigmoid(out[:, 3:4]) + 1e-3
        ratio = torch.sigmoid(out[:, 4:5])
        angle = torch.tanh(out[:, 5:7])
        return torch.cat([logit, center, major, ratio, angle], dim=1)


class HoopNet(nn.Module):
    """Backbone pre-entraine sur ImageNet (torchvision) + EllipseHead."""

    BACKBONES = {
        "mobilenet_v3_small": (torchvision.models.mobilenet_v3_small, "IMAGENET1K_V1"),
        "mobilenet_v3_large": (torchvision.models.mobilenet_v3_large, "IMAGENET1K_V2"),
        "resnet18": (torchvision.models.resnet18, "IMAGENET1K_V1"),
    }

    def __init__(self, cfg, input_size):
        super().__init__()
        fn, weights = self.BACKBONES[cfg["backbone"]]
        net = fn(weights=weights if cfg.get("pretrained", True) else None)
        if cfg["backbone"].startswith("resnet"):
            self.backbone = nn.Sequential(*list(net.children())[:-2])
        else:
            self.backbone = net.features
        with torch.no_grad():
            f = self.backbone(torch.zeros(1, 3, input_size[1], input_size[0]))
        self.head = EllipseHead(f.shape[1], f.shape[2:], cfg["head_channels"], cfg["dropout"])

    def forward(self, x):
        return self.head(self.backbone(x))


class SimpleCNN(nn.Module):
    """Petit reseau entraine de zero : reference pour mesurer l'apport du pre-entrainement."""

    def __init__(self, cfg, input_size):
        super().__init__()
        layers, c = [], 3
        for out_c in (16, 32, 64, 128, 128):
            layers += [nn.Conv2d(c, out_c, 3, padding=1, bias=False), nn.BatchNorm2d(out_c),
                       nn.ReLU(inplace=True), nn.MaxPool2d(2)]
            c = out_c
        self.backbone = nn.Sequential(*layers)
        feat_hw = (input_size[1] // 32, input_size[0] // 32)
        self.head = EllipseHead(c, feat_hw, cfg["head_channels"], cfg["dropout"])

    def forward(self, x):
        return self.head(self.backbone(x))


MODELS = {"HoopNet": HoopNet, "SimpleCNN": SimpleCNN}


def build_model(cfg_model, input_size):
    return MODELS[cfg_model["class"]](cfg_model, input_size)
