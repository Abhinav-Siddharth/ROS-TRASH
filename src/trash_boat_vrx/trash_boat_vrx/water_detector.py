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

"""Thin rendered-image detector using calibrated water-plane projection."""

from collections import deque
import math

import cv2
from cv_bridge import CvBridge
from geometry_msgs.msg import Pose, PoseArray, PoseStamped
from rclpy.node import Node
from rclpy.qos import qos_profile_sensor_data
from sensor_msgs.msg import CameraInfo, Image

from trash_boat_perception.detector_core import detect_trash
from trash_boat_vrx.projection import pixel_to_water
from trash_boat_vrx.runtime import run_node


class WaterDetector(Node):
    """Convert orange image blobs into boat-frame positions without simulator inputs."""

    def __init__(self) -> None:
        super().__init__('water_detector')
        defaults = {'hsv_lower': [5, 150, 120], 'hsv_upper': [25, 255, 255],
                    'min_area': 20.0, 'max_area': 800.0, 'camera_height': 6.0,
                    'water_z': 0.0, 'max_range': 12.0, 'pose_timeout': 0.5,
                    'pose_history_size': 100}
        for name, value in defaults.items():
            self.declare_parameter(name, value)
        self.settings = {key: self.get_parameter(key).value for key in defaults}
        self.bridge = CvBridge()
        self.intrinsics = None
        self.poses = deque(maxlen=self.settings['pose_history_size'])
        self.detections_pub = self.create_publisher(PoseArray, '/trash_detections', 10)
        self.debug_pub = self.create_publisher(Image, '/trash_detector/debug_image', 10)
        self.create_subscription(CameraInfo, '/camera/camera_info', self._calibration, 10)
        self.create_subscription(PoseStamped, '/boat_pose', self._pose, 10)
        self.create_subscription(Image, '/camera/image_raw', self._image, qos_profile_sensor_data)

    def _calibration(self, message: CameraInfo) -> None:
        values = (message.k[0], message.k[4], message.k[2], message.k[5])
        if all(math.isfinite(x) for x in values) and min(values[:2]) > 0:
            self.intrinsics = values

    def _pose(self, message: PoseStamped) -> None:
        stamp = message.header.stamp.sec + message.header.stamp.nanosec * 1e-9
        p, q = message.pose.position, message.pose.orientation
        self.poses.append((stamp, (p.x, p.y, p.z), (q.x, q.y, q.z, q.w)))

    def _image(self, message: Image) -> None:
        output = PoseArray()
        output.header.stamp = message.header.stamp
        output.header.frame_id = 'boat'
        image = self.bridge.imgmsg_to_cv2(message, desired_encoding='bgr8')
        debug = image.copy()
        stamp = message.header.stamp.sec + message.header.stamp.nanosec * 1e-9
        pose = min(self.poses, key=lambda item: abs(item[0] - stamp)) if self.poses else None
        ready = (pose is not None and self.intrinsics is not None
                 and abs(pose[0] - stamp) <= self.settings['pose_timeout'])
        detections = []
        if ready:
            centroids = detect_trash(image, self.settings['hsv_lower'],
                                     self.settings['hsv_upper'], self.settings['min_area'],
                                     self.settings['max_area'])
            for u, v in centroids:
                try:
                    body = pixel_to_water(u, v, self.intrinsics, pose[1], pose[2],
                                          self.settings['camera_height'], self.settings['water_z'],
                                          self.settings['max_range'])
                except ValueError:
                    body = None
                if body is not None:
                    detections.append(body)
                    cv2.circle(debug, (round(u), round(v)), 10, (0, 255, 0), 2)
        for fwd, left in sorted(detections, key=lambda item: math.hypot(*item)):
            item = Pose()
            item.position.x, item.position.y = fwd, left
            item.orientation.w = 1.0
            output.poses.append(item)
        label = f'{len(output.poses)} detections' if ready else 'Waiting for calibration / pose'
        cv2.putText(debug, label, (8, 22), cv2.FONT_HERSHEY_SIMPLEX, 0.45, (255, 255, 255), 1)
        self.detections_pub.publish(output)
        debug_msg = self.bridge.cv2_to_imgmsg(debug, encoding='bgr8')
        debug_msg.header = message.header
        self.debug_pub.publish(debug_msg)


def main(args: list[str] | None = None) -> None:
    """Run the rendered-camera perception node."""
    run_node(WaterDetector, args)
