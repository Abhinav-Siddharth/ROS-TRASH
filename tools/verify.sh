#!/usr/bin/env bash
# Verification script for trash_boat
# Usage: ./tools/verify.sh [--no-integration]

set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
WORKSPACE_DIR="$(cd "${SCRIPT_DIR}/.." && pwd)"
cd "${WORKSPACE_DIR}"

NO_INTEGRATION=false
if [ "$1" == "--no-integration" ]; then
    NO_INTEGRATION=true
fi

# Source ROS 2 Jazzy if not already in path
if [ -z "${ROS_DISTRO}" ]; then
    if [ -f "/opt/ros/jazzy/setup.bash" ]; then
        source /opt/ros/jazzy/setup.bash
    fi
fi

echo "=========================================="
echo "1. Building workspace"
echo "=========================================="
colcon build --symlink-install

echo "=========================================="
echo "2. Running unit and lint tests"
echo "=========================================="
source install/setup.bash
colcon test
colcon test-result --verbose

if [ "${NO_INTEGRATION}" = true ]; then
    echo "=========================================="
    echo "Unit-only verification completed successfully!"
    echo "=========================================="
    exit 0
fi

echo "=========================================="
echo "3. Running integration acceptance tests"
echo "=========================================="
SEEDS=(1 2 3)

cleanup() {
    if [ -n "${LAUNCH_PID}" ]; then
        kill -INT "${LAUNCH_PID}" 2>/dev/null || true
        wait "${LAUNCH_PID}" 2>/dev/null || true
    fi
}
trap cleanup EXIT INT TERM

for SEED in "${SEEDS[@]}"; do
    echo "------------------------------------------"
    echo "Running acceptance check for SEED=${SEED}..."
    echo "------------------------------------------"

    ros2 launch trash_boat_bringup mission.launch.py seed:="${SEED}" n_trash:=12 > "log_mission_${SEED}.txt" 2>&1 &
    LAUNCH_PID=$!

    # Wait briefly for nodes to start up
    sleep 3

    set +e
    python3 tools/acceptance_check.py --total 12 --timeout 420.0 --min-ratio 0.9 --max-bank-hits 3
    CHECK_STATUS=$?
    set -e

    kill -INT "${LAUNCH_PID}" 2>/dev/null || true
    wait "${LAUNCH_PID}" 2>/dev/null || true
    unset LAUNCH_PID

    if [ ${CHECK_STATUS} -ne 0 ]; then
        echo "FAILED: Acceptance check failed for SEED=${SEED}"
        exit 1
    fi
    echo "PASSED: SEED=${SEED} acceptance check passed"
    sleep 2
done

echo "=========================================="
echo "All acceptance checks PASSED successfully!"
echo "=========================================="
exit 0
