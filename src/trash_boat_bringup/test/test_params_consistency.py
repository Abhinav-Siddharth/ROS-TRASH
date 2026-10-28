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

"""Test consistency of shared parameters across nodes and launch files validity."""

import importlib.util
import os
import signal
from types import ModuleType

import yaml


def _load_launch_module(file_name: str) -> ModuleType:
    launch_path = os.path.join(
        os.path.dirname(__file__), '..', 'launch', file_name
    )
    spec = importlib.util.spec_from_file_location(file_name, launch_path)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_params_consistency() -> None:
    """Assert shared parameter values match across nodes in params.yaml."""
    config_path = os.path.join(
        os.path.dirname(__file__), '..', 'config', 'params.yaml'
    )
    with open(config_path, 'r', encoding='utf-8') as f:
        params = yaml.safe_load(f)

    sim_p = params['canal_sim']['ros__parameters']
    det_p = params['trash_detector']['ros__parameters']
    brain_p = params['collector_brain']['ros__parameters']

    # Shared parameters checks
    assert sim_p['canal_length'] == brain_p['canal_length']
    assert sim_p['half_width'] == brain_p['half_width']
    assert sim_p['image_size'] == det_p['image_size']
    assert sim_p['pixels_per_meter'] == det_p['pixels_per_meter']


def test_launch_descriptions_generation() -> None:
    """Assert both sim and mission generate_launch_description return without error."""
    sim_mod = _load_launch_module('sim.launch.py')
    sim_ld = sim_mod.generate_launch_description()
    assert sim_ld is not None
    assert len(sim_ld.entities) > 0

    mission_mod = _load_launch_module('mission.launch.py')
    mission_ld = mission_mod.generate_launch_description()
    assert mission_ld is not None
    assert len(mission_ld.entities) > 0


def test_mission_restores_ignored_sigint() -> None:
    """Allow the verifier to stop a mission started as a Bash background job."""
    previous_handler = signal.getsignal(signal.SIGINT)
    try:
        signal.signal(signal.SIGINT, signal.SIG_IGN)
        mission_mod = _load_launch_module('mission.launch.py')
        mission_mod.generate_launch_description()
        assert signal.getsignal(signal.SIGINT) == signal.default_int_handler
    finally:
        signal.signal(signal.SIGINT, previous_handler)
