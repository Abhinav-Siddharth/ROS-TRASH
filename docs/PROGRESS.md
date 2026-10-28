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

## Milestone M4: Full mission integration and three-seed acceptance

- **Status**: PASSED (2026-10-28).
- **Changes**: Integrated the existing mission launch, parameter YAML, bringup tests,
  and metrics executable. Completed direct runtime/test dependency declarations.
  Fixed inherited SIGINT handling in mission launch and orderly shutdown in the
  simulator, detector, and controller; physics and decision algorithms are unchanged.
- **Commands run** (system Python packages, isolated domain):
  ```bash
  export PYTHONNOUSERSITE=1 ROS_LOG_DIR=/tmp/trash_boat_roslogs
  export ROS_DOMAIN_ID=73 ROS_AUTOMATIC_DISCOVERY_RANGE=LOCALHOST
  colcon build --symlink-install && colcon test && colcon test-result --verbose
  ./tools/verify.sh
  # Separate live observation while the mission ran:
  timeout --signal=INT 8 ros2 topic hz /camera/image_raw
  ```
- **Real output excerpts** (full verifier output: `docs/verification/M4.txt`):
  ```text
  Summary: 33 tests, 0 errors, 0 failures, 0 skipped
  {"passed": true, "received_sim_data": true, "collected": 12, "total": 12, "ratio": 1.0, "bank_hits": 0, "wall_seconds": 84.5}
  PASSED: SEED=1 acceptance check passed
  {"passed": true, "received_sim_data": true, "collected": 12, "total": 12, "ratio": 1.0, "bank_hits": 0, "wall_seconds": 84.4}
  PASSED: SEED=2 acceptance check passed
  {"passed": true, "received_sim_data": true, "collected": 12, "total": 12, "ratio": 1.0, "bank_hits": 0, "wall_seconds": 84.5}
  PASSED: SEED=3 acceptance check passed
  All acceptance checks PASSED successfully!
  ```
- **Additional observed output**:
  ```text
  average rate: 10.003
  {"images": 80, "nonempty_detections": 10, "states": ["APPROACH", "COLLECT", "SEARCH"], "example_detection": [1.2, 0.0]}
  {"exit_code": 0, "clean_node_exits": 4, "traceback": false}
  ```
  The rate command intentionally ended after eight seconds (timeout exit 124).
  The final JSON is a separate real launch/SIGINT regression with SIGINT initially
  ignored, reproducing the verifier's background-job environment.
- **Earlier failures and corrections**: User-site NumPy 2.5.0 caused an actual
  `cv_bridge` crash; system NumPy/OpenCV passed with `PYTHONNOUSERSITE=1`. Initial
  sandbox tests reported `32 tests, 4 errors, 1 failure` because the home ROS log path
  was read-only; a writable `ROS_LOG_DIR` fixed this. Copied generated installation
  files then caused `File exists` during rebuild; old build/install directories were
  preserved at `/tmp/trash_boat_old_generated_hm9k6a56` and rebuilt from scratch.
  A baseline mission passed seed 1 but hung in cleanup. A shutdown smoke check then
  exposed a detector context-shutdown race and an idle-subscriber wait; the final
  lifecycle regression and all three verifier shutdowns now pass.
- **Self-review**: `git diff --check` passed; no changes to `tools/` or `SPEC.md`;
  static checks found no ground-truth references in decision nodes and no ROS
  imports in the pure modules. Four packages and the original interface remain.
- **Limitation**: `rosdep check --from-paths src --ignore-src` could not run because
  this machine's rosdep database is uninitialized. No sudo/global installation was
  performed. All declared dependencies used here are already installed.



