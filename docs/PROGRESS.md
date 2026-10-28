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

---

## Milestone M2: Perception (`trash_detector`) & `detector_core.py`

- **Status**: PASSED
- **Gate**: Detector tests pass; with the sim running, `/trash_detections` is non-empty when orange dots are in view.
- **Commands Run**:
  ```bash
  # Unit & lint tests
  ./tools/verify.sh --no-integration

  # Gate integration test
  ros2 run trash_boat_sim canal_sim &
  ros2 run trash_boat_perception trash_detector &
  # Commanded boat forward into view of trash and listened to /trash_detections
  ```
- **Real Output Excerpt**:
  ```text
  Summary: 4 packages finished [2.81s]
  Summary: 21 tests, 0 errors, 0 failures, 0 skipped
  Unit-only verification completed successfully!

  M2 Gate SUCCESS: Detected 1 trash item(s) on /trash_detections
  ```
- **Result**: `detector_core.py` implemented as pure module and verified across 5 unit tests (`pixel_to_body`, disc detection, background color rejection, distance sorting, and min area filtering). `trash_detector` node successfully processes `/camera/image_raw` and publishes body-frame detections on `/trash_detections` and circled detections on `/trash_detector/debug_image`.

---

## Milestone M3: Control Logic (`collector_brain`) & `logic.py`

- **Status**: PASSED
- **Gate**: Logic tests pass (`colcon test` clean).
- **Commands Run**:
  ```bash
  ./tools/verify.sh --no-integration
  ```
- **Real Output Excerpt**:
  ```text
  Summary: 4 packages finished [2.87s]
  Summary: 30 tests, 0 errors, 0 failures, 0 skipped
  Unit-only verification completed successfully!
  ```
- **Result**: `CollectorLogic` pure decision module implemented with 4-tier prioritized state machine (`AVOID_BANK` > `COLLECT` > `APPROACH` > `SEARCH`) along with quaternion and angle wrapping helpers. All 9 required logic test cases in `test_logic.py` and linters passed with 0 errors, 0 failures, 0 skipped.



