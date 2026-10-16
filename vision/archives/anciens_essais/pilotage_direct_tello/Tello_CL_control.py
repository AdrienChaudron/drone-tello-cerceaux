import concurrent.futures
import queue
import threading
import time
from enum import Enum
from typing import Optional

from djitellopy import Tello


class ControllerType(Enum):
    P = 1
    PD = 2
    PI = 3
    PID = 4

class Environment:
    T_sample: float
    start_time: float
    log_folder: str

    def __init__(self, T_sample: float, log_folder: str) -> None:
        self.T_sample = T_sample
        self.start_time = time.time()
        self.log_folder = log_folder

class AxisLogger:
    """Thread-safe background file logger for an individual control axis."""

    def __init__(self, filename: str) -> None:
        self.filename: str = filename
        self._queue: queue.Queue[Optional[tuple[float, float, float, float]]] = queue.Queue()
        self._thread: threading.Thread = threading.Thread(target=self._worker, daemon=True)
        self._is_running: bool = False

    def start(self) -> None:
        """Starts the background worker thread and writes the header."""
        self._is_running = True
        self._thread.start()

    def push(self, timestamp: float, target: float, command: float, measure: float) -> None:
        """Non-blocking producer call: pushes a state tuple into the FIFO queue."""
        if self._is_running:
            self._queue.put((timestamp, target, command, measure))

    def stop(self) -> None:
        """Flushes remaining queued items and shuts down the worker thread cleanly."""
        if not self._is_running:
            return
        self._is_running = False
        self._queue.put(None)  # Sentinel/poison-pill to stop worker
        self._thread.join()

    def _worker(self) -> None:
        """Consumer worker loop running in the background."""
        with open(self.filename, mode="w", encoding="utf-8") as f:
            while True:
                item = self._queue.get()
                if item is None:
                    self._queue.task_done()
                    break

                t, target, cmd, measure = item
                # Format: timestamp target command measure
                f.write(f"{t:.4f} {target:.2f} {cmd:.2f} {measure:.2f}\n")
                self._queue.task_done

