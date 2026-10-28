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

"""Launch file for complete trash_boat mission (sim, perception, control, metrics)."""

import os
import signal

from ament_index_python.packages import get_package_share_directory
from launch import LaunchDescription
from launch.actions import DeclareLaunchArgument
from launch.substitutions import LaunchConfiguration
from launch_ros.actions import Node
from launch_ros.descriptions import ParameterValue


def generate_launch_description() -> LaunchDescription:
    """Generate launch description for the full mission."""
    # Bash background jobs can inherit SIGINT as ignored. Launch's wakeup-fd
    # signal manager needs a Python handler to receive the verifier's SIGINT.
    if signal.getsignal(signal.SIGINT) == signal.SIG_IGN:
        signal.signal(signal.SIGINT, signal.default_int_handler)

    pkg_bringup = get_package_share_directory('trash_boat_bringup')
    params_file = os.path.join(pkg_bringup, 'config', 'params.yaml')

    seed_arg = DeclareLaunchArgument(
        'seed',
        default_value='42',
        description='Simulation random seed',
    )
    n_trash_arg = DeclareLaunchArgument(
        'n_trash',
        default_value='12',
        description='Total number of trash items to spawn',
    )
    current_arg = DeclareLaunchArgument(
        'current', default_value='0.05', description='Downstream trash drift in metres/second',
    )
    output_dir_arg = DeclareLaunchArgument(
        'output_dir', default_value='~/trash_boat_metrics', description='Metrics output directory',
    )

    seed_val = ParameterValue(LaunchConfiguration('seed'), value_type=int)
    n_trash_val = ParameterValue(LaunchConfiguration('n_trash'), value_type=int)
    current_val = ParameterValue(LaunchConfiguration('current'), value_type=float)

    canal_sim_node = Node(
        package='trash_boat_sim',
        executable='canal_sim',
        name='canal_sim',
        output='screen',
        parameters=[
            params_file,
            {
                'seed': seed_val,
                'n_trash': n_trash_val,
                'current': current_val,
            },
        ],
    )

    trash_detector_node = Node(
        package='trash_boat_perception',
        executable='trash_detector',
        name='trash_detector',
        output='screen',
        parameters=[params_file],
    )

    collector_brain_node = Node(
        package='trash_boat_control',
        executable='collector_brain',
        name='collector_brain',
        output='screen',
        parameters=[params_file],
    )

    metrics_logger_node = Node(
        package='trash_boat_control',
        executable='metrics_logger',
        name='metrics_logger',
        output='screen',
        parameters=[params_file, {
            'output_dir': ParameterValue(LaunchConfiguration('output_dir'), value_type=str),
        }],
    )

    return LaunchDescription(
        [
            seed_arg,
            n_trash_arg,
            current_arg,
            output_dir_arg,
            canal_sim_node,
            trash_detector_node,
            collector_brain_node,
            metrics_logger_node,
        ]
    )
