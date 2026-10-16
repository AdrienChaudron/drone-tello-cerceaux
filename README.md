# Drone Tello : traversée automatique de cerceaux

Projet du cours *Contrôle de robots mobiles* (Polytech Nancy / FST Nancy) : un drone DJI Tello détecte un cerceau avec un réseau de neurones, s'aligne puis le traverse seul, sans pilotage.

Le projet tourne sur deux ordinateurs reliés en Ethernet, qui échangent par MQTT :

| Partie | Dossier | Rôle |
|---|---|---|
| Vision | [`vision/`](vision/) | reçoit la vidéo du drone, détecte le cerceau (CNN de segmentation), calcule sa position 3D et décide quoi faire (recherche, mise en axe, traversée) |
| Contrôle | *(à venir)* | asservit les axes du drone (hauteur, lacet, X, avance) et lui envoie les commandes moteur ; héberge le broker MQTT et l'IHM web |

Article complet du projet : *(lien à ajouter)*.

Auteurs : Adrien Chaudron (vision) et Samuel Stef (contrôle).
