# Copyright 2026 Rudra Modi
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

"""Pure decision logic and state machine for trash_boat collector brain."""

from dataclasses import dataclass
import math
from typing import Sequence


@dataclass
class Command:
    """Velocity, collect trigger, and state command emitted by collector logic."""

    v: float
    w: float
    collect: bool
    state: str


def wrap_angle(angle: float) -> float:
    """Map angle to (-pi, pi]."""
    w = (angle + math.pi) % (2.0 * math.pi) - math.pi
    if w <= -math.pi:
        w += 2.0 * math.pi
    return float(w)


def yaw_from_quaternion(q: Sequence[float]) -> float:
    """Calculate yaw angle from (x, y, z, w) quaternion."""
    x, y, z, w = q
    siny_cosp = 2.0 * (w * z + x * y)
    cosy_cosp = 1.0 - 2.0 * (y * y + z * z)
    return float(math.atan2(siny_cosp, cosy_cosp))


class CollectorLogic:
    """Hierarchical state machine for autonomous patrol, approach, and scoop."""

    def __init__(
        self,
        control_rate: float = 20.0,
        search_speed: float = 0.8,
        approach_speed: float = 0.8,
        min_approach_speed: float = 0.15,
        k_ang: float = 1.5,
        k_lin: float = 0.5,
        w_max: float = 1.2,
        detection_timeout: float = 0.5,
        collect_fwd_min: float = 0.2,
        collect_fwd_max: float = 1.2,
        collect_lateral_max: float = 0.6,
        collect_cooldown: float = 0.5,
        canal_length: float = 60.0,
        half_width: float = 4.0,
        end_margin: float = 2.0,
        patrol_aim_distance: float = 3.0,
        bank_margin: float = 0.8,
        bank_hysteresis: float = 0.3,
        bank_speed: float = 0.3,
    ) -> None:
        self.control_rate: float = control_rate
        self.search_speed: float = search_speed
        self.approach_speed: float = approach_speed
        self.min_approach_speed: float = min_approach_speed
        self.k_ang: float = k_ang
        self.k_lin: float = k_lin
        self.w_max: float = w_max
        self.detection_timeout: float = detection_timeout
        self.collect_fwd_min: float = collect_fwd_min
        self.collect_fwd_max: float = collect_fwd_max
        self.collect_lateral_max: float = collect_lateral_max
        self.collect_cooldown: float = collect_cooldown
        self.canal_length: float = canal_length
        self.half_width: float = half_width
        self.end_margin: float = end_margin
        self.patrol_aim_distance: float = patrol_aim_distance
        self.bank_margin: float = bank_margin
        self.bank_hysteresis: float = bank_hysteresis
        self.bank_speed: float = bank_speed

        self.dir: float = 1.0
        self.in_avoid_bank: bool = False
        self.collect_until: float = 0.0

    def step(
        self,
        now: float,
        pose: tuple[float, float, float] | None,
        detections: list[tuple[float, float]],
        det_stamp: float | None,
    ) -> Command:
        """Evaluate decision logic for current tick and return motor/collect command."""
        if pose is None:
            return Command(v=0.0, w=0.0, collect=False, state='SEARCH')

        x, y, yaw = pose

        # Priority 1: AVOID_BANK
        if self.in_avoid_bank:
            if abs(y) < self.half_width - self.bank_margin - self.bank_hysteresis:
                self.in_avoid_bank = False
        else:
            if abs(y) > self.half_width - self.bank_margin:
                self.in_avoid_bank = True

        if self.in_avoid_bank:
            target_yaw = math.atan2(-y, self.patrol_aim_distance * self.dir)
            yaw_err = wrap_angle(target_yaw - yaw)
            w = max(-self.w_max, min(self.w_max, self.k_ang * yaw_err))
            v = self.bank_speed
            return Command(v=v, w=w, collect=False, state='AVOID_BANK')

        # Priority 2: COLLECT cooldown hold
        if now < self.collect_until:
            return Command(v=0.0, w=0.0, collect=False, state='COLLECT')

        # Priority 3: APPROACH
        is_fresh = (
            det_stamp is not None
            and (now - det_stamp) <= self.detection_timeout
            and len(detections) > 0
        )
        if is_fresh:
            fwd, left = detections[0]
            if (
                self.collect_fwd_min <= fwd <= self.collect_fwd_max
                and abs(left) <= self.collect_lateral_max
            ):
                self.collect_until = now + self.collect_cooldown
                return Command(v=0.0, w=0.0, collect=True, state='COLLECT')

            bearing = math.atan2(left, fwd)
            dist = math.hypot(fwd, left)
            w = max(-self.w_max, min(self.w_max, self.k_ang * bearing))
            lin = max(
                self.min_approach_speed,
                min(self.approach_speed, self.k_lin * dist),
            )
            v = lin * max(0.0, math.cos(bearing))
            return Command(v=v, w=w, collect=False, state='APPROACH')

        # Priority 4: SEARCH
        if self.dir > 0.0 and x >= self.canal_length - self.end_margin:
            self.dir = -1.0
        elif self.dir < 0.0 and x <= self.end_margin:
            self.dir = 1.0

        target_yaw = math.atan2(-y, self.patrol_aim_distance * self.dir)
        yaw_err = wrap_angle(target_yaw - yaw)
        w = max(-self.w_max, min(self.w_max, self.k_ang * yaw_err))
        v = self.search_speed
        return Command(v=v, w=w, collect=False, state='SEARCH')
