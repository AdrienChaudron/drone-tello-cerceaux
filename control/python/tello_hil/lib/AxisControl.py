import time

from lib.AxisName import YAW, AxisName
from tello_hil.lib.AxisLogger import AxisLogger
from tello_hil.lib.ControllerType import ControllerType
from tello_hil.lib.Environment import Environment


class AxisControl:
    _reference: float
    _values: list[float]
    _last_integral: float
    _last_err: float
    CONTROLLING: bool
    CONTROLLING_TYPE: ControllerType
    K_p: float
    K_d: float
    K_i: float
    file_name: str
    name: AxisName
    _logger: AxisLogger
    _max_value: int
    _min_value: int
    current_speed: int

    def __init__(self, CONTROLLING: bool, CONTROLLING_TYPE: ControllerType, K_p: float, K_d: float, K_i: float, name: AxisName, environment: Environment, max_value: int, min_value: int) -> None:
        self._values = [0, 0, 0, 0]
        self._last_err = 0
        self._last_integral = 0
        self.CONTROLLING = CONTROLLING
        self.CONTROLLING_TYPE = CONTROLLING_TYPE
        self.K_p = K_p
        self.K_d = K_d
        self.K_i = K_i
        self.name = name
        filename = f"{environment.log_folder}/log_{self.name.name.lower()}.txt"
        self._logger = AxisLogger(filename)
        self._reference = 0
        self._min_value = min_value
        self._max_value = max_value
        self.current_speed = 0

    def set_reference(self, reference: float) -> None:
        if reference > self._max_value:
            self._reference = self._max_value
        elif reference < self._min_value:
            self._reference = self._min_value
        else:
            self._reference = reference

    def get_reference(self) -> float:
        return self._reference

    def add_measure(self, measure: float, T_sample: float) -> None:
        self._last_integral = self.get_integral(T_sample)
        self._last_err = self.err()
        self._values.insert(0, measure)
        self._values.pop()

    def set_speed(self, speed: int) -> None:
        self.current_speed = speed

    def get_nth_value(self, n: int) -> float:
        if n < 0 or n > 3:
            raise IndexError("Only 4 values are accessible")
        return self._values[n]

    def err(self) -> float:
        e = self._reference - self._values[0]
        if self.name == YAW:
            e = (e + 180) % 360 - 180
        return e

    def get_derivation(self, T_sample: float) -> float:
        return (self._values[0] - self._values[1]) / T_sample

    def get_integral(self, T_sample: float) -> float:
        return self._last_integral + T_sample * (self._last_err + self.err()) / 2

    def get_command(self, T_sample: float) -> int:
        command: int = 0

        def saturation(val, min, max):
            val = max if val > max else min if val < min else val
            return val

        if self.CONTROLLING == True:
            match self.CONTROLLING_TYPE:
                case ControllerType.P:
                    command = int(
                        self.K_p * self.err()
                    )
                case ControllerType.PD:
                    command = int(
                        self.K_p * self.err() - self.K_d * self.get_derivation(T_sample)
                    )
                case ControllerType.PI:
                    command = int(
                        self.K_p * self.err() + self.K_i * self.get_integral(T_sample)
                    )
                case ControllerType.PID:
                    command = int(
                        self.K_p * self.err() - self.K_d * self.get_derivation(T_sample) + self.K_i * self.get_integral(T_sample)
                    )

            command = int(saturation(command, -100, 100))
            return command
        else:
            command = int(self.get_reference())
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

        environment.neural_network.archive_sys_result(
            axis_id=self.name,
            timestamp=current_time,
            cmd_ref=self._reference,
            cmd_corr=self.get_command(environment.T_sample),
            measure=self._values[0]
        )

        self._logger.push(
            timestamp=current_time,
            target=self._reference,
            command=self.get_command(environment.T_sample),
            measure=self._values[0],
            speed=self.current_speed
        )
