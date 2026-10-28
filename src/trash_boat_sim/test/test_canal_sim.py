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

"""Unit tests for CanalSim node."""

import math

import pytest
import rclpy
from rclpy.parameter import Parameter
from std_msgs.msg import Empty

from trash_boat_sim.canal_sim import CanalSim


@pytest.fixture(scope='module')
def rclpy_init():
    rclpy.init()
    yield
    rclpy.try_shutdown()


def test_collect_region(rclpy_init):
    """Trash 1.0 m ahead is removed by collect_cb; trash 3 m ahead is not."""
    node = CanalSim()
    try:
        node.x = 2.0
        node.y = 0.0
        node.yaw = 0.0
        # Trash at 3.0 m is 1.0 m ahead; trash at 5.0 m is 3.0 m ahead
        node.trash_list = [[3.0, 0.0], [5.0, 0.0]]
        node._collect_callback(Empty())

        assert len(node.trash_list) == 1
        assert node.trash_list[0] == [5.0, 0.0]
        assert node.collected == 1
    finally:
        node.destroy_node()


def test_trash_drift(rclpy_init):
    """Trash drifts +x by about current * t."""
    node = CanalSim()
    try:
        node.trash_list = [[10.0, 0.0]]
        # 20 steps of dt=0.05 gives 1.0 second
        for _ in range(20):
            node._physics_step()

        expected_x = 10.0 + node.current * 1.0
        assert math.isclose(node.trash_list[0][0], expected_x, rel_tol=1e-3)
    finally:
        node.destroy_node()


def test_bank_hit_clamp_transition(rclpy_init):
    """Driving into the bank for many steps yields bank_hits == 1, not one per step."""
    node = CanalSim()
    try:
        node.x = 10.0
        node.y = 3.5
        node.yaw = math.pi / 2.0  # Facing positive y (left bank)
        node.v_cmd = 0.5
        node.w_cmd = 0.0

        for _ in range(50):
            node._physics_step()

        assert math.isclose(node.y, node.half_width - 0.3, abs_tol=1e-5)
        assert node.bank_hits == 1
    finally:
        node.destroy_node()


def test_seed_determinism(rclpy_init):
    """Same seed gives identical initial trash positions; different seeds differ."""
    param_seed42 = Parameter('seed', Parameter.Type.INTEGER, 42)
    param_seed99 = Parameter('seed', Parameter.Type.INTEGER, 99)

    node1 = CanalSim(parameter_overrides=[param_seed42])
    node2 = CanalSim(parameter_overrides=[param_seed42])
    node3 = CanalSim(parameter_overrides=[param_seed99])

    try:
        assert node1.trash_list == node2.trash_list
        assert node1.trash_list != node3.trash_list
    finally:
        node1.destroy_node()
        node2.destroy_node()
        node3.destroy_node()
