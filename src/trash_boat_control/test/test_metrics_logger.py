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

"""Verify telemetry, distance calculation, and real process shutdown artifacts."""

from collections.abc import Iterator
import csv
import json
import os
from pathlib import Path
import select
import signal
import subprocess
import sys
import time

from geometry_msgs.msg import PoseStamped
import pytest
import rclpy
from rclpy.parameter import Parameter
from rclpy.signals import SignalHandlerOptions
from std_msgs.msg import Int32, String

from trash_boat_control.metrics_logger import MetricsLogger


@pytest.fixture(scope='module', autouse=True)
def ros_context() -> Iterator[None]:
    """Provide a real ROS context for telemetry tests."""
    rclpy.init(args=[], signal_handler_options=SignalHandlerOptions.NO)
    yield
    rclpy.try_shutdown()


@pytest.fixture
def logger(tmp_path: Path) -> Iterator[MetricsLogger]:
    """Create a real logger writing only to the test directory."""
    node = MetricsLogger(parameter_overrides=[Parameter('output_dir', value=str(tmp_path))])
    try:
        yield node
    finally:
        node.write_summary()
        node.destroy_node()


def test_unknown_status_is_not_zero_remaining(logger: MetricsLogger) -> None:
    """Do not claim completion before the simulator sends its initial status."""
    logger._log_step()
    with open(logger.csv_path, encoding='utf-8') as stream:
        rows = list(csv.DictReader(stream))
    assert rows[-1]['remaining'] == '-1'
    assert rows[-1]['collected'] == '0'


def test_telemetry_and_final_snapshot(logger: MetricsLogger) -> None:
    """Record message values and accumulate the travelled distance between poses."""
    pose = PoseStamped()
    pose.pose.position.x, pose.pose.position.y = 1.0, 1.0
    logger._pose_callback(pose)
    pose.pose.position.x, pose.pose.position.y = 4.0, 5.0
    logger._pose_callback(pose)
    logger._collected_callback(Int32(data=7))
    logger._remaining_callback(Int32(data=5))
    logger._bank_hits_callback(Int32(data=2))
    logger._brain_state_callback(String(data='APPROACH'))
    logger.write_summary()

    with open(logger.csv_path, encoding='utf-8') as stream:
        rows = list(csv.DictReader(stream))
    final = rows[-1]
    assert list(final) == [
        't', 'x', 'y', 'collected', 'remaining', 'bank_hits', 'state', 'path_length',
    ]
    assert (float(final['x']), float(final['y'])) == (4.0, 5.0)
    assert (int(final['collected']), int(final['remaining']), int(final['bank_hits'])) == (7, 5, 2)
    assert final['state'] == 'APPROACH'
    assert float(final['path_length']) == 5.0
    summary_path = Path(logger.output_dir) / 'summary.json'
    summary = json.loads(summary_path.read_text())
    assert summary['items_collected'] == 7
    assert summary['path_length_m'] == 5.0
    assert summary['bank_hits'] == 2
    assert summary['duration_s'] >= 0
    assert summary['items_per_min'] > 0
    previous = summary_path.read_bytes()
    logger.write_summary()
    assert summary_path.read_bytes() == previous


@pytest.mark.parametrize('stop_signal', [signal.SIGINT, signal.SIGTERM])
def test_process_shutdown_writes_summary(tmp_path: Path, stop_signal: int) -> None:
    """Stop the real idle node and verify complete artifacts without a traceback."""
    output_dir = tmp_path / 'mission'
    env = dict(os.environ, ROS_LOG_DIR=str(tmp_path / 'ros_logs'))
    process = subprocess.Popen(
        [sys.executable, '-m', 'trash_boat_control.metrics_logger', '--ros-args',
         '-p', f'output_dir:={output_dir}'],
        stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True, env=env,
    )
    output = ''
    try:
        assert process.stdout is not None
        deadline = time.monotonic() + 10.0
        ready = False
        while time.monotonic() < deadline:
            readable, _, _ = select.select([process.stdout], [], [], 0.1)
            if not readable:
                continue
            line = process.stdout.readline()
            output += line
            if 'Writing metrics to' in line:
                ready = True
                break
            if process.poll() is not None:
                break
        assert ready, output
        process.send_signal(stop_signal)
        remainder, _ = process.communicate(timeout=5.0)
        output += remainder
        assert process.returncode == 0, output
        assert 'Traceback' not in output
        summary = json.loads((output_dir / 'summary.json').read_text())
        assert summary['items_collected'] == 0
        assert summary['path_length_m'] == 0.0
        with (output_dir / 'metrics.csv').open() as stream:
            assert len(list(csv.DictReader(stream))) >= 1
    finally:
        if process.poll() is None:
            process.terminate()
            process.communicate(timeout=5.0)
