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

"""Render scientific result figures from measured, archived VRX trials."""

import argparse
import csv
import json
from pathlib import Path

import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt


def main() -> None:
    """Read archived measurements and save duration and trajectory figures."""
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--results', type=Path, default=Path('docs/results/vrx/experiments.json'))
    parser.add_argument('--images', type=Path, default=Path('docs/img'))
    args = parser.parse_args()
    report = json.loads(args.results.read_text())
    results = report['runs']
    args.images.mkdir(parents=True, exist_ok=True)
    plt.rcParams.update({'font.size': 10, 'axes.spines.top': False,
                         'axes.spines.right': False, 'figure.facecolor': '#f7fafc'})
    figure, axes = plt.subplots(1, 2, figsize=(13, 4.8), layout='constrained')
    names = [row['case'].replace('_', '\n') for row in results]
    times = [row['sim_seconds'] for row in results]
    colors = ['#157d92' if row['passed'] else '#c44838' for row in results]
    bars = axes[0].bar(names, times, color=colors, width=0.65)
    axes[0].axhline(420, color='#9c3d34', linestyle='--', label='420 s acceptance deadline')
    for bar, row in zip(bars, results):
        axes[0].text(bar.get_x() + bar.get_width() / 2, bar.get_height() + 7,
                     f"{row['collected']}/12\n{row['bank_hits']} hits", ha='center', fontsize=8)
    axes[0].set_ylim(0, max(450, max(times) + 50))
    axes[0].set_ylabel('Simulation time to completion (s)')
    axes[0].set_title('Actual autonomous collection trials', weight='bold')
    axes[0].legend(loc='upper left', fontsize=8)
    axes[0].grid(axis='y', alpha=0.15)
    for row in results:
        if not row['case'].startswith('nominal'):
            continue
        with (args.results.parent / row['case'] / 'metrics.csv').open() as stream:
            trajectory = list(csv.DictReader(stream))
        axes[1].plot([float(r['x']) for r in trajectory],
                     [float(r['y']) for r in trajectory], linewidth=1.5,
                     label=f"Seed {row['seed']}")
    axes[1].axhline(4, color='#566557')
    axes[1].axhline(-4, color='#566557')
    axes[1].axhspan(-2.2, 2.2, color='#15859a', alpha=0.05)
    axes[1].set(xlabel='Downstream position (m)', ylabel='Lateral position (m)',
                xlim=(0, 60), ylim=(-4.3, 4.3))
    axes[1].set_title('Measured nominal boat trajectories', weight='bold')
    axes[1].legend(loc='lower left')
    axes[1].grid(alpha=0.15)
    figure.suptitle('VRX physical boat • image-only trash localization',
                   fontsize=15, weight='bold')
    figure.savefig(args.images / 'vrx_results.png', dpi=180)
    plt.close(figure)


if __name__ == '__main__':
    main()
