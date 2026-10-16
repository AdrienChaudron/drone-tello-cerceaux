# Code du collègue (PC de contrôle) : copie AVEC un ajout pour l'ordre de la vision

Copie du 09/10/2026 de son partage `share:/home/share/mini_projet_SIA/python/` (`lib/` et `tello_nn/`), à laquelle
on a AJOUTÉ (rien de l'existant n'est modifié : send_command, get_measures, status, archive marchent pareil) :

- `lib/MqttInterface.py` : topic `tello/vision/ordre` ; `push_vision(etat, present, delta_x, delta_z, distance,
  r_yaw, r_z, **extra)` (PC vision) ; `retrieve_vision()` (PC de contrôle : DERNIER ordre, ou None) ;
  `init_mqtt_connection(..., subscribe_vision=True)` pour s'y abonner.
- `tello_nn/TelloInterface.py` : `send_vision(...)` (PC vision), qui appelle `push_vision`.
- `lib/EtatVision.py` (nouveau) : Enum des états (RECHERCHE, MISE_EN_AXE, PERDU, TRAVERSEE, ECHEC), comme AxisName.
  Envoyé par son nom dans le JSON ; `retrieve_vision()` renvoie un `EtatVision` dans le champ "etat".

Ces trois fichiers sont à déposer sur son partage (en gardant ses originaux) :

    D="/run/user/1000/gvfs/sftp:host=192.168.20.1,user=share/home/share/mini_projet_SIA/python"
    cp -p "$D/lib/MqttInterface.py" "$D/lib/MqttInterface.py.avant_vision.bak"
    cp -p "$D/tello_nn/TelloInterface.py" "$D/tello_nn/TelloInterface.py.avant_vision.bak"
    cp collegue/lib/MqttInterface.py collegue/lib/EtatVision.py "$D/lib/" && cp collegue/tello_nn/TelloInterface.py "$D/tello_nn/"

Côté PC de contrôle :

    mqtt = TelloMQTTInterface(broker_ip=..., client_id="tello_node")
    mqtt.init_mqtt_connection(subscribe_vision=True, ...)
    o = mqtt.retrieve_vision()   # {"etat": EtatVision, "present", "delta_x", "delta_z", "distance", "r_yaw", "r_z", ...} ou None
    if o is not None and o["etat"] == EtatVision.RECHERCHE: ...       # from lib.EtatVision import EtatVision
