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

"""Check launch wiring, metric provenance and camera-only decision boundaries."""

import ast
import importlib.util
import json
from pathlib import Path

import pytest

from trash_boat_vrx.verification import check_metrics


ROOT = Path(__file__).resolve().parents[1]


def test_launch_descriptions() -> None:
    """Load both real launch descriptions, including their installed dependencies."""
    for name in ['world', 'mission']:
        path = ROOT / 'launch' / (name + '.launch.py')
        spec = importlib.util.spec_from_file_location(name, path)
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)
        assert module.generate_launch_description().entities


def test_no_ground_truth_in_perception_or_control() -> None:
    """Reject forbidden simulator dependencies and trash status decision inputs."""
    for name in ['water_detector', 'projection', 'thruster_controller', 'thruster_core',
                 'marine_brain', 'marine_logic']:
        source = (ROOT / 'trash_boat_vrx' / (name + '.py')).read_text()
        for forbidden in ['trash_remaining', 'trash_collected', 'bank_hits', 'trash_boat_sim']:
            assert forbidden not in source
        if name in ['projection', 'thruster_core', 'marine_logic']:
            imports = [item for item in ast.walk(ast.parse(source))
                       if isinstance(item, (ast.Import, ast.ImportFrom))]
            assert all('rclpy' not in ast.unparse(item) for item in imports)


def test_metrics_provenance(tmp_path: Path) -> None:
    """Accept legitimate rounded telemetry and reject a mismatched summary."""
    (tmp_path / 'metrics.csv').write_text(
        't,x,y,collected,remaining,bank_hits,state,path_length\n'
        '80.25,50,0,12,0,0,COLLECT,54.583\n')
    summary = {'items_collected': 12, 'path_length_m': 54.58,
               'duration_s': 80.25, 'bank_hits': 0}
    (tmp_path / 'summary.json').write_text(json.dumps(summary))
    assert check_metrics(tmp_path, 12) == summary
    with pytest.raises(ValueError):
        check_metrics(tmp_path, 11)
    summary['path_length_m'] = 55.0
    (tmp_path / 'summary.json').write_text(json.dumps(summary))
    with pytest.raises(ValueError):
        check_metrics(tmp_path, 12)
