from lib.AxisName import YAW, X, Y, Z
from tello_hil.lib.AxisControl import AxisControl
from tello_hil.lib.ControllerType import ControllerType
from tello_hil.lib.Environment import Environment

EVT = Environment(
    T_sample = .015,
    log_folder = "./tello_logs"
)

AXIS = {
    X : AxisControl(
        name=X,                                 # Pour l'asservissement en X, le cas est particulier :
        CONTROLLING = False,                    #   On n'asservit pas x par rapport à une mesure de x
        CONTROLLING_TYPE = ControllerType.PD,   #   car obtenir une mesure précise pour cette grandeur
        K_p = 0.262,                            #   était trop difficile et ne servait à rien pour le
        K_d = 0.8663,                           #   cahier des charges.
        K_i = 0,                                #   A la place, il asservit l'offset en width du centre
        environment = EVT,                      #   cerceau - centre image. Le modèle est dans le simulink
        max_value=100,                          #   SYS_CL_X_ref.slx.
        min_value=-100
    ),
    Y : AxisControl(
        name=Y,                                 # Y reste non asservi (en BO).
        CONTROLLING = False,
        CONTROLLING_TYPE = ControllerType.P,
        K_p = 1,
        K_d = 0,
        K_i = 0,
        environment = EVT,
        max_value=40,
        min_value=-40
    ),
    Z : AxisControl(
        name=Z,
        CONTROLLING = True,
        CONTROLLING_TYPE = ControllerType.P,
        K_p = 1,
        K_d = 0,
        K_i = 0,
        environment = EVT,
        max_value=200,
        min_value=-0
    ),
    YAW : AxisControl(
        name=YAW,
        CONTROLLING = True,
        CONTROLLING_TYPE = ControllerType.P,
        K_p = 2.0,
        K_d = 0,
        K_i = 0,
        environment = EVT,
        max_value=360,
        min_value=-360
    ),
}
