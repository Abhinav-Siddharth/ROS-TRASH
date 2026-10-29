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
