import random
import select
import sys
import termios
import threading
import time
import tty
from pathlib import Path

ROOT_DIR = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT_DIR))

from lib.AxisName import YAW, X, Y, Z
from lib.MqttInterface import TelloMQTTInterface
from tello_hil.lib.Environment import Environment
from tello_hil.lib.TELLO import AXIS, EVT

IS_FLYING = False
BATTERY = 80 + random.randint(0, 15)

def loop_fetch_references(environment: Environment, status_interval: float = 1.0):
    """Worker Thread: Pulls command targets from MQTT and updates axis references."""
    global BATTERY

    last_status_time = 0.0
    first_time = time.time()

    while environment.get_tello_running_state():
        references = environment.neural_network.retrieve_command(block=True, timeout=0.5)

        if references is not None:
            AXIS[X].set_reference(references[X.name])
            AXIS[Y].set_reference(references[Y.name])
            AXIS[Z].set_reference(references[Z.name])
            AXIS[YAW].set_reference(references[YAW.name])

            if references[X.name] == -69 and references[Y.name] == -69 and references[Z.name] == -69 and references[YAW.name] == -69:
                EVT.remote_deadman = True

        current_time = time.time()
        if current_time - last_status_time >= status_interval:
            try:
                temperature = random.randint(1, 10) + 30
                flight_time = int(current_time - first_time)
                BATTERY -= random.randint(0, 1)

                environment.neural_network.publish_status(
                    battery=BATTERY,
                    is_flying=IS_FLYING,
                    temperature=temperature,
                    flight_time=flight_time,
                    tof=AXIS[Z].get_nth_value(0),
                    yaw=AXIS[YAW].get_nth_value(0)
                )
                last_status_time = current_time
            except Exception as e:
                # Prevents loop termination if a telemetry frame is missed
                pass

        time.sleep(EVT.T_sample)



def go_to_position_sim(environment: Environment, alpha: float = 0.008, noise_std: float = 0.5):
    """
    Simulation Loop:
    - Moves smoothly towards target references (first-order lag: alpha).
    - Adds small random noise to simulate real-world sensor/drone inaccuracy.
    - Archives measurements back to MQTT for each axis at each sampling period.
    """
    environment.set_tello_running_state(True)

    # Initial state values for the simulated drone
    simulated_state = {
        X: 0.0,
        Y: 0.0,
        Z: 100.0,   # Simulated initial hover altitude (e.g. 100 cm)
        YAW: 0.0,
    }

    def check_spacebar() -> bool:
        """Dead man's switch: Checks if space was pressed without blocking."""
        if select.select([sys.stdin], [], [], 0)[0]:
            return sys.stdin.read(1) == " "
        return False

    print("\n[SIMULATOR RUNNING] Press [SPACE] to stop simulation...\n")

    try:
        while environment.get_tello_running_state():
            current_timestamp = time.time()

            for axis_name in [X, Y, Z, YAW]:
                axis_obj = AXIS[axis_name]
                ref = axis_obj.get_reference()

                # 1. First-order dynamic step towards target
                simulated_state[axis_name] += alpha * (ref - simulated_state[axis_name])

                # 2. Add realistic random sensor/wind noise
                noise = random.gauss(0, noise_std)
                measured_val = int(simulated_state[axis_name] + noise)

                # 3. Feed measure into axis controller & compute command
                axis_obj.add_measure(measured_val, EVT.T_sample)
                cmd_corrected = axis_obj.get_command(EVT.T_sample)

                # 4. Log locally
                axis_obj.log(EVT)

                # 5. Archive telemetry back to MQTT (axis topic: tello/archive/<axis_name>)
                environment.neural_network.archive_sys_result(
                    axis_id=axis_name,
                    timestamp=current_timestamp,
                    cmd_ref=ref,
                    cmd_corr=cmd_corrected,
                    measure=measured_val,
                )

            # Check dead man switch
            if check_spacebar() or  EVT.remote_deadman:
                print("\n[DEAD MAN SWITCH ACTIVATED] Space pressed. Stopping simulation...")
                break

            if BATTERY < 1:
                print("\n Battery low ! Quitting...")
                break

            time.sleep(EVT.T_sample)

    finally:
        environment.set_tello_running_state(False)


def tello_sim(broker_ip: str = "localhost"):
    """Entry point simulating the Tello drone without needing physical hardware."""
    global IS_FLYING, BATTERY

    # 1. Initialize MQTT interface for simulation machine
    EVT.neural_network = TelloMQTTInterface(broker_ip=broker_ip, client_id="tello_sim")

    # Subscribe to commands from Machine 1 (Neural Network)
    EVT.neural_network.init_mqtt_connection(subscribe_commands=True, subscribe_archive=False)

    # 2. Setup cbreak terminal mode for dead man switch key detection
    old_termios_settings = termios.tcgetattr(sys.stdin)
    tty.setcbreak(sys.stdin.fileno())

    # 3. Start loggers
    IS_FLYING = True
    AXIS[X]._logger.start()
    AXIS[Y]._logger.start()
    AXIS[Z]._logger.start()
    AXIS[YAW]._logger.start()

    try:
        # 4. Launch Thread 1: Reference consumer from MQTT
        EVT.set_tello_running_state(True)
        mqtt_worker_thread = threading.Thread(
            target=loop_fetch_references,
            args=(EVT,),
            daemon=True
        )
        mqtt_worker_thread.start()

        # 5. Launch Simulation & Archive loop on main thread
        go_to_position_sim(EVT)

    finally:
        # 6. Cleanup terminal, MQTT connection, and loggers
        termios.tcsetattr(sys.stdin, termios.TCSADRAIN, old_termios_settings)

        IS_FLYING = False
        EVT.neural_network.end_mqtt_connection()
        AXIS[X]._logger.stop()
        AXIS[Y]._logger.stop()
        AXIS[Z]._logger.stop()
        AXIS[YAW]._logger.stop()
        print("[SIMULATOR SHUTDOWN] Resources cleaned up successfully.")


if __name__ == "__main__":
    tello_sim(broker_ip="localhost")
