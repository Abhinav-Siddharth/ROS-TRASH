# Copyright 2026 Abhinav Siddharth
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#     http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.

"""Pure feedback and differential mixing for force-driven twin thrusters."""

from dataclasses import dataclass
import math


@dataclass(frozen=True)
class ThrusterConfig:
    """Declared controller gains in SI units; geometry matches the SDF craft."""

    arm: float = 0.65
    max_thrust: float = 50.0
    max_speed: float = 0.8
    max_yaw_rate: float = 1.2
    surge_drag: float = 20.0
    yaw_drag: float = 10.0
    surge_gain: float = 70.0
    yaw_gain: float = 50.0
    command_timeout: float = 0.5
    odometry_timeout: float = 0.5

    def validate(self) -> None:
        """Reject nonfinite, nonpositive control gains and limits."""
        if not all(math.isfinite(value) and value > 0 for value in vars(self).values()):
            raise ValueError('Thruster gains, geometry, limits and timeouts must be positive')


def thruster_forces(now: float, target: tuple[float, float] | None,
                    target_stamp: float | None, velocity: tuple[float, float] | None,
                    velocity_stamp: float | None,
                    config: ThrusterConfig) -> tuple[float, float]:
    """Return port/starboard newtons; missing or stale input yields zero force."""
    if target is None or velocity is None or target_stamp is None or velocity_stamp is None:
        return 0.0, 0.0
    values = [now, *target, target_stamp, *velocity, velocity_stamp]
    if not all(math.isfinite(value) for value in values):
        return 0.0, 0.0
    if not (0 <= now - target_stamp <= config.command_timeout
            and 0 <= now - velocity_stamp <= config.odometry_timeout):
        return 0.0, 0.0
    v = max(-config.max_speed, min(config.max_speed, target[0]))
    w = max(-config.max_yaw_rate, min(config.max_yaw_rate, target[1]))
    force = config.surge_drag * v + config.surge_gain * (v - velocity[0])
    torque = config.yaw_drag * w + config.yaw_gain * (w - velocity[1])
    left = (force - torque / config.arm) / 2
    right = (force + torque / config.arm) / 2
    # Preserve the requested force/torque ratio when actuator limits are reached.
    scale = max(1.0, abs(left) / config.max_thrust, abs(right) / config.max_thrust)
    return left / scale, right / scale
