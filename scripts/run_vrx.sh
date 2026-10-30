#!/usr/bin/env bash
# Copyright 2026 Abhinav Siddharth
# SPDX-License-Identifier: Apache-2.0
set -euo pipefail
workspace=$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)
cd "$workspace"
if [[ ! -f /opt/ros/jazzy/setup.bash ]]; then
  echo 'ROS 2 Jazzy is required at /opt/ros/jazzy.' >&2
  exit 1
fi
export PYTHONNOUSERSITE=1
export ROS_DOMAIN_ID="${ROS_DOMAIN_ID:-83}"
export ROS_AUTOMATIC_DISCOVERY_RANGE=LOCALHOST
export GZ_IP="${GZ_IP:-127.0.0.1}"
export GZ_PARTITION="${GZ_PARTITION:-trash_boat_vrx_${ROS_DOMAIN_ID}}"
export ROS_LOG_DIR="${ROS_LOG_DIR:-$workspace/log/ros}"
export QT_QPA_PLATFORM="${QT_QPA_PLATFORM:-xcb}"
mkdir -p "$ROS_LOG_DIR"
set +u
source /opt/ros/jazzy/setup.bash
set -u
if [[ ! -d external/vrx/.git ]]; then
  echo 'Fetch the pinned dependency first: ./scripts/bootstrap_vrx.sh' >&2
  exit 1
fi
expected=03eae362bb544f630595acd53b931e4a7060dffd
if [[ $(git -C external/vrx rev-parse HEAD) != "$expected" ]]; then
  echo 'VRX version mismatch. See dependencies.repos and bootstrap_vrx.sh.' >&2
  exit 1
fi
if [[ ! -f install/trash_boat_vrx/share/trash_boat_vrx/package.xml ]]; then
  echo 'Build first: colcon build --symlink-install --parallel-workers 2' >&2
  exit 1
fi
set +u
source install/setup.bash
set -u
output_dir="$workspace/log/vrx_demo_$(date +%Y%m%d_%H%M%S)"
echo "VRX mission: domain=$ROS_DOMAIN_ID partition=$GZ_PARTITION"
echo "Metrics default: $output_dir"
echo 'Close Gazebo or press Ctrl-C to stop the mission and flush its summary.'
exec ros2 launch trash_boat_vrx mission.launch.py "output_dir:=$output_dir" "$@"
