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

"""ROS 2 node for visual trash detection from top-down camera images."""

import signal

import cv2
from cv_bridge import CvBridge
from geometry_msgs.msg import Pose, PoseArray
import rclpy
from rclpy.executors import SingleThreadedExecutor
from rclpy.node import Node
from rclpy.signals import SignalHandlerOptions
from sensor_msgs.msg import Image

from trash_boat_perception.detector_core import detect_trash, pixel_to_body


class TrashDetector(Node):
    """Detects floating trash blobs and publishes body-frame detections."""

    def __init__(self, **kwargs) -> None:
        super().__init__('trash_detector', **kwargs)

        self.declare_parameter('hsv_lower', [5, 150, 150])
        self.declare_parameter('hsv_upper', [25, 255, 255])
        self.declare_parameter('min_area', 20.0)
        self.declare_parameter('max_area', 800.0)
        self.declare_parameter('image_size', 400)
        self.declare_parameter('pixels_per_meter', 40.0)

        self.bridge: CvBridge = CvBridge()

        # Publishers
        self.pub_detections = self.create_publisher(PoseArray, '/trash_detections', 10)
        self.pub_debug = self.create_publisher(Image, '/trash_detector/debug_image', 10)

        # Subscriber
        self.sub_image = self.create_subscription(
            Image, '/camera/image_raw', self._image_callback, 10
        )

    def _image_callback(self, msg: Image) -> None:
        """Process incoming camera frame and publish PoseArray and debug image."""
        hsv_lower = self.get_parameter('hsv_lower').get_parameter_value().integer_array_value
        hsv_upper = self.get_parameter('hsv_upper').get_parameter_value().integer_array_value
        min_area = self.get_parameter('min_area').get_parameter_value().double_value
        max_area = self.get_parameter('max_area').get_parameter_value().double_value
        image_size = self.get_parameter('image_size').get_parameter_value().integer_value
        pixels_per_meter = (
            self.get_parameter('pixels_per_meter').get_parameter_value().double_value
        )

        bgr = self.bridge.imgmsg_to_cv2(msg, desired_encoding='bgr8')
        centroids = detect_trash(bgr, hsv_lower, hsv_upper, min_area, max_area)

        # Prepare PoseArray
        pose_array = PoseArray()
        pose_array.header.stamp = msg.header.stamp
        pose_array.header.frame_id = 'boat'

        debug_img = bgr.copy()

        for u, v in centroids:
            fwd, left = pixel_to_body(u, v, image_size, pixels_per_meter)
            pose = Pose()
            pose.position.x = fwd
            pose.position.y = left
            pose.position.z = 0.0
            pose.orientation.x = 0.0
            pose.orientation.y = 0.0
            pose.orientation.z = 0.0
            pose.orientation.w = 1.0
            pose_array.poses.append(pose)

            # Circle detections in green on debug image
            cv2.circle(debug_img, (int(round(u)), int(round(v))), 10, (0, 255, 0), 2)

        self.pub_detections.publish(pose_array)

        # Publish debug image
        debug_msg = self.bridge.cv2_to_imgmsg(debug_img, encoding='bgr8')
        debug_msg.header = msg.header
        self.pub_debug.publish(debug_msg)


def main(args: list[str] | None = None) -> None:
    signal.signal(signal.SIGINT, signal.default_int_handler)
    signal.signal(signal.SIGTERM, signal.default_int_handler)
    rclpy.init(args=args, signal_handler_options=SignalHandlerOptions.NO)
    executor = SingleThreadedExecutor()
    node = TrashDetector()
    executor.add_node(node)
    try:
        while rclpy.ok():
            executor.spin_once(timeout_sec=0.1)
    except (KeyboardInterrupt, rclpy.executors.ExternalShutdownException):
        pass
    finally:
        executor.shutdown()
        node.destroy_node()
        rclpy.try_shutdown()


if __name__ == '__main__':
    main()
