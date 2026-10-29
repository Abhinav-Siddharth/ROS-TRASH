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

"""Independent geometric checks for calibration, heading and wave attitude."""

import math

import numpy as np
import pytest

from trash_boat_vrx.projection import pixel_to_water, rotation_matrix


@pytest.mark.parametrize('pixel,expected', [
    ((200, 200), (0, 0)), ((200, 160), (1, 0)),
    ((160, 200), (0, 1)), ((240, 240), (-1, -1)),
])
def test_level_projection(pixel: tuple, expected: tuple) -> None:
    """Recover reference coordinates with a real pinhole camera."""
    result = pixel_to_water(*pixel, (240, 240, 200, 200), (20, 1, 0), (0, 0, 0, 1), 6)
    assert result == pytest.approx(expected)


def test_attitude_and_heading() -> None:
    """Reproject a known water point under combined boat roll, pitch and yaw."""
    # Arbitrary unit quaternion avoids duplicating the projection's ray formula.
    quaternion = (0.03, -0.04, math.sin(0.4), math.cos(0.4))
    rotation = rotation_matrix(quaternion)
    boat = np.array([12, 2, 0.12])
    target = np.array([14, 1, 0])
    body = rotation.T @ (target - boat)
    camera = body - np.array([0, 0, 6])
    u = 200 - 240 * camera[1] / -camera[2]
    v = 200 - 240 * camera[0] / -camera[2]
    result = pixel_to_water(u, v, (240, 240, 200, 200), boat, quaternion, 6)
    assert result == pytest.approx(body[:2])


def test_reject_bad_or_unobservable_geometry() -> None:
    """Reject invalid calibration, horizon-facing rays and out-of-range targets."""
    with pytest.raises(ValueError):
        pixel_to_water(200, 200, (0, 240, 200, 200), (0, 0, 0), (0, 0, 0, 1), 6)
    with pytest.raises(ValueError):
        rotation_matrix((0, 0, 0, 0))
    assert pixel_to_water(200, 200, (240, 240, 200, 200),
                          (0, 0, 0), (1, 0, 0, 0), 6) is None
    assert pixel_to_water(200, -500, (240, 240, 200, 200),
                          (0, 0, 0), (0, 0, 0, 1), 6) is None
