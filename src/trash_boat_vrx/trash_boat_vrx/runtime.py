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

"""Shared explicit executor lifecycle for integration nodes."""

import signal
from types import FrameType
from typing import Type

import rclpy
from rclpy.executors import SingleThreadedExecutor
from rclpy.node import Node
from rclpy.signals import SignalHandlerOptions


def run_node(node_type: Type[Node], args: list[str] | None = None) -> None:
    """Own the executor and context so SIGINT cannot race active publishers."""
    stopping = False

    def request_stop(_number: int, _frame: FrameType | None) -> None:
        nonlocal stopping
        stopping = True

    # Raising inside a pybind take_message can replace KeyboardInterrupt with a
    # conversion RuntimeError. Let the bounded spin finish before destroying ROS.
    signal.signal(signal.SIGINT, request_stop)
    signal.signal(signal.SIGTERM, request_stop)
    rclpy.init(args=args, signal_handler_options=SignalHandlerOptions.NO)
    executor = SingleThreadedExecutor()
    node = None
    try:
        node = node_type()
        executor.add_node(node)
        while rclpy.ok() and not stopping:
            executor.spin_once(timeout_sec=0.1)
    except (KeyboardInterrupt, rclpy.executors.ExternalShutdownException):
        pass
    finally:
        # Launch may forward a second interrupt after a terminal/group signal.
        signal.signal(signal.SIGINT, signal.SIG_IGN)
        signal.signal(signal.SIGTERM, signal.SIG_IGN)
        executor.shutdown()
        if node is not None:
            node.destroy_node()
        rclpy.try_shutdown()
