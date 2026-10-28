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

"""Pure computer-vision logic for detecting floating trash blobs."""

from typing import Sequence

import cv2
import numpy as np


def pixel_to_body(
    u: float, v: float, image_size: int, pixels_per_meter: float
) -> tuple[float, float]:
    """Return (fwd, left) in metres in the boat body frame."""
    fwd = (image_size / 2.0 - v) / pixels_per_meter
    left = (image_size / 2.0 - u) / pixels_per_meter
    return (float(fwd), float(left))


def detect_trash(
    bgr: np.ndarray,
    hsv_lower: Sequence[int],
    hsv_upper: Sequence[int],
    min_area: float,
    max_area: float,
) -> list[tuple[float, float]]:
    """Return pixel centroids (u, v) of orange blobs sorted nearest to boat center first."""
    hsv = cv2.cvtColor(bgr, cv2.COLOR_BGR2HSV)
    lower = np.array(hsv_lower, dtype=np.uint8)
    upper = np.array(hsv_upper, dtype=np.uint8)
    mask = cv2.inRange(hsv, lower, upper)

    kernel = np.ones((3, 3), np.uint8)
    mask = cv2.morphologyEx(mask, cv2.MORPH_OPEN, kernel, iterations=1)

    contours, _ = cv2.findContours(mask, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)

    centroids: list[tuple[float, float]] = []
    for cnt in contours:
        area = cv2.contourArea(cnt)
        if not (min_area <= area <= max_area):
            continue

        m = cv2.moments(cnt)
        if m['m00'] == 0.0:
            continue

        u = float(m['m10'] / m['m00'])
        v = float(m['m01'] / m['m00'])
        centroids.append((u, v))

    # Sort ascending by distance from the boat located at image center
    cx = bgr.shape[1] / 2.0
    cy = bgr.shape[0] / 2.0
    centroids.sort(key=lambda uv: (uv[0] - cx) ** 2 + (uv[1] - cy) ** 2)

    return centroids
