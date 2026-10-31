#!/usr/bin/env bash
# Copyright 2026 Abhinav Siddharth
# SPDX-License-Identifier: Apache-2.0
# Runs the actual physical missions; the reference verifier remains untouched.
set -euo pipefail
cd "$(dirname "${BASH_SOURCE[0]}")/.."
export PYTHONNOUSERSITE=1
export ROS_DOMAIN_ID="${ROS_DOMAIN_ID:-83}"
export ROS_AUTOMATIC_DISCOVERY_RANGE=LOCALHOST
export GZ_IP="${GZ_IP:-127.0.0.1}"
export ROS_LOG_DIR="${ROS_LOG_DIR:-$PWD/log/ros}"
export CMAKE_BUILD_PARALLEL_LEVEL="${CMAKE_BUILD_PARALLEL_LEVEL:-2}"
set +u
source /opt/ros/jazzy/setup.bash
set -u
colcon build --symlink-install --parallel-workers 2
set +u
source install/setup.bash
set -u
colcon test
colcon test-result --verbose
output_root="$PWD/log/vrx_verify_$(date +%Y%m%d_%H%M%S)"
mkdir -p "$output_root"
for seed in 1 2 3; do
  export GZ_PARTITION="trash_boat_verify_$$_${seed}"
  ros2 run trash_boat_vrx verify_mission --seed "$seed" \
    --output "$output_root/seed_$seed"
done
echo 'All three physical VRX acceptance missions PASSED.'
echo "Evidence: $output_root"
