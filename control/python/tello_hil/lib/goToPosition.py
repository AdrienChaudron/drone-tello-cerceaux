import select
import sys
import time

from djitellopy import Tello
from lib.AxisName import YAW, X, Y, Z
from tello_hil.lib.EtatVision import EtatVision
from tello_hil.lib.TELLO import AXIS, EVT


def go_to_position(tello: Tello):
    global VRR
    count_for_archive = 0

    def check_spacebar() -> bool:
        if select.select([sys.stdin], [], [], 0)[0]:
            return sys.stdin.read(1) == " "
        return False

    try:
        while EVT.get_tello_running_state():
            state = tello.get_current_state()
            battery = state["bat"]
            is_flying = tello.is_flying
            temperature = state["temph"]
            flight_time = tello.get_flight_time()

            # AXIS[X].add_measure(EVT.get_pv().get_delta_x() * max(0, 100 - 100 * EVT.get_pv().get_distance_to_circle()), EVT.T_sample)
            AXIS[X].add_measure(EVT.get_pv().get_delta_x(), EVT.T_sample)
            AXIS[Y].add_measure(state["pitch"], EVT.T_sample)
            AXIS[Z].add_measure(state["tof"] - 2 * (state["tof"] // 10), EVT.T_sample)
            AXIS[YAW].add_measure(state["yaw"], EVT.T_sample)

            # if EVT.get_pv().get_state() == EtatVision.MISE_EN_AXE:
            #     print("delta_x vision :", EVT.get_pv().get_delta_x(), "----- mesure en x enregistrée :", AXIS[X].get_nth_value(0), "------ erreur en x :", AXIS[X].err())

            EVT.neural_network.publish_status(
                battery=battery,
                is_flying=is_flying,
                temperature=temperature,
                flight_time=flight_time,
                tof=AXIS[Z].get_nth_value(0),
                yaw=AXIS[YAW].get_nth_value(0)
            )

            tello.send_rc_control(
                AXIS[X].get_command(EVT.T_sample),
                AXIS[Y].get_command(EVT.T_sample),
                AXIS[Z].get_command(EVT.T_sample),
                AXIS[YAW].get_command(EVT.T_sample),
            )

            if count_for_archive % 2 == 0:
                AXIS[X].log(EVT)
                AXIS[Y].log(EVT)
                AXIS[Z].log(EVT)
                AXIS[YAW].log(EVT)

            count_for_archive += 1
            VRR = AXIS[Z].err()

            if check_spacebar() or EVT.remote_deadman:
                print("\n[DEAD MAN SWITCH ACTIVATED] Space pressed. Initiating emergency land...")
                break

            time.sleep(EVT.T_sample)
    finally:
        EVT.set_tello_running_state(False)
        tello.send_rc_control(0, 0, 0, 0)
