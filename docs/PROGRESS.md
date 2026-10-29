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

## Milestone M5: Verified metrics and nine measured experiments

- **Status**: PASSED (2026-10-28).
- **Changes**: Added telemetry/path/final-snapshot tests and real SIGINT/SIGTERM
  process tests for the metrics logger. The logger records unknown remaining status
  as -1 until data arrives, appends a final CSV row, and closes idempotently. Existing
  `current` and `output_dir` parameters are exposed through typed launch arguments
  for the specified experiment matrix; defaults are unchanged (DECISION-005).
- **Commands run**:
  ```bash
  export PYTHONNOUSERSITE=1 ROS_LOG_DIR=/tmp/trash_boat_roslogs
  export ROS_DOMAIN_ID=74 ROS_AUTOMATIC_DISCOVERY_RANGE=LOCALHOST
  colcon build --symlink-install && colcon test && colcon test-result --verbose
  source install/setup.bash
  ROS_DOMAIN_ID=76 python3 docs/run_experiments.py --output-dir log/experiments_20261028
  ```
- **Real output excerpts** (complete experiment output: `docs/verification/M5.txt`):
  ```text
  Summary: 37 tests, 0 errors, 0 failures, 0 skipped
  Double value is: 0.0
  Integer value is: 3
  Completed 9 experiments: /home/abhi_pop/Desktop/ros-projects/ros-projects/log/experiments_20261028/experiments.json
  PASS: 9/9 results and all 34 recorded source hashes match the tested files
  ```
  The double/integer lines came from separate live `ros2 param get` checks confirming
  that the requested current and seed actually reached the simulator.
- **Results**: Every seed/current pair collected 12/12 with zero bank hits. Logged
  durations were 81.85–88.50 s, with all items first observed collected at 80.5–87.0 s.
  Each actual launch had four clean node exits and matching final CSV/summary counts
  and distance. Results, timing definitions, limitations, and plotted trajectories
  are in `docs/RESULTS.md`; numeric evidence is in `docs/results/experiments.json`.
  Raw CSVs and launch/probe logs are preserved under ignored `log/experiments_20261028/`.
- **Earlier checks**: The new experiment utility initially had one E501 (100-character
  line) and one D213 module-docstring formatting error in its separate style checks.
  Both were corrected; flake8 and pep257 now report `No problems found`. No mission
  or experiment failed its acceptance probe.
- **Self-review**: Charts were visually inspected. Source hashes, frozen defaults,
  interface count, pure-module separation, and protected files were checked. No
  ground-truth inputs were added to perception or controller decisions. Standard
  Python 3.12 fork warnings remain in ament_flake8 output after OpenCV is loaded;
  they do not cause test errors, failures, or skips.

## Milestone M6: Course documentation, clean-clone checks, and hosted CI

- **Status**: PASSED (2026-10-28), including clean Ubuntu 24.04/Jazzy hosted CI.
  The actual hosted output and run are recorded below.
- **Changes**: Rewrote the README with setup/run instructions, a Mermaid architecture,
  coordinate/state explanations, monitoring, verification, results, and limitations.
  Added `docs/EXPLAIN.md` with a presentation script and viva questions. CI now runs
  the unchanged complete verifier on Ubuntu 24.04/Jazzy and uploads evidence. Fixed
  explicit executor initialization and readiness ordering (DECISION-006).
- **Clean-clone procedure**: Made a local clone at `/tmp/trash_boat_clean_clone` with
  `git clone --no-hardlinks`; no build/install artifacts were copied. Applied the
  pending M6 patch, then checked that every Python source exactly matched the primary
  checkout. Executed the documented gate from a minimal environment:
  ```bash
  env -i PATH=/usr/bin:/bin LANG=C.UTF-8 PYTHONNOUSERSITE=1 \
    ROS_LOG_DIR=/tmp/trash_boat_clean_roslogs ROS_DOMAIN_ID=77 \
    ROS_AUTOMATIC_DISCOVERY_RANGE=LOCALHOST bash --noprofile --norc -c \
    'source /opt/ros/jazzy/setup.bash && ./tools/verify.sh'
  ```
