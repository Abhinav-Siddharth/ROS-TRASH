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

"""Archive measured VRX trials without rewriting their raw telemetry."""

import argparse
import csv
import json
from pathlib import Path
import shutil


SOURCES = {
    'nominal_seed1': 'vrx_m4_seed1_docking', 'nominal_seed2': 'vrx_m5_nominal_seed2',
    'nominal_seed3': 'vrx_m5_nominal_seed3', 'zero_current': 'vrx_m5_zero_current',
    'strong_current': 'vrx_m5_strong_current', 'small_waves': 'vrx_m5_small_waves',
    'larger_waves': 'vrx_m5_larger_waves',
}


def main() -> None:
    """Copy original acceptance/CSV/summary files and construct an attributable report."""
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--provenance', required=True, type=Path)
    parser.add_argument('--output', type=Path, default=Path('docs/results/vrx'))
    args = parser.parse_args()
    provenance = json.loads(args.provenance.read_text())
    args.output.mkdir(parents=True, exist_ok=False)
    runs = []
    for case, source in SOURCES.items():
        directory = Path('log') / source
        result = json.loads((directory / 'acceptance.json').read_text())
        summary = json.loads((directory / 'summary.json').read_text())
        with (directory / 'metrics.csv').open() as stream:
            rows = list(csv.DictReader(stream))
        assert int(rows[-1]['collected']) == result['collected'] == summary['items_collected']
        assert int(rows[-1]['bank_hits']) == result['bank_hits'] == summary['bank_hits']
        destination = args.output / case
        destination.mkdir()
        for filename in ['acceptance.json', 'summary.json', 'metrics.csv']:
            shutil.copyfile(directory / filename, destination / filename)
        result['case'] = case
        result['source_directory'] = str(directory)
        result['provenance'] = provenance
        runs.append(result)
    report = {'provenance': provenance, 'runs': runs,
              'all_passed': all(row['passed'] for row in runs)}
    (args.output / 'experiments.json').write_text(json.dumps(report, indent=2) + '\n')
    lines = [
        '# Measured VRX results', '',
        'These are real Gazebo Harmonic / VRX missions, separate from the reference',
        'simulator results in RESULTS.md. Images were rendered by Gazebo; the actual',
        'ROS perception, marine decision logic and force controller ran in every trial.', '',
        f"Runtime commit: `{provenance['commit']}`.",
        f"Runtime source SHA-256: `{provenance['runtime_sha256']}`.",
        f"Upstream VRX commit: `{provenance['vrx_commit']}` (v3.1.0).", '',
        '| Case | Seed | Current (m/s) | Wave amplitude (m) | Items | Sim time (s) | '
        'Wall time (s) | Items/min | Path (m) | Hits | Result |',
        '|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---|',
    ]
    for row in runs:
        metrics = row['metrics']
        cells = [row['case'], row['seed'], row['current'], row['wave_amplitude'],
                 f"{row['collected']}/12", f"{row['sim_seconds']:.2f}",
                 row['wall_seconds'], metrics['items_per_min'], metrics['path_length_m'],
                 row['bank_hits'], 'PASS' if row['passed'] else 'FAIL']
        lines.append('| ' + ' | '.join(str(cell) for cell in cells) + ' |')
    lines += ['', '![Measured durations and trajectories](img/vrx_results.png)', '',
              'All missions used 12 items, a 60 × 8 m canal, unchanged physical intake',
              'bounds (0–1.5 m forward, ±1 m lateral), and the same declared speed limits.',
              'Passing requires ≥11/12 within 420 simulated seconds and ≤3 actual bank',
              'contact transitions, rendered data, consistent telemetry and clean shutdown.', '',
              'The nominal seed-2 run had three contact transitions near the end bank.',
              'It satisfies the contract but demonstrates that collision avoidance is not',
              'perfect. The scorer was not filtered or relaxed. Earlier failed development',
              'attempts are retained in verification/vrx/M4_attempt_*.json.', '',
              'Wave amplitude is the configured VRX analytic component amplitude, not',
              'significant wave height. The water visual is flat; VRX buoyancy forces',
              'and object/boat motion use the configured wave field. Current drives trash',
              'through physical forces; the boat drag model assumes otherwise still water.', '',
              '## Reproduce', '', 'From the workspace after setup/build:', '', '```bash',
              'export PYTHONNOUSERSITE=1', 'source /opt/ros/jazzy/setup.bash',
              'source install/setup.bash',
              'python3 docs/run_vrx_experiments.py --output log/vrx_repeat --workers 2',
              '```', '', 'The output directory must be new. Each case uses an isolated ROS',
              'domain and Gazebo partition; failures remain visible and return nonzero.',
              'Raw archived acceptance JSON, CSV and summaries are in results/vrx/.', '']
    Path('docs/RESULTS_VRX.md').write_text('\n'.join(lines))
    if not report['all_passed']:
        raise SystemExit(1)


if __name__ == '__main__':
    main()
