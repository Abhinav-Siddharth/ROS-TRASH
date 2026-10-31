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

"""Independent real-process VRX acceptance monitor; never used by decision nodes."""

import argparse
from collections import Counter
import csv
import json
import math
import os
from pathlib import Path
import signal
import subprocess
import sys
import time

from geometry_msgs.msg import PoseArray, PoseStamped, Twist
import rclpy
from rclpy.node import Node
from rclpy.parameter import Parameter
from sensor_msgs.msg import Image
from std_msgs.msg import Float64, Int32, String


class MissionMonitor(Node):
    """Observe rendered data and scorer counters independently of autonomy."""

    def __init__(self) -> None:
        super().__init__('vrx_acceptance_monitor', parameter_overrides=[
            Parameter('use_sim_time', value=True),
        ])
        self.collected = -1
        self.remaining = -1
        self.bank_hits = -1
        self.images = 0
        self.detections = 0
        self.nonempty = 0
        self.commands = 0
        self.thrusters = 0
        self.poses = 0
        self.states = Counter()
        self.last_image = None
        self.last_pose = None
        self.create_subscription(Int32, '/trash_collected', self._collected, 10)
        self.create_subscription(Int32, '/trash_remaining', self._remaining, 10)
        self.create_subscription(Int32, '/bank_hits', self._hits, 10)
        self.create_subscription(Image, '/camera/image_raw', self._image, 10)
        self.create_subscription(PoseArray, '/trash_detections', self._detections, 10)
        self.create_subscription(String, '/brain_state', self._state, 10)
        self.create_subscription(Twist, '/cmd_vel', self._command, 10)
        self.create_subscription(Float64, '/boat/thrusters/left', self._thrust, 10)
        self.create_subscription(PoseStamped, '/boat_pose', self._pose, 10)

    def _collected(self, message: Int32) -> None:
        self.collected = message.data

    def _remaining(self, message: Int32) -> None:
        self.remaining = message.data

    def _hits(self, message: Int32) -> None:
        self.bank_hits = message.data

    def _image(self, message: Image) -> None:
        self.images += 1
        self.last_image = message

    def _detections(self, message: PoseArray) -> None:
        self.detections += 1
        self.nonempty += bool(message.poses)

    def _state(self, message: String) -> None:
        self.states[message.data] += 1

    def _command(self, _message: Twist) -> None:
        self.commands += 1

    def _thrust(self, _message: Float64) -> None:
        self.thrusters += 1

    def _pose(self, message: PoseStamped) -> None:
        self.poses += 1
        self.last_pose = (message.pose.position.x, message.pose.position.y)

    def snapshot(self) -> dict:
        """Return measured data and simulated duration, excluding wall-clock startup."""
        return {'collected': self.collected, 'remaining': self.remaining,
                'bank_hits': self.bank_hits,
                'sim_seconds': round(self.get_clock().now().nanoseconds * 1e-9, 3),
                'images': self.images, 'detection_frames': self.detections,
                'nonempty_detections': self.nonempty, 'commands': self.commands,
                'thruster_messages': self.thrusters, 'poses': self.poses,
                'states': dict(self.states), 'last_pose': self.last_pose}


def stop_process(process: subprocess.Popen) -> bool:
    """Interrupt this launch's process group; report escalation as unclean shutdown."""
    if process.poll() is not None:
        return process.returncode == 0
    process.send_signal(signal.SIGINT)
    try:
        process.wait(timeout=25)
        return process.returncode == 0
    except subprocess.TimeoutExpired:
        os.killpg(process.pid, signal.SIGTERM)
        try:
            process.wait(timeout=10)
        except subprocess.TimeoutExpired:
            os.killpg(process.pid, signal.SIGKILL)
            process.wait(timeout=5)
        return False


def check_metrics(directory: Path, collected: int) -> dict:
    """Require measured final CSV and summary to agree; reject missing telemetry."""
    summary = json.loads((directory / 'summary.json').read_text())
    with (directory / 'metrics.csv').open() as stream:
        rows = list(csv.DictReader(stream))
    if not rows or int(rows[-1]['collected']) != collected:
        raise ValueError('CSV final item count disagrees with independent monitor')
    if summary['items_collected'] != collected:
        raise ValueError('Summary count disagrees with independent monitor')
    if not math.isclose(float(rows[-1]['path_length']), summary['path_length_m'], abs_tol=0.006):
        raise ValueError('Summary path length disagrees with CSV')
    if int(rows[-1]['bank_hits']) != summary['bank_hits']:
        raise ValueError('Summary bank hits disagree with CSV')
    if not math.isclose(float(rows[-1]['t']), summary['duration_s'], abs_tol=0.01):
        raise ValueError('Summary duration disagrees with final CSV timestamp')
    return summary


