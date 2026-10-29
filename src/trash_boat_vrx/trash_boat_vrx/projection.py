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

"""Pure calibrated projection from the rendered camera onto the water plane."""

import math
from typing import Sequence

import numpy as np


def rotation_matrix(quaternion: Sequence[float]) -> np.ndarray:
    """Return body-to-world rotation for a finite, nonzero xyzw quaternion."""
    q = np.asarray(quaternion, dtype=float)
    if q.shape != (4,) or not np.isfinite(q).all() or np.linalg.norm(q) < 1e-9:
        raise ValueError('Invalid camera orientation')
    x, y, z, w = q / np.linalg.norm(q)
    return np.array([
        [1 - 2 * (y * y + z * z), 2 * (x * y - z * w), 2 * (x * z + y * w)],
        [2 * (x * y + z * w), 1 - 2 * (x * x + z * z), 2 * (y * z - x * w)],
        [2 * (x * z - y * w), 2 * (y * z + x * w), 1 - 2 * (x * x + y * y)],
    ])


def pixel_to_water(u: float, v: float, intrinsics: Sequence[float],
                   boat_position: Sequence[float], boat_quaternion: Sequence[float],
                   camera_height: float, water_z: float = 0.0,
                   max_range: float = 12.0) -> tuple[float, float] | None:
    """
    Intersect a downward camera ray with water, returning forward/left metres.

    Camera mounting rotation is pitch +pi/2: image up points along boat +X and
    image left along boat +Y. Boat roll, pitch, height and yaw are accounted for.
    Only calibration and boat localization are used; no object locations enter.
    """
    fx, fy, cx, cy = intrinsics
    values = [u, v, fx, fy, cx, cy, camera_height, water_z, max_range, *boat_position]
    if not all(math.isfinite(x) for x in values) or min(fx, fy, camera_height, max_range) <= 0:
        raise ValueError('Invalid projection calibration')
    rotation = rotation_matrix(boat_quaternion)
    boat = np.asarray(boat_position, dtype=float)
    origin = boat + rotation @ np.array([0.0, 0.0, camera_height])
    ray = rotation @ np.array([(cy - v) / fy, (cx - u) / fx, -1.0])
    if ray[2] >= -1e-6 or origin[2] <= water_z:
        return None
    distance = (water_z - origin[2]) / ray[2]
    body = rotation.T @ (origin + distance * ray - boat)
    if math.hypot(body[0], body[1]) > max_range:
        return None
    return float(body[0]), float(body[1])
