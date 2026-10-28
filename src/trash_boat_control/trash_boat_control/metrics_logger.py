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

"""Metrics logger node recording telemetry CSV and mission summary JSON."""

import csv
import json
import math
import os
import signal

from geometry_msgs.msg import PoseStamped
import rclpy
from rclpy.node import Node
from rclpy.signals import SignalHandlerOptions
from std_msgs.msg import Int32, String


class MetricsLogger(Node):
    """Subscribes to telemetry topics and logs metrics at 2 Hz."""

    def __init__(self, **kwargs) -> None:
        super().__init__('metrics_logger', **kwargs)

        self.declare_parameter('output_dir', '~/trash_boat_metrics')
        raw_output_dir = self.get_parameter('output_dir').get_parameter_value().string_value
        self.output_dir: str = os.path.expanduser(raw_output_dir)
        os.makedirs(self.output_dir, exist_ok=True)

        self.start_time: float = self.get_clock().now().nanoseconds * 1e-9

        # Metrics state
        self.x: float = 0.0
        self.y: float = 0.0
        self.prev_x: float | None = None
        self.prev_y: float | None = None
        self.path_length: float = 0.0

        self.collected: int = 0
        self.remaining: int = -1  # Unknown until simulator status arrives.
        self.bank_hits: int = 0
        self.brain_state: str = 'SEARCH'

        # CSV Writer setup
        self.csv_path: str = os.path.join(self.output_dir, 'metrics.csv')
        self.csv_file = open(self.csv_path, 'w', newline='', encoding='utf-8')
        self.csv_writer = csv.writer(self.csv_file)
        self.csv_writer.writerow(
            ['t', 'x', 'y', 'collected', 'remaining', 'bank_hits', 'state', 'path_length']
        )
        self.csv_file.flush()

        # Subscribers
        self.sub_pose = self.create_subscription(
            PoseStamped, '/boat_pose', self._pose_callback, 10
        )
        self.sub_collected = self.create_subscription(
            Int32, '/trash_collected', self._collected_callback, 10
        )
        self.sub_remaining = self.create_subscription(
            Int32, '/trash_remaining', self._remaining_callback, 10
        )
        self.sub_bank_hits = self.create_subscription(
            Int32, '/bank_hits', self._bank_hits_callback, 10
        )
        self.sub_brain_state = self.create_subscription(
            String, '/brain_state', self._brain_state_callback, 10
        )

        # 2 Hz logging timer
        self.timer = self.create_timer(0.5, self._log_step)
        self.get_logger().info(f'Writing metrics to {self.csv_path}')

    def _pose_callback(self, msg: PoseStamped) -> None:
        self.x = msg.pose.position.x
        self.y = msg.pose.position.y
        if self.prev_x is not None and self.prev_y is not None:
            step_dist = math.hypot(self.x - self.prev_x, self.y - self.prev_y)
            self.path_length += step_dist
        self.prev_x = self.x
        self.prev_y = self.y

    def _collected_callback(self, msg: Int32) -> None:
        self.collected = msg.data

    def _remaining_callback(self, msg: Int32) -> None:
        self.remaining = msg.data

    def _bank_hits_callback(self, msg: Int32) -> None:
        self.bank_hits = msg.data

    def _brain_state_callback(self, msg: String) -> None:
        self.brain_state = msg.data

    def _log_step(self) -> None:
        now = self.get_clock().now().nanoseconds * 1e-9
        t = now - self.start_time
        self.csv_writer.writerow(
            [
                round(t, 2),
                round(self.x, 3),
                round(self.y, 3),
                self.collected,
                self.remaining,
                self.bank_hits,
                self.brain_state,
                round(self.path_length, 3),
            ]
        )
        self.csv_file.flush()

    def write_summary(self) -> None:
        """Write summary.json on shutdown."""
        if self.csv_file.closed:
            return
        self._log_step()
        now = self.get_clock().now().nanoseconds * 1e-9
        duration_s = max(0.001, now - self.start_time)
        items_per_min = self.collected / (duration_s / 60.0)

        summary_data = {
            'items_collected': self.collected,
            'duration_s': round(duration_s, 2),
            'items_per_min': round(items_per_min, 2),
            'path_length_m': round(self.path_length, 2),
            'bank_hits': self.bank_hits,
        }

        summary_path = os.path.join(self.output_dir, 'summary.json')
        with open(summary_path, 'w', encoding='utf-8') as f:
            json.dump(summary_data, f, indent=2)
            f.write('\n')

        if not self.csv_file.closed:
            self.csv_file.close()


def main(args: list[str] | None = None) -> None:
    signal.signal(signal.SIGINT, signal.default_int_handler)
    signal.signal(signal.SIGTERM, signal.default_int_handler)
    rclpy.init(args=args, signal_handler_options=SignalHandlerOptions.NO)
    node = MetricsLogger()
    try:
        while rclpy.ok():
            rclpy.spin_once(node, timeout_sec=0.1)
    except (KeyboardInterrupt, rclpy.executors.ExternalShutdownException):
        pass
    finally:
        node.write_summary()
        node.destroy_node()
        rclpy.try_shutdown()


if __name__ == '__main__':
    main()