class AxisControl:
    _reference: int
    _values: list[int]
    _last_integral: float
    _last_err: int
    CONTROLLING: bool
    CONTROLLING_TYPE: ControllerType
    K_p: float
    K_d: float
    K_i: float
    file_name: str
    name: str
    _logger: AxisLogger

    def __init__(self, CONTROLLING: bool, CONTROLLING_TYPE: ControllerType, K_p: float, K_d: float, K_i: float, name: str, environment: Environment) -> None:
        self._values = [0, 0, 0, 0]
        self._last_err = 0
        self._last_integral = 0
        self.CONTROLLING = CONTROLLING
        self.CONTROLLING_TYPE = CONTROLLING_TYPE
        self.K_p = K_p
        self.K_d = K_d
        self.K_i = K_i
        self.name = name
        filename = f"{environment.log_folder}/log_{self.name.lower()}.txt"
        self._logger = AxisLogger(filename)

    def set_reference(self, reference: int) -> None:
        self._reference = reference

    def get_reference(self) -> int:
        return self._reference

    def add_measure(self, measure: int, T_sample: float) -> None:
        self._last_integral = self.get_integral(T_sample)
        self._last_err = self.err()
        self._values.insert(0, measure)
        self._values.pop()

    def get_nth_value(self, n: int) -> int:
        if n < 0 or n > 3:
            raise IndexError("Only 4 values are accessible")
        return self._values[n]

    def err(self) -> int:
        return self._reference - self._values[0]

    def get_derivation(self, T_sample: float) -> float:
        return (self._values[0] - self._values[1]) / T_sample

    def get_integral(self, T_sample: float) -> float:
        return self._last_integral + T_sample * (self._last_err + self.err()) / 2

    def get_command(self, T_sample: float) -> int:
        command = 0

        def saturation(val, min, max):
            val = max if val > max else min if val < min else val
            return val

        if self.CONTROLLING == True:
            match self.CONTROLLING_TYPE:
                case ControllerType.P:
                    command = self.K_p * self.err()
                case ControllerType.PD:
                    command = self.K_p * self.err() - self.K_d * self.get_derivation(T_sample)
                case ControllerType.PI:
                    command = self.K_p * self.err() + self.K_i * self.get_integral(T_sample)
                case ControllerType.PID:
                    command = self.K_p * self.err() - self.K_d * self.get_derivation(T_sample) + self.K_i * self.get_integral(T_sample)

            command = int(saturation(command, -100, 100))
            return command
        else:
            command = self.get_reference()
            return command

    def get_scheme(self) -> str:
        if self.CONTROLLING == False:
            return r"""
                            === Open Loop ===

                   U(s) = R(s)        +-------+     Y(s)
                  ------------------->| AXIS  |------>
                                      +-------+
            """
        else:
            match self.CONTROLLING_TYPE:
                case ControllerType.P:
                    return r"""
                                        === P corrected closed loop ===

                                  +---+    E(s)    +----+    U(s)    +------+
                        R(s) ---->|+  |----------->| Kp |----------->| AXIS |----+----> Y(s)
                                  |   |            +----+            +------+    |
                               +->|-  |                                          |
                               |  +---+                                          |
                               |                                                 |
                               +-------------------------------------------------+
                    """
                case ControllerType.PD:
                    return r"""
                                                === PD corrected closed loop ===

                                  +---+    E(s)    +----+           +---+    U(s)    +------+
                        R(s) ---->|+  |----------->| Kp |---------->|+  |----------->| AXIS |----+----> Y(s)
                                  |   |            +----+        +->|-  |            +------+    |
                               +->|-  |                          |  +---+                        |
                               |  +---+                          |                               |
                               |                                 |     +------+                  |
                               |                                 +-----| Kd*s |<-----------------+
                               |                                       +------+                  |
                               +-----------------------------------------------------------------+
                    """
                case ControllerType.PI:
                    return r"""
                                                === PI corrected closed loop ===

                                                        +--------+
                                                   +--->| Ki / s |----+
                                                   |    +--------+    |
                                  +---+    E(s)    |                  v       U(s)    +------+
                        R(s) ---->|+  |------------+                 (+)------------->| AXIS |----+----> Y(s)
                                  |   |            |    +--------+    ^               +------+    |
                               +->|-  |            +--->|   Kp   |----+                           |
                               |  +---+                 +--------+                                |
                               |                                                                  |
                               +------------------------------------------------------------------+
                    """
                case ControllerType.PID:
                    return r"""
                                                === PID corrected closed loop ===

                                                       +--------+
                                                  +--->| Ki / s |----+
                                                  |    +--------+    |
                                  +---+    E(s)   |                  v    +---+    U(s)    +------+
                        R(s) ---->|+  |-----------+                 (+)-->|+  |----------->| AXIS |----+----> Y(s)
                                  |   |           |    +--------+    ^ +->|-  |            +------+    |
                               +->|-  |           +--->|   Kp   |----+ |  +---+                        |
                               |  +---+                +--------+      |                               |
                               |                                       |    +------+                   |
                               |                                       +----| Kd*s |<------------------+
                               |                                            +------+                   |
                               +-----------------------------------------------------------------------+
                    """

    def print_info(self) -> None:
        green = "\033[92m"
        white = "\033[97m"
        reset = "\033[0m"

        print(self.get_scheme())
        print("\n" * 2)
        print(f"┌─ ⚙ Parameters ──────────────────┐")
        print(f"│  {green}Kₚ{reset} : {white}{self.K_p:<24}{reset}│")
        print(f"│  {green}Kᵢ{reset} : {white}{self.K_i:<24}{reset}│")
        print(f"│  {green}K_d{reset} : {white}{self.K_d:<24}{reset}│")
        print(f"└─────────────────────────────────┘")

    @property
    def logger(self) -> AxisLogger:
        """Access the underlying AxisLogger instance."""
        return self._logger

    def log(self, environment: Environment) -> None:
        """
        Logs current state in the format: timestamp - target - command - measure.
        """
        current_time = time.time() - environment.start_time
        self._logger.push(
            timestamp=current_time,
            target=self._reference,
            command=self.get_command(environment.T_sample),
            measure=self._values[0]
        )


#################################
##         Parametres          ##
#################################

EVT = Environment(
    T_sample = .015,
    log_folder = "./tello_logs"
)

AXIS = {
    "X" : AxisControl(
        name="X",
        CONTROLLING = False,
        CONTROLLING_TYPE = ControllerType.PD,
        K_p = 1.32,
        K_d = 0.8888,
        K_i = 0,
        environment = EVT
    ),
    "Y" : AxisControl(
        name="Y",
        CONTROLLING = False,
        CONTROLLING_TYPE = ControllerType.P,
        K_p = 1,
        K_d = 0,
        K_i = 0,
        environment = EVT
    ),
    "Z" : AxisControl(
        name="Z",
        CONTROLLING = True,
        CONTROLLING_TYPE = ControllerType.P,
        K_p = 1,
        K_d = 0,
        K_i = 0,
        environment = EVT
    ),
    "YAW" : AxisControl(
        name="YAW",
        CONTROLLING = True,
        CONTROLLING_TYPE = ControllerType.P,
        K_p = 2.0,
        K_d = 0,
        K_i = 0,
        environment = EVT
    ),
}