- **Real final output excerpts** (complete output: `docs/verification/final_verify.txt`):
  ```text
  Summary: 37 tests, 0 errors, 0 failures, 0 skipped
  {"passed": true, "received_sim_data": true, "collected": 12, "total": 12, "ratio": 1.0, "bank_hits": 0, "wall_seconds": 84.9}
  PASSED: SEED=1 acceptance check passed
  {"passed": true, "received_sim_data": true, "collected": 12, "total": 12, "ratio": 1.0, "bank_hits": 0, "wall_seconds": 84.2}
  PASSED: SEED=2 acceptance check passed
  {"passed": true, "received_sim_data": true, "collected": 12, "total": 12, "ratio": 1.0, "bank_hits": 0, "wall_seconds": 84.4}
  PASSED: SEED=3 acceptance check passed
  All acceptance checks PASSED successfully!
  ```
  Exit code: 0. A separate fresh build/test in the primary checkout also passed all
  37 tests (`docs/verification/M6_unit.txt`).
- **Demo**: The same real mission/probe harness verified seed 42 in isolated domain
  78 with its own output directory: 12/12, zero bank hits, probe 81.6 s, first full
  collection at 83.0 s, logged duration 84.50 s. Evidence: `seed42.json` in the
  verification directory. `--show-args` confirmed defaults 42, 12, 0.05, and
  `~/trash_boat_metrics`.
- **Shutdown stress**: Ran the existing two real-process tests ten times in an
  explicit loop; inspected the actual XML after each iteration:
  ```text
  {"iteration": 10, "real_process_checks_passed": 20}
  PASS: 20/20 immediate-stop checks, zero errors/failures/skips
  ```
- **Earlier failures**: Initial clean-clone output was `37 tests, 0 errors, 2 failures`
  because SIGINT/SIGTERM could interrupt lazy executor initialization after readiness
  was announced. The tests and their traceback assertions were retained; explicit
  initialization fixed the race. Colcon's optional repeat flag was ignored because
  pytest-repeat is absent, so an explicit loop provided real repetitions without any
  installation. An initial patch-copy command ran in the wrong checkout and produced
  an empty patch; recreating it in the primary checkout corrected the transfer.
- **Self-review**: Documentation links resolve, workflow YAML parses, and the CI
  command invokes the full gate. AST comparisons confirm the simulator class and
  controller decision class are unchanged from M1/M3. Protected tools and SPEC are
  unchanged from the initial commit; no new decision inputs, topics, or frozen
  defaults were introduced. Plots were visually checked.
- **GitHub**: The user supplied `Abhinav-Siddharth/ROS-TRASH`, initially empty. The
  connected account has write access; Git push dry-run succeeded. The independent
  `gh auth status` reported an invalid CLI token, so Git transport and the connected
  GitHub tools are used without changing credentials. Original local milestone
  history will be preserved in the initial push.
- **Publication approval**: Automatic approval review rejected the combined
  commit/push request before execution: publishing all source and documentation to
  this public repository needs explicit approval of that public export; supplying
  the URL for CI was not considered sufficient. Local verification is complete.
  Local commits can proceed independently, but no push or alternate publication
  method will be attempted without the user's approval. Hosted CI remains unverified.

### M6 publication and CI follow-up

- The user explicitly approved public publication and CI after the review block.
  `git push -u origin main` succeeded, preserving the original milestone history at
  `https://github.com/Abhinav-Siddharth/ROS-TRASH` (initial head `b24a97a`).
- The first hosted workflow run failed before creating any jobs:
  `https://github.com/Abhinav-Siddharth/ROS-TRASH/actions/runs/40741499826`.
  The workflow's job-level environment used `runner.temp`, but `runner` is unavailable
  at that key according to GitHub's official context-availability table:
  `https://docs.github.com/en/actions/reference/workflows-and-actions/contexts#context-availability`.
  Replaced it with the same explicit writable `/tmp/trash_boat_roslogs` path used
  locally, including the matching artifact path. No verification step was removed.
- The connected fetch tool does not expose check-suite endpoints, and the public
  checks endpoint returned an empty list for the invalid workflow. No job logs were
  available for that initial validation failure. The corrected workflow is retried
  via a normal follow-up push, not by weakening tests or mission thresholds.
- Run `40741867555` accepted the corrected workflow and successfully installed ROS 2
  Jazzy, then failed in the separate dependency step. The actual job log reported:
  ```text
  WARNING: ROS_PYTHON_VERSION is unset. Defaulting to 3
  ERROR: the following packages/stacks could not have their rosdep keys resolved
  to system dependencies (ROS distro is not set.
  trash_boat_sim: Cannot locate rosdep definition for [ament_pep257]
  ```
  GitHub starts each step in a new shell; explicitly sourcing
  `/opt/ros/jazzy/setup.bash` in the dependency step supplies the required distro.
  The build/mission step was automatically not executed after the dependency failure;
  it remains present and unchanged for the retry.

