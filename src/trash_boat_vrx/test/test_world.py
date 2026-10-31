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

"""Check deterministic world generation and the frozen acceptance geometry."""

from dataclasses import replace
import random
import xml.etree.ElementTree as ET

import pytest

from trash_boat_vrx.world import make_world, spawn_positions, WorldConfig


def test_seeded_distribution() -> None:
    """Match the reference's uniform distribution without hardcoded locations."""
    config = WorldConfig(seed=1)
    rng = random.Random(1)
    expected = [(rng.uniform(8, 57), rng.uniform(-3.2, 3.2)) for _ in range(12)]
    assert spawn_positions(config) == expected
    assert spawn_positions(replace(config, seed=2)) != expected
    assert make_world(config) == make_world(config)


def test_real_physics_camera_and_intake() -> None:
    """Require real sensors, VRX force systems and the exact scoop bounds."""
    root = ET.fromstring(make_world(WorldConfig()))
    plugins = root.findall('.//plugin')
    assert any(p.attrib['name'] == 'vrx::Surface' for p in plugins)
    assert any(p.attrib['name'] == 'vrx::SimpleHydrodynamics' for p in plugins)
    assert root.find('.//sensor[@type="camera"]/camera/image/width').text == '400'
    contact = root.find('.//sensor[@type="contact"]/contact')
    assert len(contact.findall('collision')) == 3
    scorer = root.find('.//plugin[@name="trash_boat_vrx::TrashWorld"]')
    assert scorer.find('scoop_forward').text == '1.5'
    assert scorer.find('scoop_lateral').text == '1.0'
    models = root.findall('.//world/model')
    assert len([m for m in models if m.attrib['name'].startswith('trash_')]) == 13
    assert not root.findall('.//uri')
    assert not root.findall('.//plugin[@name="gz::sim::systems::VelocityControl"]')


@pytest.mark.parametrize('change', [
    {'wave_amplitude': -1}, {'n_trash': 0}, {'current': float('nan')},
    {'step_size': 0}, {'boat_y': 4.1},
])
def test_invalid_world_rejected(change: dict) -> None:
    """Fail early for bad launch parameters instead of emitting broken SDF."""
    with pytest.raises(ValueError):
        make_world(replace(WorldConfig(), **change))
