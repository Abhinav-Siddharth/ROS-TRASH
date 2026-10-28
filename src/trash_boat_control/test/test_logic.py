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

"""Unit tests for CollectorLogic state machine and helpers."""

import math

from trash_boat_control.logic import CollectorLogic, wrap_angle, yaw_from_quaternion


def test_search_state_no_detections() -> None:
    """Test 1: No detections, pose (10,0,0): state SEARCH, v > 0, |w| < 0.05."""
    logic = CollectorLogic()
    cmd = logic.step(now=1.0, pose=(10.0, 0.0, 0.0), detections=[], det_stamp=None)
    assert cmd.state == 'SEARCH'
    assert cmd.v > 0.0
    assert abs(cmd.w) < 0.05
    assert not cmd.collect


def test_approach_straight_ahead() -> None:
    """Test 2: Detection (3.0, 0.0): APPROACH, v > 0, |w| < 0.05, collect False."""
    logic = CollectorLogic()
    cmd = logic.step(
        now=1.0,
        pose=(10.0, 0.0, 0.0),
        detections=[(3.0, 0.0)],
        det_stamp=1.0,
    )
    assert cmd.state == 'APPROACH'
    assert cmd.v > 0.0
    assert abs(cmd.w) < 0.05
    assert not cmd.collect


def test_approach_turn_left() -> None:
    """Test 3: Detection (3.0, 1.0): APPROACH and w > 0 (turn left)."""
    logic = CollectorLogic()
    cmd = logic.step(
        now=1.0,
        pose=(10.0, 0.0, 0.0),
        detections=[(3.0, 1.0)],
        det_stamp=1.0,
    )
    assert cmd.state == 'APPROACH'
    assert cmd.w > 0.0
    assert not cmd.collect


def test_collect_and_cooldown() -> None:
    """Test 4: Detection (0.8, 0.1): collect True on 1st tick, False on next ticks (COLLECT)."""
    logic = CollectorLogic()
    # First tick: scoop trigger
    cmd1 = logic.step(
        now=1.0,
        pose=(10.0, 0.0, 0.0),
        detections=[(0.8, 0.1)],
        det_stamp=1.0,
    )
    assert cmd1.collect
    assert cmd1.state == 'COLLECT'
    assert cmd1.v == 0.0
    assert cmd1.w == 0.0

    # Next tick during cooldown (dt = 0.05s)
    cmd2 = logic.step(
        now=1.05,
        pose=(10.0, 0.0, 0.0),
        detections=[(0.8, 0.1)],
        det_stamp=1.0,
    )
    assert not cmd2.collect
    assert cmd2.state == 'COLLECT'
    assert cmd2.v == 0.0
    assert cmd2.w == 0.0


def test_detection_behind() -> None:
    """Test 5: Detection behind (-2.0, 0.0): v == 0, w != 0."""
    logic = CollectorLogic()
    cmd = logic.step(
        now=1.0,
        pose=(10.0, 0.0, 0.0),
        detections=[(-2.0, 0.0)],
        det_stamp=1.0,
    )
    assert cmd.state == 'APPROACH'
    assert math.isclose(cmd.v, 0.0, abs_tol=1e-5)
    assert cmd.w != 0.0


def test_avoid_bank() -> None:
    """Test 6: Pose (20, 3.5, 0): state AVOID_BANK, w < 0, v == bank_speed."""
    logic = CollectorLogic()
    cmd = logic.step(now=1.0, pose=(20.0, 3.5, 0.0), detections=[], det_stamp=None)
    assert cmd.state == 'AVOID_BANK'
    assert cmd.w < 0.0
    assert math.isclose(cmd.v, logic.bank_speed, abs_tol=1e-5)


def test_patrol_flip_at_end() -> None:
    """Test 7: Pose (59, 0, 0) with dir +1: patrol direction flips upstream."""
    logic = CollectorLogic()
    assert logic.dir == 1.0
    cmd = logic.step(now=1.0, pose=(59.0, 0.0, 0.0), detections=[], det_stamp=None)
    assert logic.dir == -1.0
    assert cmd.state == 'SEARCH'
    assert cmd.w != 0.0


def test_stale_detection_ignored() -> None:
    """Test 8: Detections older than detection_timeout are ignored (state SEARCH)."""
    logic = CollectorLogic()
    # det_stamp is 1.0 s old (> detection_timeout 0.5 s)
    cmd = logic.step(
        now=2.0,
        pose=(10.0, 0.0, 0.0),
        detections=[(2.0, 0.0)],
        det_stamp=1.0,
    )
    assert cmd.state == 'SEARCH'


def test_helpers_wrap_angle_and_yaw_from_quaternion() -> None:
    """Test 9: wrap_angle and yaw_from_quaternion basic cases."""
    # wrap_angle
    assert math.isclose(wrap_angle(0.0), 0.0, abs_tol=1e-5)
    assert math.isclose(wrap_angle(math.pi), math.pi, abs_tol=1e-5)
    assert math.isclose(wrap_angle(-math.pi), math.pi, abs_tol=1e-5)
    assert math.isclose(wrap_angle(3.0 * math.pi), math.pi, abs_tol=1e-5)
    assert math.isclose(wrap_angle(-3.0 * math.pi), math.pi, abs_tol=1e-5)
    assert math.isclose(wrap_angle(math.pi / 2.0), math.pi / 2.0, abs_tol=1e-5)

    # yaw_from_quaternion
    # Identity: (0, 0, 0, 1) -> 0.0
    assert math.isclose(yaw_from_quaternion((0.0, 0.0, 0.0, 1.0)), 0.0, abs_tol=1e-5)

    # 90 degrees CCW: z = sin(pi/4), w = cos(pi/4)
    sin45 = math.sin(math.pi / 4.0)
    cos45 = math.cos(math.pi / 4.0)
    assert math.isclose(
        yaw_from_quaternion((0.0, 0.0, sin45, cos45)),
        math.pi / 2.0,
        abs_tol=1e-5,
    )
