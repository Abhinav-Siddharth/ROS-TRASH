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

"""Launch the offline VRX world and its explicit ROS interfaces."""

import os
from pathlib import Path
import shutil
import signal
import tempfile

from ament_index_python.packages import get_package_prefix, get_package_share_directory
from launch import LaunchDescription
from launch.actions import (DeclareLaunchArgument, EmitEvent, ExecuteProcess, LogInfo,
                            OpaqueFunction, RegisterEventHandler)
from launch.event_handlers import OnProcessExit, OnShutdown
from launch.events import Shutdown
from launch.substitutions import LaunchConfiguration
from launch_ros.actions import Node

from trash_boat_vrx.world import make_world, WorldConfig


def start_world(context) -> list:
    """Generate this run's world, then start Gazebo with fail-fast cleanup."""
    def value(name: str) -> str:
        return LaunchConfiguration(name).perform(context)

    config = WorldConfig(seed=int(value('seed')), n_trash=int(value('n_trash')),
                         current=float(value('current')),
                         wave_amplitude=float(value('wave_amplitude')),
                         boat_x=float(value('boat_x')), boat_y=float(value('boat_y')),
                         boat_yaw=float(value('boat_yaw')))
    directory = Path(tempfile.mkdtemp(prefix='trash_boat_vrx_'))
    world_path = directory / 'canal.sdf'
    world_path.write_text(make_world(config))
    args = ['gz', 'sim', '-r', '-v', '3']
    if value('headless').lower() == 'true':
        args += ['-s', '--headless-rendering']
    args.append(str(world_path))
    paths = [os.path.join(get_package_prefix(package), 'lib')
             for package in ['trash_boat_vrx', 'vrx_gz']]
    paths.append(os.environ.get('GZ_SIM_SYSTEM_PLUGIN_PATH', ''))
    transport = {'GZ_PARTITION': value('partition'),
                 'GZ_IP': os.environ.get('GZ_IP', '127.0.0.1')}
    simulator = ExecuteProcess(cmd=args, output='screen', sigterm_timeout='10',
                               additional_env={**transport,
                                               'GZ_SIM_SYSTEM_PLUGIN_PATH': ':'.join(paths)})
    share = get_package_share_directory('trash_boat_vrx')
    bridge = Node(package='ros_gz_bridge', executable='parameter_bridge',
                  name='vrx_bridge', output='screen', parameters=[{
                      'config_file': os.path.join(share, 'config', 'bridge.yaml'),
                      'use_sim_time': True,
                  }], additional_env=transport)

    def cleanup(_event, _context) -> list:
        if directory.exists():
            shutil.rmtree(directory)
        return []

    return [LogInfo(msg=f'Generated VRX canal: {world_path}'),
            RegisterEventHandler(OnShutdown(on_shutdown=cleanup)),
            RegisterEventHandler(OnProcessExit(target_action=simulator,
                                 on_exit=[EmitEvent(event=Shutdown(reason='Gazebo exited'))])),
            RegisterEventHandler(OnProcessExit(target_action=bridge,
                                 on_exit=[EmitEvent(event=Shutdown(reason='Bridge exited'))])),
            simulator, bridge]


def generate_launch_description() -> LaunchDescription:
    """Declare reproducible world parameters and start the simulator."""
    if signal.getsignal(signal.SIGINT) == signal.SIG_IGN:
        signal.signal(signal.SIGINT, signal.default_int_handler)
    defaults = {'seed': '42', 'n_trash': '12', 'current': '0.05',
                'wave_amplitude': '0.0', 'headless': 'false',
                'partition': os.environ.get('GZ_PARTITION', 'trash_boat_vrx'),
                'boat_x': '2.0', 'boat_y': '0.0', 'boat_yaw': '0.0'}
    return LaunchDescription([
        *[DeclareLaunchArgument(key, default_value=value) for key, value in defaults.items()],
        OpaqueFunction(function=start_world),
    ])
