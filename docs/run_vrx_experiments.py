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

"""Reproduce the VRX nominal and disturbance matrix with real mission processes."""

import argparse
from concurrent.futures import ThreadPoolExecutor
import hashlib
import json
import os
from pathlib import Path
import subprocess
import sys


CASES = [
    ('nominal_seed1', 1, 0.05, 0.0), ('nominal_seed2', 2, 0.05, 0.0),
    ('nominal_seed3', 3, 0.05, 0.0), ('zero_current', 1, 0.0, 0.0),
    ('strong_current', 1, 0.15, 0.0), ('small_waves', 1, 0.05, 0.05),
    ('larger_waves', 3, 0.05, 0.10),
]


def source_provenance(workspace: Path) -> dict:
    """Hash the tested runtime sources and record local/upstream commit identities."""
    digest = hashlib.sha256()
    paths = sorted(path for path in (workspace / 'src').rglob('*')
                   if path.is_file() and '__pycache__' not in path.parts)
    for path in paths:
        digest.update(str(path.relative_to(workspace)).encode())
        digest.update(path.read_bytes())
    return {
        'commit': subprocess.check_output(['git', 'rev-parse', 'HEAD'],
                                          cwd=workspace, text=True).strip(),
        'runtime_sha256': digest.hexdigest(),
        'vrx_commit': subprocess.check_output(['git', '-C', 'external/vrx', 'rev-parse', 'HEAD'],
                                              cwd=workspace, text=True).strip(),
    }


def main() -> None:
    """Run isolated seeds/currents/waves; never overwrite or suppress failed trials."""
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output', required=True, type=Path)
    parser.add_argument('--workers', choices=[1, 2], default=1, type=int)
    parser.add_argument('--domain-base', type=int, default=100)
    args = parser.parse_args()
    workspace = Path(__file__).resolve().parents[1]
    args.output = args.output.resolve()
    args.output.mkdir(parents=True, exist_ok=False)
    provenance = source_provenance(workspace)
    (args.output / 'provenance.json').write_text(json.dumps(provenance, indent=2) + '\n')

    def run(case: tuple) -> dict:
        index, (name, seed, current, amplitude) = case
        directory = args.output / name
        environment = dict(os.environ, ROS_DOMAIN_ID=str(args.domain_base + index),
                           GZ_PARTITION=f'trash_boat_experiment_{os.getpid()}_{index}',
                           GZ_IP='127.0.0.1')
        command = ['ros2', 'run', 'trash_boat_vrx', 'verify_mission',
                   '--seed', str(seed), '--current', str(current),
                   '--wave-amplitude', str(amplitude), '--output', str(directory)]
        with (args.output / (name + '.txt')).open('w') as stream:
            completed = subprocess.run(command, cwd=workspace, env=environment,
                                       stdout=stream, stderr=subprocess.STDOUT, check=False)
        result = json.loads((directory / 'acceptance.json').read_text())
        result['case'] = name
        result['exit_code'] = completed.returncode
        result['provenance'] = provenance
        sys.stdout.write(json.dumps({key: result[key] for key in
                         ['case', 'passed', 'collected', 'bank_hits', 'sim_seconds']}) + '\n')
        sys.stdout.flush()
        return result

    with ThreadPoolExecutor(max_workers=args.workers) as pool:
        results = list(pool.map(run, enumerate(CASES)))
    (args.output / 'experiments.json').write_text(json.dumps(results, indent=2) + '\n')
    if not all(result['passed'] and result['exit_code'] == 0 for result in results):
        raise SystemExit(1)


if __name__ == '__main__':
    main()