WaypointDuration = 100 * EVT.T_sample
seuil = 5

VRR = 100


#################################
##          Functions          ##
#################################
def go_to_position(waypoints):
    global VRR

    for waypoint in waypoints:
        AXIS["X"].set_reference(waypoint[0])
        AXIS["Y"].set_reference(waypoint[1])
        AXIS["Z"].set_reference(waypoint[2])
        AXIS["YAW"].set_reference(waypoint[3])

        tic_count = int(WaypointDuration / EVT.T_sample)

        for _i in range(tic_count):

            AXIS["X"].add_measure(tello.get_roll(), EVT.T_sample)
            AXIS["Y"].add_measure(tello.get_pitch(), EVT.T_sample)
            AXIS["Z"].add_measure(tello.get_distance_tof(), EVT.T_sample)
            AXIS["YAW"].add_measure(tello.get_yaw(), EVT.T_sample)

            tello.send_rc_control(
                AXIS["X"].get_command(EVT.T_sample),
                AXIS["Y"].get_command(EVT.T_sample),
                AXIS["Z"].get_command(EVT.T_sample),
                AXIS["YAW"].get_command(EVT.T_sample),
            )

            AXIS["X"].log(EVT)
            AXIS["Y"].log(EVT)
            AXIS["Z"].log(EVT)
            AXIS["YAW"].log(EVT)

            VRR = AXIS["Z"].err()

            time.sleep(EVT.T_sample)


    tello.send_rc_control(0, 0, 0, 0)

##############################
##          Control         ##
##############################


if __name__ == "__main__":
    tello = Tello()
    tello.connect()

    print("battery: " + str(tello.get_battery()) + "%")

    AXIS["X"]._logger.start()
    AXIS["Y"]._logger.start()
    AXIS["Z"]._logger.start()
    AXIS["YAW"]._logger.start()

    time.sleep(3)

    ######################################
    ##      Open Loop - Beginning       ##
    with concurrent.futures.ThreadPoolExecutor() as executor:
        start_time = time.time()
        Registering = True

        tello.takeoff()
        time.sleep(3)

        z_offset = tello.get_distance_tof()
        range_max_z = 80
        range_min_z = -50

        range_max_yaw = 30
        range_min_yaw = -30

        range_max_x = 100
        range_min_x = -100

        range_max_y = 10
        range_min_y = -10

        # Consigne sous la forme x, y, z, yaw
        waypoints = [
            [0, 0, z_offset, 0],
            [0, 0, z_offset + range_max_z, 0],
            [range_max_x / 2, 0, z_offset + range_max_z, 0],
            [range_max_x, 0, z_offset + range_max_z, 0],
            [0, 0, z_offset + range_max_z, 0],
            [range_min_x / 2, 0, z_offset + range_max_z, 0],
            [range_min_x, 0, z_offset + range_max_z, 0],
            [0, 0, z_offset + range_max_z, 0],
            [range_max_x / 2, 0, z_offset + range_max_z, 0],
            [range_max_x, 0, z_offset + range_max_z, 0],
            [0, 0, z_offset + range_max_z, 0],
            [range_min_x / 2, 0, z_offset + range_max_z, 0],
            [range_min_x, 0, z_offset + range_max_z, 0],
            [0, 0, z_offset + range_max_z, 0],
            [range_max_x / 2, 0, z_offset + range_max_z, 0],
            [range_max_x, 0, z_offset + range_max_z, 0],
            [0, 0, z_offset + range_max_z, 0],
            [range_min_x / 2, 0, z_offset + range_max_z, 0],
            [range_min_x, 0, z_offset + range_max_z, 0],
            [0, 0, z_offset + range_max_z, 0],
            [range_max_x / 2, 0, z_offset + range_max_z, 0],
            [range_max_x, 0, z_offset + range_max_z, 0],
            [0, 0, z_offset + range_max_z, 0],
            [range_min_x / 2, 0, z_offset + range_max_z, 0],
            [range_min_x, 0, z_offset + range_max_z, 0],
            [0, 0, z_offset + range_max_z, 0],
            [0, 0, z_offset, 0],
        ]

        go_to_position(waypoints)

        time.sleep(2)

        AXIS["X"]._logger.stop()
        AXIS["Y"]._logger.stop()
        AXIS["Z"]._logger.stop()
        AXIS["YAW"]._logger.stop()

        tello.land()
        Registering = False
    ##      Open Loop - End             ##
    ######################################
