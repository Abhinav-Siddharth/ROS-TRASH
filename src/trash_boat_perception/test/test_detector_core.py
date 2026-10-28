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

"""Unit tests for detector_core pure vision functions."""

import math

import cv2
import numpy as np

from trash_boat_perception.detector_core import detect_trash, pixel_to_body


def test_pixel_to_body() -> None:
    """Test camera pixel coordinates to body frame conversion."""
    image_size = 400
    ppm = 40.0

    # Center (200, 200) -> (0.0, 0.0)
    assert pixel_to_body(200.0, 200.0, image_size, ppm) == (0.0, 0.0)

    # (200, 160) -> 1.0 m forward
    fwd, left = pixel_to_body(200.0, 160.0, image_size, ppm)
    assert math.isclose(fwd, 1.0, abs_tol=1e-5)
    assert math.isclose(left, 0.0, abs_tol=1e-5)

    # (160, 200) -> 1.0 m left
    fwd, left = pixel_to_body(160.0, 200.0, image_size, ppm)
    assert math.isclose(fwd, 0.0, abs_tol=1e-5)
    assert math.isclose(left, 1.0, abs_tol=1e-5)

    # (200, 240) -> -1.0 m forward (behind)
    fwd, left = pixel_to_body(200.0, 240.0, image_size, ppm)
    assert math.isclose(fwd, -1.0, abs_tol=1e-5)
    assert math.isclose(left, 0.0, abs_tol=1e-5)

    # (240, 200) -> -1.0 m left (right)
    fwd, left = pixel_to_body(240.0, 200.0, image_size, ppm)
    assert math.isclose(fwd, 0.0, abs_tol=1e-5)
    assert math.isclose(left, -1.0, abs_tol=1e-5)


def test_single_orange_disc() -> None:
    """Synthetic image with one orange disc yields exactly one detection within 1 px."""
    img = np.full((400, 400, 3), (120, 80, 30), dtype=np.uint8)
    cv2.circle(img, (150, 120), 7, (0, 128, 255), -1)

    dets = detect_trash(img, [5, 150, 150], [25, 255, 255], 20.0, 800.0)
    assert len(dets) == 1
    u, v = dets[0]
    assert math.hypot(u - 150.0, v - 120.0) <= 1.0


def test_background_rejection() -> None:
    """Plain water, bank green, boat triangle and text yield zero detections."""
    img = np.full((400, 400, 3), (40, 90, 60), dtype=np.uint8)
    img[100:300, :] = (120, 80, 30)

    # White boat triangle
    boat_pts = np.array([[200, 188], [194, 208], [206, 208]], dtype=np.int32)
    cv2.fillPoly(img, [boat_pts], (255, 255, 255))

    # White text
    cv2.putText(img, 'SPEED: 0.8', (20, 40), cv2.FONT_HERSHEY_SIMPLEX, 0.8, (255, 255, 255), 2)

    dets = detect_trash(img, [5, 150, 150], [25, 255, 255], 20.0, 800.0)
    assert len(dets) == 0


def test_sorted_nearest_first() -> None:
    """Two discs yield two detections sorted nearest to the boat first."""
    img = np.full((400, 400, 3), (120, 80, 30), dtype=np.uint8)
    # Boat is at (200, 200)
    # Further disc: distance 100 px
    cv2.circle(img, (200, 100), 7, (0, 128, 255), -1)
    # Nearer disc: distance 30 px
    cv2.circle(img, (200, 170), 7, (0, 128, 255), -1)

    dets = detect_trash(img, [5, 150, 150], [25, 255, 255], 20.0, 800.0)
    assert len(dets) == 2

    # First must be the nearer one at (200, 170)
    assert math.hypot(dets[0][0] - 200.0, dets[0][1] - 170.0) <= 1.0
    # Second must be the further one at (200, 100)
    assert math.hypot(dets[1][0] - 200.0, dets[1][1] - 100.0) <= 1.0


def test_small_disc_ignored() -> None:
    """A disc smaller than min_area (radius 2) is ignored."""
    img = np.full((400, 400, 3), (120, 80, 30), dtype=np.uint8)
    cv2.circle(img, (150, 120), 2, (0, 128, 255), -1)

    dets = detect_trash(img, [5, 150, 150], [25, 255, 255], 20.0, 800.0)
    assert len(dets) == 0
