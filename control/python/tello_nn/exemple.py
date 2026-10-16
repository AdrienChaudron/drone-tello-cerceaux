# yo bg, en gros, dans ton code, t'auras deux manières d'intéragir avec le tello

# Dans un premier temps, faudra que t'importes TelloInterface et le nom des axes
from lib.AxisName import YAW, X, Y, Z
from TelloInterface import TelloInterface

# C'est cette classe qui te permettra d'intéragir avec le tello par le biais de mon ordinateur
# Qui dit objet dit instantiation

tello = TelloInterface(tello_hil_ip="10.10.10.10")
tello.start_communication()

# Il faudra remplacer l'ip ci-présente par l'IP de mon ordinateur quand on sera sur l'hotspot de mon ordinateur
# Elle sera peut-être amenée à changer si jamais je déconnecte le hotspot pour me connecter à internet sur mon ordinateur
# Parce que quand je suis sur le hotspot, bah j'ai pas accès à Gemini ou Claude, donc je sers à rien mdrrrr
#
# Tout ça pour dire que tu dois garder cette ligne dans un endroit accessible

# Ensuite, tu peux envoyer un jeux de coordonnées consigne au tello avec
tello.send_command(
    x=0,
    y=0,
    z=0,
    yaw=0
)
# C'est des valeurs d'exemples à la con ici. Bien sûr, tu remplaces par ce que ton réseau de neuronnes à trouver
# x et y sont régulés, c'est donc les coordonnées dans l'espace et pas des puissances moteurs

# Tu peux ensuite récupérer les mesures du drone avec
tello.get_measures(Z)
tello.get_measures(Y)
# ...

# T'as capté le délire


# Une fois que t'as fini, tu clôts la comm avec
tello.end_communication()
# Ça ne fait pas aterrir le drone vu que tu m'as demandé de le faire par deadman
# Faudra que tu retapes tello.start_communication() pour pouvoir de nouveau communiquer
