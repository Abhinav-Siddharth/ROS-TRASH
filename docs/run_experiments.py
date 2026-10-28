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

"""
Run the nine specified M5 experiments against real nodes and the provided probe.

Run from a built/sourced workspace with:
    python3 docs/run_experiments.py --output-dir log/experiments
"""

import argparse
import csv
from datetime import datetime, timezone
import hashlib
import json
import os
from pathlib import Path
import signal
import subprocess
import sys
import time


ROOT = Path(__file__).resolve().parents[1]


def run_mission(seed: int, current: float, directory: Path, env: dict[str, str]) -> dict:
    """Launch, measure, and cleanly stop one actual mission."""
    directory.mkdir(parents=True, exist_ok=False)
    command = [
        'ros2', 'launch', 'trash_boat_bringup', 'mission.launch.py',
        f'seed:={seed}', 'n_trash:=12', f'current:={current}', f'output_dir:={directory}',
    ]
    with (directory / 'launch.txt').open('w') as stream:
        process = subprocess.Popen(
            command, cwd=ROOT, env=env, stdout=stream, stderr=subprocess.STDOUT,
            start_new_session=True,
        )
        try:
            time.sleep(3.0)
            probe = subprocess.run(
                [sys.executable, str(ROOT / 'tools/acceptance_check.py'), '--total', '12',
                 '--timeout', '420.0', '--min-ratio', '0.9', '--max-bank-hits', '3'],
                cwd=ROOT, env=env, capture_output=True, text=True, timeout=435.0,
                check=False,
            )
            (directory / 'probe.txt').write_text(probe.stdout + probe.stderr)
        finally:
            if process.poll() is None:
                process.send_signal(signal.SIGINT)
                try:
                    process.wait(timeout=20.0)
                except subprocess.TimeoutExpired:
                    os.killpg(process.pid, signal.SIGTERM)
                    process.wait(timeout=10.0)
                    raise RuntimeError(f'Mission did not stop on SIGINT: {directory}')
    log = (directory / 'launch.txt').read_text()
    if process.returncode != 0 or 'Traceback' in log or 'process has died' in log:
        raise RuntimeError(f'Mission process failed; inspect {directory / "launch.txt"}')
    if log.count('process has finished cleanly') != 4:
        raise RuntimeError(f'Expected four clean node exits: {directory}')
    lines = [line for line in probe.stdout.splitlines() if line.startswith('{')]
    if not lines or probe.returncode not in (0, 1):
        raise RuntimeError(f'Acceptance probe failed: {directory / "probe.txt"}')
    acceptance = json.loads(lines[-1])
    summary = json.loads((directory / 'summary.json').read_text())
    with (directory / 'metrics.csv').open() as stream:
        rows = list(csv.DictReader(stream))
    if not rows or int(rows[-1]['collected']) != summary['items_collected']:
        raise RuntimeError(f'CSV/summary collection mismatch: {directory}')
    if abs(float(rows[-1]['path_length']) - summary['path_length_m']) > 0.02:
        raise RuntimeError(f'CSV/summary path mismatch: {directory}')
    return {
        'seed': seed, 'current_m_s': current, 'passed': acceptance['passed'],
        'acceptance': acceptance, 'summary': summary,
        'time_to_11_s': next((float(r['t']) for r in rows if int(r['collected']) >= 11), None),
        'time_to_12_s': next((float(r['t']) for r in rows if int(r['collected']) >= 12), None),
        'output_directory': directory.name,
    }


def main() -> None:
    """Write attributable experiment results incrementally without overwriting runs."""
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output-dir', type=Path, default=ROOT / 'log/experiments')
    args = parser.parse_args()
    output = args.output_dir.expanduser().resolve()
    output.mkdir(parents=True, exist_ok=True)
    if any(output.iterdir()):
        parser.error('output directory must be empty; choose a new directory for each matrix')
    env = dict(os.environ, PYTHONNOUSERSITE='1')
    env.setdefault('ROS_DOMAIN_ID', '73')
    env.setdefault('ROS_AUTOMATIC_DISCOVERY_RANGE', 'LOCALHOST')
    files = sorted(ROOT.glob('src/**/*.py')) + sorted(ROOT.glob('src/**/*.yaml'))
    files = [p for p in files if '__pycache__' not in p.parts and 'egg-info' not in str(p)]
    report = {
        'started_utc': datetime.now(timezone.utc).isoformat(),
        'source_sha256': {
            str(p.relative_to(ROOT)): hashlib.sha256(p.read_bytes()).hexdigest() for p in files
        },
        'settings': {'seeds': [1, 2, 3], 'currents_m_s': [0.0, 0.05, 0.15],
                     'n_trash': 12, 'timeout_s': 420.0, 'min_ratio': 0.9, 'max_bank_hits': 3},
        'runs': [],
    }
    for current in report['settings']['currents_m_s']:
        for seed in report['settings']['seeds']:
            print(f'START seed={seed} current={current}', flush=True)
            run = run_mission(seed, current, output / f'seed_{seed}_current_{current}', env)
            report['runs'].append(run)
            (output / 'experiments.json').write_text(json.dumps(report, indent=2) + '\n')
            print('RESULT ' + json.dumps(run), flush=True)
    report['finished_utc'] = datetime.now(timezone.utc).isoformat()
    (output / 'experiments.json').write_text(json.dumps(report, indent=2) + '\n')
    result_path = output / 'experiments.json'
    print(f'Completed {len(report["runs"])} experiments: {result_path}', flush=True)
    if not all(run['passed'] for run in report['runs']):
        raise SystemExit(1)


if __name__ == '__main__':
    main()
