# Project Progress Log

This log records progress and verification output milestone-by-milestone.

---

## Milestone M0: Workspace Skeleton, Tooling & Package Structure

- **Status**: PASSED
- **Gate**: `colcon build` succeeds; `colcon test` passes.
- **Commands Run**:
  ```bash
  ./tools/verify.sh --no-integration
  ```
- **Real Output Excerpt**:
  ```text
  ==========================================
  1. Building workspace
  ==========================================
  Summary: 4 packages finished [2.87s]
  ==========================================
  2. Running unit and lint tests
  ==========================================
  Summary: 4 packages finished [1.87s]
  Summary: 12 tests, 0 errors, 0 failures, 0 skipped
  ==========================================
  Unit-only verification completed successfully!
  ==========================================
  ```
- **Result**: All 4 packages (`trash_boat_sim`, `trash_boat_perception`, `trash_boat_control`, `trash_boat_bringup`) built and passed copyright, flake8, and pep257 linter tests with 0 errors, 0 failures, 0 skipped.

---

## Milestone M1: Simulator (`canal_sim`) & `sim.launch.py`

- **Status**: PASSED
- **Gate**: Sim tests pass; `ros2 topic hz /camera/image_raw` is ~10 Hz; save one frame to `docs/img/sim_frame.png`.
- **Commands Run**:
  ```bash
  # Unit & lint tests
  ./tools/verify.sh --no-integration

  # Verify camera frame rate and capture frame
  ros2 launch trash_boat_bringup sim.launch.py
  ros2 topic hz /camera/image_raw
  # captured frame via CvBridge to docs/img/sim_frame.png
  ```
- **Real Output Excerpt**:
  ```text
  Summary: 4 packages finished [2.72s]
  Summary: 16 tests, 0 errors, 0 failures, 0 skipped
  Unit-only verification completed successfully!

  average rate: 10.003
  	min: 0.092s max: 0.109s std dev: 0.00426s window: 33
  Saved docs/img/sim_frame.png successfully
  ```
- **Result**: `canal_sim` node running with unicycle physics, seeded trash spawning, trash drift, scoop collection, bank contact detection, and 10 Hz camera rendering. 4 unit tests in `test_canal_sim.py` passed cleanly. Camera publishing verified at 10.0 Hz and reference frame saved to `docs/img/sim_frame.png`.