### Final hosted gate: PASSED

- Run: `https://github.com/Abhinav-Siddharth/ROS-TRASH/actions/runs/40742785234`.
- Tested runtime commit: `7b1643f0d217d714388a27cb2668b7e5bb3d08ba`.
- GitHub returned `status=completed`, `conclusion=success`. Checkout, ROS setup,
  declared dependency installation, the complete verifier, and evidence upload all
  succeeded. This validates dependency resolution on a clean Ubuntu 24.04 runner,
  independently of the locally uninitialized rosdep database.
- Real hosted verifier output (full extracted output: `verification/hosted_verify.txt`):
  ```text
  Summary: 37 tests, 0 errors, 0 failures, 0 skipped
  {"passed": true, "received_sim_data": true, "collected": 12, "total": 12, "ratio": 1.0, "bank_hits": 0, "wall_seconds": 85.2}
  PASSED: SEED=1 acceptance check passed
  {"passed": true, "received_sim_data": true, "collected": 12, "total": 12, "ratio": 1.0, "bank_hits": 0, "wall_seconds": 84.6}
  PASSED: SEED=2 acceptance check passed
  {"passed": true, "received_sim_data": true, "collected": 12, "total": 12, "ratio": 1.0, "bank_hits": 0, "wall_seconds": 84.8}
  PASSED: SEED=3 acceptance check passed
  All acceptance checks PASSED successfully!
  ```
- All M0–M6 gates are now satisfied. All nine M5 experiments and the seed-42 demo
  passed, and the immediate-stop regression passed 20/20 real-process checks.
  Algorithms, protected tools, thresholds, and frozen simulator values remain intact.
- The final documentation commit records this already successful runtime gate;
  it does not change executable code. The live CI badge tracks subsequent runs.




### VRX M0: dependency and baseline gate PASSED (2026-10-29)

- Human approved the M0–M6 extension and pinned official VRX downloads. Contract:
  `docs/VRX_SPEC.md`; authorization and exceptions: DECISION-007.
- `git clone --depth 1 --branch v3.1.0 https://github.com/osrf/vrx.git external/vrx`.
  Annotated tag object `185fd8b...` resolves to source commit `03eae362...`; the
  manifest and bootstrap check pin the resolved source commit.
- `PYTHONNOUSERSITE=1 ROS_LOG_DIR=/tmp/trash_boat_roslogs bash scripts/bootstrap_vrx.sh`:
  `Pinned VRX source verified.` An initial `set -u` exposed an unset variable inside
  ROS setup; the script now disables nounset only while sourcing ROS, then restores it.
- `colcon build --symlink-install --parallel-workers 2 --cmake-args -DCMAKE_BUILD_TYPE=RelWithDebInfo`
  with system Python and `CMAKE_BUILD_PARALLEL_LEVEL=2`:
  `Summary: 9 packages finished [48.7s]`. Actual upstream Surface,
  SimpleHydrodynamics, Waves and other VRX shared libraries built successfully.
- Sourced `install/setup.bash`; `colcon test --event-handlers console_cohesion+ &&
  colcon test-result --verbose` in isolated domain 81 with approved local DDS:
  `Summary: 37 tests, 0 errors, 0 failures, 0 skipped`.
- Evidence: `docs/verification/vrx/M0_build.txt`, `M0_test.txt`. No system installs,
  no protected tool changes, no algorithm/default changes.

### VRX M1: world and physical scoring gate PASSED

- Added the approved integration package with a deterministic, offline SDF generator,
  upstream VRX Surface/SimpleHydrodynamics/PolyhedraBuoyancyDrag systems, a real RGB
  camera, hull contact sensor, and simulator-only C++ force/scoring system.
- `ros2 run trash_boat_vrx generate_world /tmp/trash_boat_canal.sdf &&
  gz sdf -k /tmp/trash_boat_canal.sdf`: `Valid.`
- Actual `world.launch.py headless:=true seed:=1`, isolated domains/partitions,
  system Python and approved graphics/DDS access; live ROS probe output:
  ```text
  {"collected": 0, "remaining": 12, "bank_hits": 0,
   "camera_fx": 240.00000953674316, "contact_sensor_topic": true,
   "images": 20, "poses": 100,
   "last_pose": [2.0, 0.0, 0.12543004729965884], "wall_seconds": 10.07}
  PASS: explicit scoop, outside item retained, no duplicate score, actual bank contacts
  {"collected": 1, "remaining": 11, "bank_hits": 1, ...}
  ```
  The scoring probe deliberately placed two objects with Gazebo's set_pose service
  (one inside, one outside), requested two scoops, then drove the boat into a bank
  with thruster forces. These are controlled scorer tests, NOT acceptance missions.
  Nominal trials retain the exact seeded spawn distribution. Screenshot:
  `docs/img/vrx_camera_M1.png`. Both Gazebo and bridge exited cleanly.
