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

"""Verify force signs, saturation, braking and independent input watchdogs."""

from dataclasses import replace
from pathlib import Path
import xml.etree.ElementTree as ET

import pytest
from trash_boat_vrx.thruster_core import thruster_forces, ThrusterConfig
from trash_boat_vrx.world import make_world, WorldConfig
import yaml


def test_force_signs_and_feedback() -> None:
    """Require forward force, positive left-turn torque, and active braking."""
    config = ThrusterConfig()
    left, right = thruster_forces(1, (0.8, 0), 1, (0, 0), 1, config)
    assert 0 < left == right <= config.max_thrust
    left, right = thruster_forces(1, (0, 1.2), 1, (0, 0), 1, config)
    assert left < 0 < right
    left, right = thruster_forces(1, (0, 0), 1, (0.8, 0), 1, config)
    assert left == right < 0
    left, right = thruster_forces(1, (0.8, 1.2), 1, (-10, -10), 1, config)
    assert max(abs(left), abs(right)) == pytest.approx(config.max_thrust)


@pytest.mark.parametrize('target,stamp,velocity,velocity_stamp', [
    (None, 1, (0, 0), 1), ((0.8, 0), None, (0, 0), 1),
    ((0.8, 0), 0, (0, 0), 1), ((0.8, 0), 1, (0, 0), 0),
    ((0.8, 0), 2, (0, 0), 1), ((float('nan'), 0), 1, (0, 0), 1),
])
def test_watchdogs(target, stamp, velocity, velocity_stamp) -> None:
    """Stop for missing, stale, future or nonfinite commands and localization."""
    assert thruster_forces(1, target, stamp, velocity, velocity_stamp,
                           ThrusterConfig()) == (0.0, 0.0)


def test_invalid_configuration() -> None:
    """Reject impossible actuator geometry and invalid limits."""
    with pytest.raises(ValueError):
        replace(ThrusterConfig(), arm=0).validate()
    with pytest.raises(ValueError):
        replace(ThrusterConfig(), surge_gain=float('inf')).validate()


def test_sdf_controller_and_yaml_agree() -> None:
    """Keep actuator arm, saturation and watchdog consistent across interfaces."""
    params = yaml.safe_load((Path(__file__).parents[1] / 'config/params.yaml').read_text())
    control = params['thruster_controller']['ros__parameters']
    config = ThrusterConfig()
    for name, value in vars(config).items():
        assert control[name] == value
    root = ET.fromstring(make_world(WorldConfig()))
    scorer = root.find('.//plugin[@name="trash_boat_vrx::TrashWorld"]')
    assert float(scorer.find('thruster_arm').text) == config.arm
    assert float(scorer.find('thrust_limit').text) == config.max_thrust
    assert float(scorer.find('command_timeout').text) == config.command_timeout
