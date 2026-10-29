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

"""Run the full image-driven collector in the physical VRX canal."""

import os
import signal

from ament_index_python.packages import get_package_share_directory
from launch import LaunchDescription
from launch.actions import DeclareLaunchArgument, EmitEvent, IncludeLaunchDescription
from launch.events import Shutdown
from launch.launch_description_sources import PythonLaunchDescriptionSource
from launch.substitutions import LaunchConfiguration
from launch_ros.actions import Node
from launch_ros.descriptions import ParameterValue


def generate_launch_description() -> LaunchDescription:
    """Start real simulator, bridges, perception, decision, actuation and metrics."""
    if signal.getsignal(signal.SIGINT) == signal.SIG_IGN:
        signal.signal(signal.SIGINT, signal.default_int_handler)
    share = get_package_share_directory('trash_boat_vrx')
    baseline = os.path.join(get_package_share_directory('trash_boat_bringup'),
                            'config', 'params.yaml')
    profile = os.path.join(share, 'config', 'params.yaml')
    defaults = {'seed': '42', 'n_trash': '12', 'current': '0.05',
                'wave_amplitude': '0.0', 'headless': 'false',
                'partition': os.environ.get('GZ_PARTITION', 'trash_boat_vrx'),
                'output_dir': '~/trash_boat_vrx_metrics'}
    world = IncludeLaunchDescription(
        PythonLaunchDescriptionSource(os.path.join(share, 'launch', 'world.launch.py')),
        launch_arguments={key: LaunchConfiguration(key) for key in defaults
                          if key != 'output_dir'}.items(),
    )
    stop = [EmitEvent(event=Shutdown(reason='A required mission node exited'))]
    detector = Node(package='trash_boat_vrx', executable='water_detector',
                    name='water_detector', output='screen', parameters=[profile], on_exit=stop)
    thrusters = Node(package='trash_boat_vrx', executable='thruster_controller',
                     name='thruster_controller', output='screen',
                     parameters=[profile], on_exit=stop)
    brain = Node(package='trash_boat_vrx', executable='marine_brain',
                 name='collector_brain', output='screen',
                 parameters=[baseline, profile, {'use_sim_time': True}], on_exit=stop)
    metrics = Node(package='trash_boat_control', executable='metrics_logger',
                   name='metrics_logger', output='screen', parameters=[baseline, {
                       'use_sim_time': True,
                       'output_dir': ParameterValue(
                           LaunchConfiguration('output_dir'), value_type=str),
                   }], on_exit=stop)
    return LaunchDescription([
        *[DeclareLaunchArgument(key, default_value=value) for key, value in defaults.items()],
        world, detector, thrusters, brain, metrics,
    ])
