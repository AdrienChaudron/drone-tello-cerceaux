# Vision : détection du cerceau et ordres de guidage

Ce dossier contient tout ce qui tourne sur le PC vision pendant un vol :

```text
vidéo du Tello (MQTT, tello/video)
   └─► CNN de segmentation E3 (masque de l'anneau + probabilité de présence)
         └─► ajustement d'ellipse ─► position 3D du cerceau (calibration de la caméra)
               └─► machine à états : RECHERCHE / MISE_EN_AXE / TRAVERSEE / PERDU / ECHEC
                     └─► ordre envoyé au PC de contrôle (MQTT, tello/vision/ordre)
                         + image annotée et état pour l'IHM web (HTTP, port 8080)
```

## Installation

```bash
cd vision
python -m venv venv
source venv/bin/activate
pip install -r requirements.txt
pip install -e .            # rend le paquet tellovision importable
```

Le modèle entraîné (`logs/E3_segmentation480_couleur_0/best_model.pt`, 6,8 Mo) est fourni : aucun entraînement n'est nécessaire pour voler.

## Lancer la vision

Le broker MQTT tourne sur le PC de contrôle (adresse, identifiants et topics dans `configs/reseau.yaml`).

```bash
python tools/vision_node.py                  # vol : vision + ordres + IHM (http://<ce PC>:8080)
python tools/vision_node.py --no-commande    # test : vision et IHM seulement, aucun ordre envoyé
python tools/vision_node.py --broker 127.0.0.1
python tools/vision_node.py --run logs/<autre_modele>
```

Chaque vol est journalisé dans `logs/vol/` (un fichier CSV par lancement, non versionné).

## Organisation

| Chemin | Contenu |
|---|---|
| `tools/vision_node.py` | programme principal du PC vision |
| `tellovision/detector.py` | chaîne image → masque → ellipse → position 3D |
| `tellovision/seg.py` | réseau RingSegNet (MobileNetV3-small + U-Net), passage du masque à l'ellipse (RANSAC) |
| `tellovision/pose.py` | ellipse → cercle 3D (centre, normale, deux solutions) |
| `tellovision/frames.py` | repère caméra → repère drone (caméra inclinée de 10,3°) |
| `tellovision/ordres.py` | machine à états (recherche, mise en axe, traversée) et filtre des fausses ellipses |
| `tellovision/link.py` | réception de la vidéo MQTT |
| `tellovision/ihm_server.py` | flux MJPEG et état de la vision pour l'IHM web |
| `tellovision/main.py`, `data.py`, `models.py`, `losses.py`, `metrics.py`, `utils.py` | chargement du modèle et prétraitement (utilisés aussi pour l'entraînement) |
| `collegue/` | interface MQTT commune avec le PC de contrôle (`TelloInterface.send_vision`) |
| `configs/camera.yaml` | calibration de la caméra (focales, centre optique, distorsion) |
| `configs/drone.yaml` | inclinaison de la caméra |
| `configs/hoop.yaml` | diamètre du cerceau (0,68 m) : fixe l'échelle de toutes les distances |
| `configs/ordres.yaml` | réglages de la machine à états (seuils, durées, recherche) |
| `configs/reseau.yaml` | broker MQTT et topics |
| `logs/E3_segmentation480_couleur_0/` | modèle E3 retenu |
| `docs/` | rapports (dont `rapport_E3_segmentation_couleur.md` / `.pdf`) |
| `archives/` | code qui n'est pas nécessaire au vol : entraînement, outils de test, anciens essais |

## Ordre envoyé au PC de contrôle

À chaque image traitée (~15 images/s), sur `tello/vision/ordre` :

| Champ | Unité | Sens |
|---|---|---|
| `etat` | — | RECHERCHE, MISE_EN_AXE, TRAVERSEE, PERDU, ECHEC |
| `present` | — | cerceau vu récemment |
| `delta_x` | pixels (image 960×720) | > 0 : cerceau à droite |
| `delta_z` | m | > 0 : cerceau plus haut que le drone |
| `distance` | m | distance au cerceau |
| `r_yaw` | degrés absolus | consigne de cap |
| `r_z` | cm absolus | consigne de hauteur (recherche uniquement) |

## Résultats du modèle E3 (validation, 120 images)

Exactitude 95,8 %, précision 98,9 %, rappel 95,6 % ; centre de l'ellipse à 9,7 px près (médiane) ; distance à 1,7 % près (≈ 4 cm) entre 0,9 et 3,1 m ; ~66 ms par image sur processeur. Détails dans `docs/rapport_E3_segmentation_couleur.md`.
