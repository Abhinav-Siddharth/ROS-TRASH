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

"""Test safe shoreline approaches without compromising true visual scooping."""

import math

import pytest

from trash_boat_control.logic import CollectorLogic
from trash_boat_vrx.marine_logic import MarineCollectorLogic


def test_brake_and_align_beside_shore() -> None:
    """At a safe waypoint, face shoreline trash without driving into the bank."""
    logic = MarineCollectorLogic(CollectorLogic(bank_margin=1.4))
    command = logic.step(1, (20, 2.2, 0), [(0.1, 1.0)], 1)
    assert command.state == 'APPROACH'
    assert command.v == 0 and command.w > 0 and not command.collect


def test_waypoint_never_triggers_false_collection() -> None:
    """A waypoint under the scoop cannot substitute for the actual visual target."""
    logic = MarineCollectorLogic(CollectorLogic(bank_margin=1.4))
    command = logic.step(1, (20, 2.2, 0), [(0.2, 1.0)], 1)
    assert not command.collect
    command = logic.step(2, (20, 2.2, math.pi / 2), [(1.0, -0.2)], 2)
    assert command.collect
    command = logic.step(2.1, (20, 2.2, math.pi / 2), [(1.0, -0.2)], 2.1)
    assert not command.collect and command.state == 'COLLECT'


def test_interior_and_priorities_preserved() -> None:
    """Keep direct interior approach, missing-pose stop, stale search and avoidance."""
    logic = MarineCollectorLogic(CollectorLogic(bank_margin=1.4))
    assert logic.step(1, None, [], None).v == 0
    command = logic.step(1, (20, 0, 0), [(3, 1)], 1)
    assert command.v > 0 and command.w > 0
    assert logic.step(2, (20, 0, 0), [(3, 1)], 1).state == 'SEARCH'
    assert logic.step(3, (20, 3, 0), [(0.8, 0)], 3).state == 'AVOID_BANK'


def test_final_dock_and_retreat_for_displaced_trash() -> None:
    """Reach a bank-displaced real target, then back away before the next turn."""
    logic = MarineCollectorLogic(CollectorLogic())
    # Arrive at the staging waypoint and face the detected shoreline target.
    command = logic.step(1, (20, 2.2, 0), [(0.0, 1.6)], 1)
    assert command.v == 0 and command.w > 0 and logic.docking
    command = logic.step(2, (20, 2.2, math.pi / 2), [(1.6, 0)], 2)
    assert command.v == 0.3 and command.w == 0 and not command.collect
    command = logic.step(3, (20, 2.65, math.pi / 2), [(1.15, 0)], 3)
    assert command.collect and logic.retreating
    assert logic.step(3.1, (20, 2.65, math.pi / 2), [], None).state == 'COLLECT'
    command = logic.step(4, (20, 2.65, math.pi / 2), [], None)
    assert command.v < 0 and command.w == 0
    command = logic.step(5, (20, 2.1, math.pi / 2), [], None)
    assert not logic.retreating and command.state == 'SEARCH'


@pytest.mark.parametrize('pose', [
    (42.0, -2.65, 0.1), (42.0, 2.65, -0.1),
    (42.0, -2.65, -0.1), (42.0, 2.65, 0.1),
    (58.8, 0.0, 0.0), (1.2, 0.0, math.pi),
])
def test_recovery_reaches_corridor_for_either_collection_heading(pose: tuple) -> None:
    """Losing sight after collection must never reverse an inward-facing hull outward."""
    logic = MarineCollectorLogic(CollectorLogic())
    assert logic.step(1, pose, [(1.0, 0.0)], 1).collect
    x, y, yaw = pose
    initial = (x, y)
    for tick in range(300):
        command = logic.step(2 + tick * 0.05, (x, y, yaw), [], None)
        assert not command.collect
        # An independent kinematic integration catches an indefinitely wrong retreat.
        x += command.v * math.cos(yaw) * 0.05
        y += command.v * math.sin(yaw) * 0.05
        yaw += command.w * 0.05
        if not logic.retreating:
            break
    assert not logic.retreating, (initial, (x, y))
    assert abs(y) <= 2.2 and 1.4 <= x <= 58.6


def test_lost_target_aborts_docking_and_recovers() -> None:
    """A vanished visual target cannot latch docking forever beside a bank."""
    logic = MarineCollectorLogic(CollectorLogic())
    logic.step(1, (20, 2.2, 0), [(0, 1.6)], 1)
    assert logic.docking
    command = logic.step(2, (20, 2.65, math.pi / 2), [], 2)
    assert not logic.docking and logic.retreating
    assert command.v < 0 and not command.collect
