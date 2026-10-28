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

"""Canal simulation node for trash_boat."""

import math
import random

import cv2
from cv_bridge import CvBridge
from geometry_msgs.msg import PoseStamped, Twist
import numpy as np
import rclpy
from rclpy.node import Node
from sensor_msgs.msg import Image
from std_msgs.msg import Empty, Int32


class CanalSim(Node):
    """Simulates canal environment, unicycle boat, drifting trash, and camera feed."""

    def __init__(self, **kwargs) -> None:
        super().__init__('canal_sim', **kwargs)

        self.declare_parameter('canal_length', 60.0)
        self.declare_parameter('half_width', 4.0)
        self.declare_parameter('n_trash', 12)
        self.declare_parameter('current', 0.05)
        self.declare_parameter('seed', 42)
        self.declare_parameter('image_size', 400)
        self.declare_parameter('pixels_per_meter', 40.0)

        self.canal_length: float = float(
            self.get_parameter('canal_length').get_parameter_value().double_value
        )
        self.half_width: float = float(
            self.get_parameter('half_width').get_parameter_value().double_value
        )
        self.n_trash: int = int(
            self.get_parameter('n_trash').get_parameter_value().integer_value
        )
        self.current: float = float(
            self.get_parameter('current').get_parameter_value().double_value
        )
        self.seed: int = int(
            self.get_parameter('seed').get_parameter_value().integer_value
        )
        self.image_size: int = int(
            self.get_parameter('image_size').get_parameter_value().integer_value
        )
        self.pixels_per_meter: float = float(
            self.get_parameter('pixels_per_meter').get_parameter_value().double_value
        )

        # Boat state: unicycle starting at (2.0, 0.0, yaw 0.0)
        self.x: float = 2.0
        self.y: float = 0.0
        self.yaw: float = 0.0
        self.v_cmd: float = 0.0
        self.w_cmd: float = 0.0

        # Metrics
        self.collected: int = 0
        self.bank_hits: int = 0
        self.in_bank_clamp: bool = False

        # Spawn trash with seeded RNG
        self.trash_list: list[list[float]] = []
        self._init_trash()

        # OpenCV bridge
        self.bridge: CvBridge = CvBridge()

        # Publishers
        self.pub_image = self.create_publisher(Image, '/camera/image_raw', 10)
        self.pub_pose = self.create_publisher(PoseStamped, '/boat_pose', 10)
        self.pub_collected = self.create_publisher(Int32, '/trash_collected', 10)
        self.pub_remaining = self.create_publisher(Int32, '/trash_remaining', 10)
        self.pub_bank_hits = self.create_publisher(Int32, '/bank_hits', 10)

        # Subscribers
        self.sub_cmd_vel = self.create_subscription(
            Twist, '/cmd_vel', self._cmd_vel_callback, 10
        )
        self.sub_collect = self.create_subscription(
            Empty, '/collect', self._collect_callback, 10
        )

        # Timers: 20 Hz physics/pose, 10 Hz camera, 2 Hz status
        self.dt: float = 0.05
        self.timer_physics = self.create_timer(self.dt, self._physics_step)
        self.timer_camera = self.create_timer(0.1, self._camera_step)
        self.timer_status = self.create_timer(0.5, self._publish_status)

        # Initial status publish
        self._publish_status()

    def _init_trash(self) -> None:
        """Spawn trash uniformly across the canal using seeded RNG."""
        rng = random.Random(self.seed)
        self.trash_list = []
        for _ in range(self.n_trash):
            tx = rng.uniform(8.0, self.canal_length - 3.0)
            ty = rng.uniform(-(self.half_width - 0.8), self.half_width - 0.8)
            self.trash_list.append([tx, ty])

    def _cmd_vel_callback(self, msg: Twist) -> None:
        self.v_cmd = float(msg.linear.x)
        self.w_cmd = float(msg.angular.z)

    def _collect_callback(self, _msg: Empty) -> None:
        """Remove trash in scoop region: 0 <= fwd <= 1.5 and |left| <= 1.0."""
        retained: list[list[float]] = []
        newly_collected = 0

        cos_yaw = math.cos(self.yaw)
        sin_yaw = math.sin(self.yaw)

        for tx, ty in self.trash_list:
            dx = tx - self.x
            dy = ty - self.y
            fwd = dx * cos_yaw + dy * sin_yaw
            left = -dx * sin_yaw + dy * cos_yaw

            if 0.0 <= fwd <= 1.5 and abs(left) <= 1.0:
                newly_collected += 1
            else:
                retained.append([tx, ty])

        if newly_collected > 0:
            self.collected += newly_collected
            self.trash_list = retained
            self._publish_status()

    def _physics_step(self) -> None:
        """Update boat kinematics, clamp positions, and publish pose at 20 Hz."""
        self.x += self.v_cmd * math.cos(self.yaw) * self.dt
        self.y += self.v_cmd * math.sin(self.yaw) * self.dt
        self.yaw += self.w_cmd * self.dt

        # Normalize yaw to (-pi, pi]
        self.yaw = (self.yaw + math.pi) % (2.0 * math.pi) - math.pi

        # Clamp lateral position to half_width - 0.3
        clamp_limit = self.half_width - 0.3
        if abs(self.y) >= clamp_limit:
            self.y = math.copysign(clamp_limit, self.y)
            if not self.in_bank_clamp:
                self.bank_hits += 1
                self.in_bank_clamp = True
                self._publish_status()
        else:
            self.in_bank_clamp = False

        # Clamp longitudinal position to [0.3, canal_length - 0.3]
        self.x = max(0.3, min(self.canal_length - 0.3, self.x))

        # Trash drift downstream (+x), piling at x = canal_length - 0.5
        pile_limit = self.canal_length - 0.5
        for trash in self.trash_list:
            trash[0] += self.current * self.dt
            if trash[0] > pile_limit:
                trash[0] = pile_limit

        # Publish boat pose
        pose_msg = PoseStamped()
        pose_msg.header.stamp = self.get_clock().now().to_msg()
        pose_msg.header.frame_id = 'map'
        pose_msg.pose.position.x = float(self.x)
        pose_msg.pose.position.y = float(self.y)
        pose_msg.pose.position.z = 0.0
        pose_msg.pose.orientation.z = math.sin(self.yaw / 2.0)
        pose_msg.pose.orientation.w = math.cos(self.yaw / 2.0)
        self.pub_pose.publish(pose_msg)

    def _camera_step(self) -> None:
        """Render top-down camera view and publish image at 10 Hz."""
        img = np.full(
            (self.image_size, self.image_size, 3), (40, 90, 60), dtype=np.uint8
        )

        canal_corners_world = [
            (0.0, -self.half_width),
            (self.canal_length, -self.half_width),
            (self.canal_length, self.half_width),
            (0.0, self.half_width),
        ]

        cos_yaw = math.cos(self.yaw)
        sin_yaw = math.sin(self.yaw)
        cx = self.image_size / 2.0
        cy = self.image_size / 2.0

        canal_pts = []
        for wx, wy in canal_corners_world:
            dx = wx - self.x
            dy = wy - self.y
            fwd = dx * cos_yaw + dy * sin_yaw
            left = -dx * sin_yaw + dy * cos_yaw
            u = cx - left * self.pixels_per_meter
            v = cy - fwd * self.pixels_per_meter
            canal_pts.append([u, v])

        canal_pts_arr = np.array([canal_pts], dtype=np.int32)
        cv2.fillPoly(img, canal_pts_arr, (120, 80, 30))

        # Draw trash circles (orange BGR (0, 128, 255), radius 7)
        for tx, ty in self.trash_list:
            dx = tx - self.x
            dy = ty - self.y
            fwd = dx * cos_yaw + dy * sin_yaw
            left = -dx * sin_yaw + dy * cos_yaw
            u = cx - left * self.pixels_per_meter
            v = cy - fwd * self.pixels_per_meter
            if -10 <= u <= self.image_size + 10 and -10 <= v <= self.image_size + 10:
                cv2.circle(
                    img,
                    (int(round(u)), int(round(v))),
                    7,
                    (0, 128, 255),
                    -1,
                )

        # Draw boat (white triangle pointing up at center)
        boat_triangle = np.array(
            [
                [cx, cy - 12.0],
                [cx - 6.0, cy + 8.0],
                [cx + 6.0, cy + 8.0],
            ],
            dtype=np.int32,
        )
        cv2.fillPoly(img, [boat_triangle], (255, 255, 255))

        img_msg = self.bridge.cv2_to_imgmsg(img, encoding='bgr8')
        img_msg.header.stamp = self.get_clock().now().to_msg()
        img_msg.header.frame_id = 'boat'
        self.pub_image.publish(img_msg)

    def _publish_status(self) -> None:
        """Publish status topics: collected, remaining, and bank_hits."""
        msg_c = Int32()
        msg_c.data = self.collected
        self.pub_collected.publish(msg_c)

        msg_r = Int32()
        msg_r.data = len(self.trash_list)
        self.pub_remaining.publish(msg_r)

        msg_b = Int32()
        msg_b.data = self.bank_hits
        self.pub_bank_hits.publish(msg_b)


def main(args: list[str] | None = None) -> None:
    rclpy.init(args=args)
    node = CanalSim()
    try:
        rclpy.spin(node)
    except (KeyboardInterrupt, rclpy.executors.ExternalShutdownException):
        pass
    finally:
        node.destroy_node()
        rclpy.try_shutdown()


if __name__ == '__main__':
    main()