- Failures caught and fixed: missing plugin search path (added proper ament DSV and
  explicit launch path), camera calibration topic is `/vrx/camera_info`, and launch
  cleanup can receive repeated shutdown events. Local GZ_IP removes a long discovery
  delay. Early probes failed honestly on missing data; no assertion was removed.
- Corrected the new CMake package's lint tests to inspect the source directory, not
  its build directory. Actual source checks caught three indentation errors and
  unsupported SPDX-only C++ headers; fixed formatting and added full license headers.
- Final pre-commit `colcon build --symlink-install --parallel-workers 2 && colcon test
  --event-handlers console_cohesion+ && colcon test-result --verbose`:
  `Summary: 51 tests, 0 errors, 0 failures, 0 skipped`.
- Evidence: `docs/verification/vrx/M1_{build,test,probe,runtime}.txt`. Protected tools,
  original algorithms and frozen defaults untouched. The elevated renderer emits
  EGL probe warnings for the unused NVIDIA device, then successfully renders; no
  driver or global settings were changed.

### VRX M2: rendered perception gate PASSED

- Added pure pinhole/water-plane projection with boat quaternion, position and
  known camera mount. The thin detector subscribes ONLY to camera image/calibration
  and boat localization, uses the existing pure orange-blob detector, publishes
  nearest-first detections and a real annotated debug image for each frame.
- Unit checks cover reference pixel directions, combined roll/pitch/yaw, invalid
  calibration/quaternions, horizon and range rejection. Fixed the reported docstring
  and decorator formatting errors without changing any assertion or lint rule.
- Live world `headless:=true seed:=1 boat_x:=10` plus the actual `water_detector`
  node with simulation time. A controlled calibration placement (not mission input)
  gave expected body position [3,1] and image-derived [3.08397,1.03487] metres:
  ```text
  {"passed": true, "rendered_debug_frames": 12, "expected_body": [3, 1],
   "detected_body": [3.083971674557771, 1.0348742031273284],
   "wall_seconds": 3.99}
  ```
  `docs/img/vrx_detection_M2.png` was visually inspected; both orange objects are
  circled in the rendered canal. Small projection bias comes from projecting the
  visible top of a floating sphere onto the nominal water plane.
- Final `colcon build --symlink-install --parallel-workers 2 && colcon test
  --event-handlers console_cohesion+ && colcon test-result --verbose`:
  `Summary: 57 tests, 0 errors, 0 failures, 0 skipped`.
- Evidence: `docs/verification/vrx/M2_{build,test,probe}.txt`. Both real node processes
  stopped cleanly. The reference detector and controller modules remain unchanged.

### VRX M3: physical thruster control gate PASSED

- Added pure surge/yaw feedback, differential force mixing with ratio-preserving
  saturation, independent command/odometry freshness checks, and a thin ROS wrapper.
  SDF and YAML arm/force/watchdog values are cross-checked by a real test.
- Actual headless world + actual thruster_controller, commanded only through
  `/cmd_vel`; measured Gazebo odometry and force topics:
  ```text
  forward: v=0.79999998 m/s, x=6.51460405 m, left=right=8.00000086 N
  braking: v=0.00013035 m/s after 3 s of zero command
  turning: w=1.19999910 rad/s, left=-9.23080638 N, right=9.23082120 N
  turn stop: w=-0.00001937 rad/s after 3 s of zero command
  stale command: left=right=0.0 N
  ```
  Motion came from forces on a rigid body, not commanded poses/velocities. A stale
  command cuts thrust; the boat then coasts under physical drag, as expected.
- Initial probe aborted because its test Twist assigned integers to floating-point
  fields, triggering ROS serialization's type assertion. Stopped its two identified
  child process groups, corrected test message types, reran the full motion check.
  No production assertion, algorithm or test threshold was weakened.
- Final pre-commit build/test/result gate:
  `Summary: 66 tests, 0 errors, 0 failures, 0 skipped`.
- Evidence: `docs/verification/vrx/M3_{build,test,probe}.txt`. Reference decision logic
  and speed defaults unchanged. No trash status/positions enter thruster control.

### VRX M4: autonomous physical mission gate PASSED

