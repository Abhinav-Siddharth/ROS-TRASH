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

"""Thin ROS wrapper reusing the existing collector interfaces and state machine."""

from trash_boat_control.collector_brain import CollectorBrain
from trash_boat_vrx.marine_logic import MarineCollectorLogic
from trash_boat_vrx.runtime import run_node


class MarineBrain(CollectorBrain):
    """Adapt only the physical hull's approach geometry, with no scoring inputs."""

    def __init__(self) -> None:
        super().__init__()
        defaults = {'shore_clearance': 1.8, 'end_clearance': 1.4,
                    'arrival_radius': 0.25, 'alignment_distance': 1.1,
                    'dock_speed': 0.3, 'dock_heading_tolerance': 0.15,
                    'dock_bank_margin': 1.1, 'retreat_speed': 0.3,
                    'turn_in_place_threshold': 0.6}
        for key, value in defaults.items():
            self.declare_parameter(key, value)
        self.logic = MarineCollectorLogic(self.logic, **{
            key: self.get_parameter(key).value for key in defaults
        })


def main(args: list[str] | None = None) -> None:
    """Run the physical boat's camera-only collector brain."""
    run_node(MarineBrain, args)