def main() -> None:
    """Run a full real mission and save honest, attributable acceptance evidence."""
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--seed', type=int, default=1)
    parser.add_argument('--current', type=float, default=0.05)
    parser.add_argument('--wave-amplitude', type=float, default=0.0)
    parser.add_argument('--output', required=True, type=Path)
    parser.add_argument('--sim-timeout', type=float, default=420.0)
    parser.add_argument('--wall-timeout', type=float, default=1200.0)
    parser.add_argument('--gui', action='store_true')
    args = parser.parse_args()
    args.output = args.output.resolve()
    args.output.mkdir(parents=True, exist_ok=False)
    command = ['ros2', 'launch', 'trash_boat_vrx', 'mission.launch.py',
               f'seed:={args.seed}', f'current:={args.current}',
               f'wave_amplitude:={args.wave_amplitude}',
               f'headless:={str(not args.gui).lower()}', f'output_dir:={args.output}']
    with (args.output / 'mission.log').open('w') as log:
        process = subprocess.Popen(command, stdout=log, stderr=subprocess.STDOUT,
                                   start_new_session=True)
        rclpy.init()
        node = MissionMonitor()
        result = {'backend': 'vrx', 'seed': args.seed, 'current': args.current,
                  'wave_amplitude': args.wave_amplitude, 'command': command}
        start = time.monotonic()
        last_report = start
        last_clock = 0.0
        clock_at = start
        error = None
        try:
            while time.monotonic() - start < args.wall_timeout:
                rclpy.spin_once(node, timeout_sec=0.1)
                measured = node.snapshot()
                now = time.monotonic()
                if measured['sim_seconds'] != last_clock:
                    last_clock = measured['sim_seconds']
                    clock_at = now
                if process.poll() is not None:
                    raise RuntimeError('Required mission process exited before completion')
                if now - clock_at > 90:
                    raise RuntimeError('No advancing simulation clock for 90 wall seconds')
                if now - last_report >= 10:
                    sys.stdout.write(json.dumps(measured) + '\n')
                    sys.stdout.flush()
                    last_report = now
                if node.remaining == 0 and node.collected == 12:
                    break
                if measured['sim_seconds'] >= args.sim_timeout:
                    break
                if node.bank_hits > 3:
                    break
        except (RuntimeError, KeyboardInterrupt) as exception:
            error = str(exception)
        finally:
            result.update(node.snapshot())
            result['wall_seconds'] = round(time.monotonic() - start, 2)
            result['clean_shutdown'] = stop_process(process)
            node.destroy_node()
            rclpy.try_shutdown()
    try:
        result['metrics'] = check_metrics(args.output, result['collected'])
        if result['metrics']['bank_hits'] != result['bank_hits']:
            raise ValueError('Summary bank hits disagree with independent monitor')
    except (OSError, ValueError, KeyError) as exception:
        error = str(exception)
    log_text = (args.output / 'mission.log').read_text()
    result['runtime_errors'] = [line for line in log_text.splitlines()
                                if 'Traceback' in line or '[ERROR]' in line or '[Err]' in line]
    result['passed'] = bool(
        error is None and result['clean_shutdown'] and not result['runtime_errors']
        and result['collected'] >= 11 and result['remaining'] >= 0
        and result['collected'] + result['remaining'] == 12
        and 0 <= result['bank_hits'] <= 3 and result['sim_seconds'] <= args.sim_timeout + 0.1
        and result['images'] > 10 and result['nonempty_detections'] > 0
        and result['thruster_messages'] > 0 and result['poses'] > 0
        and 'COLLECT' in result['states'] and 'APPROACH' in result['states']
    )
    result['error'] = error
    (args.output / 'acceptance.json').write_text(json.dumps(result, indent=2) + '\n')
    sys.stdout.write(json.dumps(result, indent=2) + '\n')
    if not result['passed']:
        raise SystemExit(1)


if __name__ == '__main__':
    main()
