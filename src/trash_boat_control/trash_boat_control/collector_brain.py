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

"""Collector brain node executing navigation, trash approach, and scoop control."""

import signal

from geometry_msgs.msg import PoseArray, PoseStamped, Twist
import rclpy
from rclpy.executors import SingleThreadedExecutor
from rclpy.node import Node
from rclpy.signals import SignalHandlerOptions
from std_msgs.msg import Empty, String

from trash_boat_control.logic import CollectorLogic, yaw_from_quaternion


class CollectorBrain(Node):
    """ROS 2 wrapper for autonomous collector brain state machine."""

    def __init__(self, **kwargs) -> None:
        super().__init__('collector_brain', **kwargs)

        self.declare_parameter('control_rate', 20.0)
        self.declare_parameter('search_speed', 0.8)
        self.declare_parameter('approach_speed', 0.8)
        self.declare_parameter('min_approach_speed', 0.15)
        self.declare_parameter('k_ang', 1.5)
        self.declare_parameter('k_lin', 0.5)
        self.declare_parameter('w_max', 1.2)
        self.declare_parameter('detection_timeout', 0.5)
        self.declare_parameter('collect_fwd_min', 0.2)
        self.declare_parameter('collect_fwd_max', 1.2)
        self.declare_parameter('collect_lateral_max', 0.6)
        self.declare_parameter('collect_cooldown', 0.5)
        self.declare_parameter('canal_length', 60.0)
        self.declare_parameter('half_width', 4.0)
        self.declare_parameter('end_margin', 2.0)
        self.declare_parameter('patrol_aim_distance', 3.0)
        self.declare_parameter('bank_margin', 0.8)
        self.declare_parameter('bank_hysteresis', 0.3)
        self.declare_parameter('bank_speed', 0.3)

        self.logic = CollectorLogic(
            control_rate=float(
                self.get_parameter('control_rate').get_parameter_value().double_value
            ),
            search_speed=float(
                self.get_parameter('search_speed').get_parameter_value().double_value
            ),
            approach_speed=float(
                self.get_parameter('approach_speed').get_parameter_value().double_value
            ),
            min_approach_speed=float(
                self.get_parameter('min_approach_speed').get_parameter_value().double_value
            ),
            k_ang=float(self.get_parameter('k_ang').get_parameter_value().double_value),
            k_lin=float(self.get_parameter('k_lin').get_parameter_value().double_value),
            w_max=float(self.get_parameter('w_max').get_parameter_value().double_value),
            detection_timeout=float(
                self.get_parameter('detection_timeout').get_parameter_value().double_value
            ),
            collect_fwd_min=float(
                self.get_parameter('collect_fwd_min').get_parameter_value().double_value
            ),
            collect_fwd_max=float(
                self.get_parameter('collect_fwd_max').get_parameter_value().double_value
            ),
            collect_lateral_max=float(
                self.get_parameter('collect_lateral_max').get_parameter_value().double_value
            ),
            collect_cooldown=float(
                self.get_parameter('collect_cooldown').get_parameter_value().double_value
            ),
            canal_length=float(
                self.get_parameter('canal_length').get_parameter_value().double_value
            ),
            half_width=float(
                self.get_parameter('half_width').get_parameter_value().double_value
            ),
            end_margin=float(
                self.get_parameter('end_margin').get_parameter_value().double_value
            ),
            patrol_aim_distance=float(
                self.get_parameter('patrol_aim_distance').get_parameter_value().double_value
            ),
            bank_margin=float(
                self.get_parameter('bank_margin').get_parameter_value().double_value
            ),
            bank_hysteresis=float(
                self.get_parameter('bank_hysteresis').get_parameter_value().double_value
            ),
            bank_speed=float(
                self.get_parameter('bank_speed').get_parameter_value().double_value
            ),
        )

        self.current_pose: tuple[float, float, float] | None = None
        self.current_detections: list[tuple[float, float]] = []
        self.det_stamp: float | None = None

        # Publishers
        self.pub_cmd_vel = self.create_publisher(Twist, '/cmd_vel', 10)
        self.pub_collect = self.create_publisher(Empty, '/collect', 10)
        self.pub_brain_state = self.create_publisher(String, '/brain_state', 10)

        # Subscribers
        self.sub_pose = self.create_subscription(
            PoseStamped, '/boat_pose', self._pose_callback, 10
        )
        self.sub_detections = self.create_subscription(
            PoseArray, '/trash_detections', self._detections_callback, 10
        )

        timer_period = 1.0 / self.logic.control_rate
        self.timer = self.create_timer(timer_period, self._control_step)

    def _pose_callback(self, msg: PoseStamped) -> None:
        q = (
            msg.pose.orientation.x,
            msg.pose.orientation.y,
            msg.pose.orientation.z,
            msg.pose.orientation.w,
        )
        yaw = yaw_from_quaternion(q)
        self.current_pose = (msg.pose.position.x, msg.pose.position.y, yaw)

    def _detections_callback(self, msg: PoseArray) -> None:
        self.current_detections = [(p.position.x, p.position.y) for p in msg.poses]
        self.det_stamp = msg.header.stamp.sec + msg.header.stamp.nanosec * 1e-9

    def _control_step(self) -> None:
        now = self.get_clock().now().nanoseconds * 1e-9
        cmd = self.logic.step(now, self.current_pose, self.current_detections, self.det_stamp)

        # Publish cmd_vel
        twist = Twist()
        twist.linear.x = float(cmd.v)
        twist.angular.z = float(cmd.w)
        self.pub_cmd_vel.publish(twist)

        # Publish brain state
        state_msg = String()
        state_msg.data = cmd.state
        self.pub_brain_state.publish(state_msg)

        # Publish collect trigger if fired
        if cmd.collect:
            self.pub_collect.publish(Empty())


def main(args: list[str] | None = None) -> None:
    signal.signal(signal.SIGINT, signal.default_int_handler)
    signal.signal(signal.SIGTERM, signal.default_int_handler)
    rclpy.init(args=args, signal_handler_options=SignalHandlerOptions.NO)
    executor = SingleThreadedExecutor()
    node = CollectorBrain()
    executor.add_node(node)
    try:
        while rclpy.ok():
            executor.spin_once(timeout_sec=0.1)
    except (KeyboardInterrupt, rclpy.executors.ExternalShutdownException):
        pass
    finally:
        # Launch may forward a second interrupt after a terminal/group signal.
        signal.signal(signal.SIGINT, signal.SIG_IGN)
        signal.signal(signal.SIGTERM, signal.SIG_IGN)
        executor.shutdown()
        node.destroy_node()
        rclpy.try_shutdown()


if __name__ == '__main__':
    main()
