# Archives (plus utilisées, gardées pour mémoire)

Depuis le 09/10/2026, la machine à états et les asservissements sont sur le PC de contrôle ; notre PC n'envoie plus
que l'ordre de vision (voir ../README.md). Ces fichiers ne sont plus importés par le code actif et ne se lancent
plus tels quels depuis ce dossier (chemins relatifs à tools/).

- alignement/            guidances de notre côté avec alignement sur l'axe du cerceau (guidance.py, unicycle.py)
- guidance_directe/      guidance « visée directe » de notre côté (direct.py) et sa simulation
- identification/        identif_x.py : identification de l'axe X (résultats dans logs/identif/)
- pilotage_direct_tello/ programmes qui pilotaient le Tello directement (djitellopy), sans le PC de contrôle
- divers/                data2.py (version pédagogique de data.py), ancien annotateur, ancienne config,
                         view_stream.py (vidéo dans OpenCV : remplacée par l'IHM et vision_node.py --no-ordre)
- mesure_retard/         mesure_retard.py (retard camera / cap en vol) et test_flux_tello.py (flux + horloge) ; mesures dans logs/retard/
