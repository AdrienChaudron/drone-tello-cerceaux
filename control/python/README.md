# Partie création de commandes

Cette partie du code reçoit les états de la machine à états finis de la vision par MQTT, et produit des commandes à envoyer au drone connecté en WiFi.

## Répertoires

Que contiennent nos dossiers ?

- `lib` : librairies communes vision / commandes. Basiquement, les fonctions pub / sub sur MQTT et les enums des axes
- `tello_hil` : toutes la partie commande
    - `tello_hil/lib` : Toutes les libs propres à la partie commande. Définitions des objets axes, définitions des constantes trouvées en identification sur Matlab, HIL, etc.
    - `tello_hil/Tello_CL_control.py` : Programme qui coordonne toutes les libs pour mettre en place les réceptions de commandes / envois d'archives dans un thread, le HIL dans un autre, et l'envoi du flux vidéo pré-traité dans un dernier
    - `tello_hil/tello_sim.py` : simule le tello. Pratique si aucun drone sous la main au moment de faire un essais
- `tello_logs` : Le dossier qu'on aurait dû ajouter dans un .gitignore si on était des ingénieurs consciencieux et qu'on avait pas si peu de temps pour ce projet. C'est là que seront écrites les valeurs enregistrées par le programme python sur chaque axe
- `tello_nn/` : Contient les fichiers pour simuler les commandes du réseaux de neurones si Adrien n'est pas là. Contient aussi l'interface qu'il a dû utiliser pour se connecter de son côté. En dernier lieu, il y a un artéfact pour expliquer comment utiliser l'interface dans un langage fleuri.
