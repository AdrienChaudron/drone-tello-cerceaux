# Archives

Code conservé pour mémoire et pour reproduire nos résultats, mais **inutile pour faire voler le drone**.
Ces scripts ont été écrits pour l'arborescence d'origine (`tools/` et `configs/` à la racine de `vision/`) :
pour en réutiliser un, le recopier dans `vision/tools/` (et sa configuration dans `vision/configs/`).

| Dossier | Contenu |
|---|---|
| `entrainement/` | entraînement et évaluation des modèles : configurations E0 à E3 (`configs/`), annotation des images (`annotate_hoops.py`), calibration de la caméra (`calibrate_camera.py`, damier `damier_9x6_27mm.pdf`), capture d'images (`capture_live.py`), comparaison des modèles (`compare_models.py`), visualisation des augmentations (`show_augmentations.py`). Les 615 images annotées ne sont pas versionnées. |
| `outils_test/` | outils de mise au point : détection en direct sans décollage (`live_detect.py`), visualiseurs du flux MQTT (`voir_mqtt.py`, `view_stream.py`, `deux_vues.sh`), localisation sur une séquence (`localize.py`), simulateurs du PC de contrôle et de la recherche (`simulate_hil.py`, `simulate_recherche.py`), IHM et broker de simulation (`ihm_sim/`, `configs/reseau_sim.yaml`). |
| `anciens_essais/` | approches abandonnées : guidage direct, alignement unicycle, pilotage direct du Tello, identification de l'axe X, mesure du retard vidéo (voir son propre `LISEZMOI.md`). |

Entraîner à nouveau le modèle E3 (depuis `vision/`, avec les images dans `captures/`) :

```bash
cp archives/entrainement/configs/E3_segmentation480_couleur.yaml configs/
python -m tellovision.main configs/E3_segmentation480_couleur.yaml train
python -m tellovision.main logs/E3_segmentation480_couleur_0 test
```
