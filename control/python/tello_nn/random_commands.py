import random
import time
import sys
from pathlib import Path

ROOT_DIR = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT_DIR))

from lib.AxisName import YAW, X, Y, Z
from tello_nn.TelloInterface import TelloInterface

tello = TelloInterface(tello_hil_ip="localhost")
tello.start_communication()


# Initial coherent starting position
x, y, z, yaw = 0, 0, 50, 0

# Maximum displacement per step to keep movement coherent
MAX_STEP_XY = 40  # cm
MAX_STEP_Z = 20   # cm
MAX_STEP_YAW = 30 # degrees

try:
    while True:
        # Generate small coherent deltas
        x += random.uniform(-MAX_STEP_XY, MAX_STEP_XY)
        y += random.uniform(-MAX_STEP_XY, MAX_STEP_XY)
        z += random.uniform(-MAX_STEP_Z, MAX_STEP_Z)
        yaw += random.uniform(-MAX_STEP_YAW, MAX_STEP_YAW)

        # Clamp strictly within boundaries:
        # (-200 < x < 200, -200 < y < 200, 10 < z < 200, 0 < yaw < 360)
        x = max(-199, min(199, round(x)))
        y = max(-199, min(199, round(y)))
        z = max(11, min(199, round(z)))
        yaw = round(yaw % 360)
        if yaw == 0:
            yaw = 1

        tello.send_command(x=x, y=y, z=z, yaw=yaw)

        # Random sleep between 1 and 6 seconds
        time.sleep(random.uniform(1.0, 6.0))

except KeyboardInterrupt:
    print("Loop stopped by user.")
