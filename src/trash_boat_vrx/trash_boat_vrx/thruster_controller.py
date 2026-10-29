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

"""Thin ROS wrapper for velocity feedback and physical thruster commands."""

from dataclasses import asdict
import math

from geometry_msgs.msg import Twist
from nav_msgs.msg import Odometry
from rclpy.node import Node
from std_msgs.msg import Float64

from trash_boat_vrx.runtime import run_node
from trash_boat_vrx.thruster_core import thruster_forces, ThrusterConfig


class ThrusterController(Node):
    """Drive the force-actuated boat using only command and odometry inputs."""

    def __init__(self) -> None:
        super().__init__('thruster_controller')
        for name, value in asdict(ThrusterConfig()).items():
            self.declare_parameter(name, value)
        self.declare_parameter('control_rate', 20.0)
        self.config = ThrusterConfig(**{
            key: self.get_parameter(key).value for key in asdict(ThrusterConfig())
        })
        self.config.validate()
        rate = self.get_parameter('control_rate').value
        if not math.isfinite(rate) or rate <= 0:
            raise ValueError('control_rate must be positive')
        self.target = None
        self.target_stamp = None
        self.velocity = None
        self.velocity_stamp = None
        self.left_pub = self.create_publisher(Float64, '/boat/thrusters/left', 10)
        self.right_pub = self.create_publisher(Float64, '/boat/thrusters/right', 10)
        self.create_subscription(Twist, '/cmd_vel', self._command, 10)
        self.create_subscription(Odometry, '/boat/odometry', self._odometry, 10)
        self.create_timer(1 / rate, self._step)

    def _command(self, message: Twist) -> None:
        self.target = (message.linear.x, message.angular.z)
        self.target_stamp = self.get_clock().now().nanoseconds * 1e-9

    def _odometry(self, message: Odometry) -> None:
        self.velocity = (message.twist.twist.linear.x, message.twist.twist.angular.z)
        self.velocity_stamp = message.header.stamp.sec + message.header.stamp.nanosec * 1e-9

    def _step(self) -> None:
        now = self.get_clock().now().nanoseconds * 1e-9
        left, right = thruster_forces(now, self.target, self.target_stamp,
                                      self.velocity, self.velocity_stamp, self.config)
        self.left_pub.publish(Float64(data=left))
        self.right_pub.publish(Float64(data=right))


def main(args: list[str] | None = None) -> None:
    """Run the thruster feedback controller."""
    run_node(ThrusterController, args)
