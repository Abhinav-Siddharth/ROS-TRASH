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

"""Exercise repeated shutdown signals during real ROS node destruction."""

import os
from pathlib import Path
import select
import signal
import subprocess
import sys
import time


CHILD = """
import sys
from rclpy.node import Node
from trash_boat_vrx.runtime import run_node
class CleanupNode(Node):
    def __init__(self):
        super().__init__('cleanup_signal_test')
        self.create_timer(0.02, lambda: self.get_logger().info('READY'))
    def destroy_node(self):
        sys.stdout.write('CLEANUP\\n')
        sys.stdout.flush()
        sys.stdin.readline()
        return super().destroy_node()
run_node(CleanupNode)
"""


def test_repeated_interrupt_during_cleanup(tmp_path: Path) -> None:
    """Deliver a second SIGINT and SIGTERM inside real teardown without a traceback."""
    env = dict(os.environ, ROS_LOG_DIR=str(tmp_path / 'logs'))
    process = subprocess.Popen([sys.executable, '-u', '-c', CHILD], env=env,
                               stdin=subprocess.PIPE, stdout=subprocess.PIPE,
                               stderr=subprocess.STDOUT, text=True)
    output = ''
    try:
        phase = 'READY'
        deadline = time.monotonic() + 15
        while time.monotonic() < deadline:
            readable, _, _ = select.select([process.stdout], [], [], 0.1)
            if not readable:
                continue
            line = process.stdout.readline()
            output += line
            if phase == 'READY' and 'READY' in line:
                process.send_signal(signal.SIGINT)
                phase = 'CLEANUP'
            elif phase == 'CLEANUP' and 'CLEANUP' in line:
                process.send_signal(signal.SIGINT)
                process.send_signal(signal.SIGTERM)
                process.stdin.write('\n')
                process.stdin.flush()
                phase = 'DONE'
                break
        assert phase == 'DONE', output
        remainder, _ = process.communicate(timeout=5)
        output += remainder
        assert process.returncode == 0, output
        assert 'Traceback' not in output
    finally:
        if process.poll() is None:
            process.kill()
            process.communicate(timeout=5)


CALLBACK_CHILD = """
import sys
from rclpy.node import Node
from trash_boat_vrx.runtime import run_node
class CallbackNode(Node):
    def __init__(self):
        super().__init__('callback_signal_test')
        self.create_timer(0.02, self.callback)
    def callback(self):
        sys.stdout.write('IN_CALLBACK\\n')
        sys.stdout.flush()
        sys.stdin.readline()
        sys.stdout.write('CALLBACK_RETURNED\\n')
        sys.stdout.flush()
run_node(CallbackNode)
"""


def test_signal_allows_active_callback_to_return(tmp_path: Path) -> None:
    """SIGINT requests shutdown without injecting an exception into active ROS calls."""
    process = subprocess.Popen(
        [sys.executable, '-u', '-c', CALLBACK_CHILD],
        env=dict(os.environ, ROS_LOG_DIR=str(tmp_path / 'logs')),
        stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True)
    output = ''
    try:
        deadline = time.monotonic() + 15
        while time.monotonic() < deadline:
            readable, _, _ = select.select([process.stdout], [], [], 0.1)
            if readable:
                output += process.stdout.readline()
                if 'IN_CALLBACK' in output:
                    break
        assert 'IN_CALLBACK' in output, output
        process.send_signal(signal.SIGINT)
        process.stdin.write('\n')
        process.stdin.flush()
        rest, _ = process.communicate(timeout=5)
        output += rest
        assert process.returncode == 0 and 'CALLBACK_RETURNED' in output, output
        assert 'Traceback' not in output
    finally:
        if process.poll() is None:
            process.kill()
            process.communicate(timeout=5)