- Added the full VRX mission launch (Gazebo, bridge, rendered perception, camera-only
  marine brain, force controller, real metrics logger) and independent acceptance
  monitor. The monitor requires real image/detection/command/pose traffic, exact
  12-item accounting, unchanged >=11/12 within 420 simulated seconds and <=3 actual
  contact transitions, CSV/summary agreement, and no runtime errors on shutdown.
- Real initial attempts exposed distinct failures, retained as evidence:
  - 12/12 at 90.8 s, one contact, but teardown tracebacks from double SIGINT: FAIL.
  - Clearance-margin-only fix: four real contact transitions at 39.615 s: FAIL.
  - Fixed safe waypoint: zero hits but stalled on an item displaced toward a bank;
    intentionally interrupted diagnostic run around 140 s: FAIL, never acceptance.
- Inspected state/pose/commands and camera-derived detections, recorded an eight-topic
  real rosbag (14.24 s, 1960 messages), decoded its images and visually inspected
  `docs/img/vrx_diagnostic_debug.png`. No bag is tracked. Decisions 008–010 explain
  the fixes: single-parent interrupt forwarding, cleanup immune to repeated signals,
  safe approach staging, controlled aligned docking, and reverse retreat before
  turning away. Search turns with large heading error happen in place.
- The reference decision class still decides collection from the REAL visual target.
  A waypoint cannot trigger collection. Original modules/defaults/physics are unchanged
  except orderly cleanup in node main functions. The new marine algorithm is pure,
  with declared parameters, and no trash ground truth enters decisions.
- Actual command (system Python, localhost transports, isolated domain 84):
  `ros2 run trash_boat_vrx verify_mission --seed 1 --output log/vrx_m4_seed1_docking`
  ```text
  collected=12, remaining=0, bank_hits=0, sim_seconds=154.61
  images=1546, detection_frames=1546, clean_shutdown=true
  metrics: duration_s=154.61, path_length_m=83.79, items_per_min=4.66
  runtime_errors=[], passed=true, error=null
  ```
  The complete measured JSON is authoritative if a rounded excerpt differs.
- Final pre-commit build/test/result gate: `Summary: 74 tests, 0 errors, 0 failures,
  0 skipped`. Includes a real-node repeated SIGINT/SIGTERM teardown regression,
  waypoint-versus-real-target distinction, docking/retreat, launch validity, no
  forbidden decision inputs, and metric mismatch rejection.
- Evidence: `docs/verification/vrx/M4_*`. Failed attempts remain explicitly marked.
  Protected tools and SPEC section 7 were not edited; no frozen environment settings
  or collection bounds were changed.

### VRX M5: seeded and disturbance evidence gate PASSED

- Seven real missions passed: nominal seeds 1/2/3 at current 0.05, plus seed-1
  zero/0.15 currents, 0.05 m waves, and seed-3 0.10 m waves. Every case collected
  12/12, stopped cleanly, had no runtime errors, and matched final CSV/summary counts,
  contacts and rounded path/duration. Nominal seed 2 had three actual end-bank contact
  transitions; all other runs had zero. This limitation is visible in RESULTS_VRX.md.
- Completion times (sim s): nominal 154.605 / 104.580 / 89.760; zero current 157.160;
  strong current 131.790; 0.05 m waves 154.760; 0.10 m waves 89.760. No deadlines,
  collision counter filtering, scoop bounds, frozen settings or assertions changed.
- Runtime commit bbbae5f, official VRX source 03eae362. Verified the exact source-tree
  hash stayed unchanged throughout all trials:
  `a42d31cbf6671a240f6a5f896ee7f8ab1f4bd6c9d1a40eb68d607a599cf95708`.
- Archived verbatim acceptance JSON, metrics.csv and summary.json for each case in
  `docs/results/vrx/`; combined report includes source provenance and exact commands.
  Reproducer: `docs/run_vrx_experiments.py`; graph script reads the actual measurements.
  `docs/img/vrx_results.png` was visually inspected. Full CSV paths and timestamps are
  measured data, not fabricated examples or hardcoded controller inputs.
- Independently ran a stationary physical boat with wave amplitude 0.10 for 12 sim s:
  188 samples after startup; z ranged 0.0274691–0.2248299 m, quaternion roll/pitch
  components varied. This proves waves affect physics, beyond merely setting SDF
  values. Water rendering remains a flat visual plane and is documented as such.
- Required pre-commit build/test/result gate:
  `Summary: 74 tests, 0 errors, 0 failures, 0 skipped`.
- No runtime source changed during M5. Original reference results remain separate.
