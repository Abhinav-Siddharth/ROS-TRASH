#!/usr/bin/env bash
# Copyright 2026 Abhinav Siddharth
# SPDX-License-Identifier: Apache-2.0
# Download only the explicitly approved, pinned official VRX dependency.
set -euo pipefail
cd "$(dirname "${BASH_SOURCE[0]}")/.."
vrx_commit=03eae362bb544f630595acd53b931e4a7060dffd
if [[ ! -d external/vrx/.git ]]; then
  mkdir -p external
  git clone --depth 1 --branch v3.1.0 https://github.com/osrf/vrx.git external/vrx
fi
actual_commit=$(git -C external/vrx rev-parse HEAD)
if [[ "$actual_commit" != "$vrx_commit" ]]; then
  echo "Wrong VRX version: $actual_commit; expected $vrx_commit" >&2
  exit 1
fi
if [[ -n $(git -C external/vrx status --porcelain) ]]; then
  echo 'VRX checkout is modified; preserve your changes and restore the pinned source.' >&2
  exit 1
fi
set +u
source /opt/ros/jazzy/setup.bash
set -u
export PYTHONNOUSERSITE=1
# Use rosdep explicitly if system dependencies are missing; no implicit sudo or pip.
echo 'Pinned VRX source verified. Resolve declared dependencies if needed with:'
echo '  rosdep install --from-paths src external/vrx --ignore-src -y --rosdistro jazzy'
echo 'Build: colcon build --symlink-install --parallel-workers 2'
