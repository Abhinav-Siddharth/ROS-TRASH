# trash_boat: Technical Specification (v1.0)

Source of truth for the project. Read `AGENTS.md` first (rules of engagement), then this file.
If something here is ambiguous, do NOT guess silently: record your assumption in
`docs/DECISIONS.md` and continue.

---

## 1. Goal

A **simulated** boat patrols a canal and, using **only its camera image**, finds floating
trash, approaches it, collects it, and avoids hitting the canal banks.

Scope: ROS 2 Jazzy, pure simulation (no Gazebo, no hardware), Python.

Non-goals (do NOT build these): Gazebo/VRX integration, YOLO/ML detection, Nav2, custom
message packages, multi-boat, real hardware drivers.

**Approved extension (2026-10-29):** The human requested a ready-to-run VRX simulation
and approved its M0–M6 plan and official pinned source/assets downloads. The additional
contract in `docs/VRX_SPEC.md` supersedes the Gazebo/VRX exclusion for that backend only.
The original backend, defaults, interfaces, section 7 thresholds, and protected tools
remain unchanged. See DECISION-007 for the explicit scope and dependency exceptions.

## 2. Environment and constraints

| Item | Value |
|---|---|
| OS | Ubuntu 24.04 |
| ROS | ROS 2 Jazzy (already installed at `/opt/ros/jazzy`) |
| Python | 3.12, system Python (no virtualenv, no `pip install`) |
| Build | `colcon build --symlink-install`, all packages `ament_python` |
| Libraries | `rclpy`, `cv_bridge`, `python3-opencv`, `python3-numpy` (apt/rosdep only) |
| Lint/tests | `ament_flake8`, `ament_pep257`, `ament_copyright`, `pytest` must all pass |
| Style | single quotes, max line length 99, type hints on all public functions |
| License | Apache-2.0 in every `package.xml` and file header where required |

Every dependency must be declared in the relevant `package.xml` so that
`rosdep install --from-paths src --ignore-src -y` fully prepares a clean machine.

## 3. Repository layout (final state)

```
trash_boat_ws/                      <- git repo root = colcon workspace
├── AGENTS.md  SPEC.md  README.md  LICENSE  .gitignore
├── .github/workflows/ci.yml
├── docs/  DECISIONS.md  PROGRESS.md  RESULTS.md
├── tools/ verify.sh  acceptance_check.py       <- PROVIDED, DO NOT EDIT
└── src/
    ├── trash_boat_sim/          canal_sim node (reference implementation provided)
    ├── trash_boat_perception/   trash_detector node
    ├── trash_boat_control/      collector_brain node + pure-logic module
    └── trash_boat_bringup/      launch files + config/params.yaml
```

The human may already have created empty package skeletons. Run `ls src` first. Reuse
what exists; create only what is missing (`ros2 pkg create --build-type ament_python ...`).
Optional extra node `metrics_logger` lives in `trash_boat_control`.

## 4. Conventions

- Frames: world frame `map` (x = downstream along the canal, y = left of canal axis,
  yaw CCW positive, units SI: metres, radians, seconds). Boat frame `boat`
  (x = forward, y = left).
- Canal geometry: x in `[0, canal_length]`, y in `[-half_width, +half_width]`.
- Camera: top-down, boat-centred, **image up = boat forward, image left = boat left**.
  Size `image_size` x `image_size` px, scale `pixels_per_meter`. Boat is at pixel
  `(size/2, size/2)`.
- Pixel (u = column, v = row) to boat frame:
  `fwd = (size/2 - v) / scale`, `left = (size/2 - u) / scale`.
- Time: always use the node clock (`self.get_clock().now()`), never `time.time()`, and
  never `sleep` inside callbacks.
- Logging: `self.get_logger()`; never `print`.
- No magic numbers: every tunable is a declared ROS parameter with a default equal to the
  value in this spec.

## 5. Interfaces

All topics use default QoS (reliable, volatile, depth 10) unless stated.

| Topic | Type | Publisher | Subscribers | Notes |
|---|---|---|---|---|
| `/cmd_vel` | `geometry_msgs/Twist` | collector_brain | canal_sim | `linear.x` m/s, `angular.z` rad/s |
| `/collect` | `std_msgs/Empty` | collector_brain | canal_sim | one message = one scoop attempt |
| `/camera/image_raw` | `sensor_msgs/Image` (`bgr8`) | canal_sim | trash_detector | 10 Hz, `frame_id='boat'` |
| `/boat_pose` | `geometry_msgs/PoseStamped` | canal_sim | collector_brain, metrics_logger | 20 Hz, `frame_id='map'` |
| `/trash_detections` | `geometry_msgs/PoseArray` | trash_detector | collector_brain | `frame_id='boat'`; published for EVERY image, empty array if none; `position.x=fwd`, `position.y=left`, `z=0`, orientation `w=1` |
| `/trash_detector/debug_image` | `sensor_msgs/Image` | trash_detector | (rqt) | image with detections circled |
| `/brain_state` | `std_msgs/String` | collector_brain | metrics_logger | one of `SEARCH`, `APPROACH`, `COLLECT`, `AVOID_BANK` |
| `/trash_collected` | `std_msgs/Int32` | canal_sim | acceptance, metrics_logger | cumulative count |
| `/trash_remaining` | `std_msgs/Int32` | canal_sim | acceptance, metrics_logger ONLY | **ground truth. perception and control MUST NOT use it** |
| `/bank_hits` | `std_msgs/Int32` | canal_sim | acceptance, metrics_logger | number of distinct bank-contact events |

No other topics, services, actions, or custom messages without a `docs/DECISIONS.md`
entry.

## 6. Package specifications

### 6.1 `trash_boat_sim`: `canal_sim`

**Reference implementation is provided** at
`src/trash_boat_sim/trash_boat_sim/canal_sim.py`. Copy it in as-is. You may make lint
fixes and bug fixes, but must not change behaviour, topics, or default parameters. Any
behaviour change needs a `DECISIONS.md` entry.

Parameters (defaults): `canal_length=60.0`, `half_width=4.0`, `n_trash=12`,
`current=0.05` (m/s downstream drift of trash), `seed=42`, `image_size=400`,
`pixels_per_meter=40.0`.

Behaviour summary: unicycle boat starting at (2, 0, yaw 0); trash spawned uniformly at
`x in [8, L-3]`, `|y| <= half_width - 0.8` using a seeded `random.Random`; trash drifts
downstream and piles at `x = L - 0.5`; a `/collect` message removes every trash item with
`0 <= fwd <= 1.5` and `|left| <= 1.0` and increments the counter; the boat is clamped to
`|y| <= half_width - 0.3` and each transition into that clamp counts as ONE bank hit;
status topics published at 2 Hz and on every collect.

Required tests (`test/test_canal_sim.py`, use `rclpy.init()` in a fixture):
1. Trash placed 1.0 m ahead is removed by `collect_cb`; trash 3 m ahead is not.
2. Trash drifts `+x` by about `current * t`.
3. Driving into the bank for many steps yields `bank_hits == 1`, not one per step.
4. Same `seed` gives identical initial trash positions; different seeds differ.

### 6.2 `trash_boat_perception`: `trash_detector`

Input `/camera/image_raw`; output `/trash_detections` and `/trash_detector/debug_image`.

Put the algorithm in **pure functions** in `trash_boat_perception/detector_core.py`
(no ROS imports) so they can be unit-tested:

```python
def detect_trash(bgr: np.ndarray, hsv_lower, hsv_upper,
                 min_area: float, max_area: float) -> list[tuple[float, float]]:
    """Return pixel centroids (u, v) of orange blobs."""

def pixel_to_body(u: float, v: float, image_size: int, pixels_per_meter: float
                  ) -> tuple[float, float]:
    """Return (fwd, left) in metres."""
```

Algorithm: BGR to HSV; `cv2.inRange` with `hsv_lower`/`hsv_upper`; morphological open
(3x3 kernel, 1 iteration); `cv2.findContours` (external); drop contours outside
`[min_area, max_area]`; centroid via image moments; convert to boat frame; sort ascending
by distance from the boat. The node publishes one `PoseArray` per image.

Parameters: `hsv_lower=[5,150,150]`, `hsv_upper=[25,255,255]` (OpenCV hue range 0-179;
the sim's trash is BGR (0,128,255), about hue 15), `min_area=20.0`, `max_area=800.0`,
`image_size=400`, `pixels_per_meter=40.0` (must equal the sim's values).

Detections must come only from the image. The detector never touches any sim internals.

Required tests (`test/test_detector_core.py`):
1. `pixel_to_body(200,200,400,40) == (0,0)`; `(200,160) -> (1.0, 0.0)`;
   `(160,200) -> (0.0, 1.0)` (left); `(200,240) -> (-1.0, 0.0)` (behind);
   `(240,200) -> (0.0, -1.0)` (right).
2. Synthetic image with one orange disc (radius 7) at a known pixel yields exactly one
   detection within 1 px.
3. Plain water colour (BGR 120,80,30), bank green (40,90,60), white boat triangle and
   white text yield zero detections.
4. Two discs yield two detections sorted nearest first.
5. A disc smaller than `min_area` (e.g. radius 2) is ignored.

### 6.3 `trash_boat_control`: `collector_brain`

Put the decision logic in a **pure class** `trash_boat_control/logic.py::CollectorLogic`
(no ROS imports) with:

```python
logic.step(now: float, pose: tuple[float, float, float] | None,
           detections: list[tuple[float, float]], det_stamp: float | None
           ) -> Command   # Command(v, w, collect: bool, state: str)
```

The ROS node only handles subscriptions, a `control_rate` timer, and publishing
`/cmd_vel`, `/collect`, `/brain_state`. If `pose is None` (nothing received yet), output
`v=w=0`.

Parameters (defaults): `control_rate=20.0`, `search_speed=0.8`, `approach_speed=0.8`,
`min_approach_speed=0.15`, `k_ang=1.5`, `k_lin=0.5`, `w_max=1.2`,
`detection_timeout=0.5`, `collect_fwd_min=0.2`, `collect_fwd_max=1.2`,
`collect_lateral_max=0.6`, `collect_cooldown=0.5`, `canal_length=60.0`,
`half_width=4.0`, `end_margin=2.0`, `patrol_aim_distance=3.0`, `bank_margin=0.8`,
`bank_hysteresis=0.3`, `bank_speed=0.3`.

Helpers: `wrap_angle(a)` maps to `(-pi, pi]`; `yaw_from_quaternion(q)` uses the general
formula `atan2(2(wz + xy), 1 - 2(y^2 + z^2))`.

State machine, evaluated each tick, **priority order top to bottom**:

1. **AVOID_BANK**: entered when `|y| > half_width - bank_margin`; left when
   `|y| < half_width - bank_margin - bank_hysteresis`. Behaviour:
   `target_yaw = atan2(-y, patrol_aim_distance * dir)`,
   `w = clamp(k_ang * wrap_angle(target_yaw - yaw), +-w_max)`, `v = bank_speed`.
2. **COLLECT**: after a collect trigger, hold `v=0, w=0` for `collect_cooldown` seconds
   (no new triggers during the hold), then return to SEARCH/APPROACH.
3. **APPROACH**: when at least one detection is fresh
   (`now - det_stamp <= detection_timeout`). Target is the nearest detection.
   `bearing = atan2(left, fwd)`, `dist = hypot(fwd, left)`,
   `w = clamp(k_ang * bearing, +-w_max)`,
   `v = max(min_approach_speed, min(approach_speed, k_lin * dist)) * max(0, cos(bearing))`.
   If `collect_fwd_min <= fwd <= collect_fwd_max` and `|left| <= collect_lateral_max`:
   emit `collect=True` exactly once and enter COLLECT.
4. **SEARCH** (default): patrol along the canal centreline.
   `dir` is `+1` (downstream) or `-1` (upstream), initially `+1`; flip to `-1` when
   `x >= canal_length - end_margin`, flip to `+1` when `x <= end_margin`.
   `target_yaw = atan2(-y, patrol_aim_distance * dir)`, `w` as in AVOID_BANK,
   `v = search_speed`.

(The camera sees 5 m to each side, wider than the 4 m half-width, so no zig-zag is
needed. A zig-zag search is an optional experiment for M5.)

Required tests (`test/test_logic.py`):
1. No detections, pose (10,0,0): state SEARCH, `v > 0`, `|w| < 0.05`.
2. Detection (3.0, 0.0): APPROACH, `v > 0`, `|w| < 0.05`, `collect False`.
3. Detection (3.0, 1.0): APPROACH and `w > 0` (turn left).
4. Detection (0.8, 0.1): `collect True` on the first tick, `False` on the next ticks
   during the cooldown, state COLLECT.
5. Detection behind (-2.0, 0.0): `v == 0`, `w != 0`.
6. Pose (20, 3.5, 0): state AVOID_BANK, `w < 0`, `v == bank_speed`.
7. Pose (59, 0, 0) with dir `+1`: after a step, patrol direction flips and the target
   yaw heads upstream (`w != 0`, yaw error near pi).
8. Detections older than `detection_timeout` are ignored (state SEARCH).
9. `wrap_angle` and `yaw_from_quaternion` basic cases.

The brain MUST NOT subscribe to `/trash_remaining`, `/trash_collected`, or `/bank_hits`.

### 6.4 `metrics_logger` (in `trash_boat_control`)

Subscribes to `/boat_pose`, `/trash_collected`, `/trash_remaining`, `/bank_hits`,
`/brain_state`. Writes a CSV at 2 Hz (`t,x,y,collected,remaining,bank_hits,state,
path_length`) to `output_dir` (default `~/trash_boat_metrics`), and on shutdown writes
`summary.json` with `items_collected, duration_s, items_per_min, path_length_m,
bank_hits`. Shutdown handling must work on Ctrl-C and on launch SIGINT.

### 6.5 `trash_boat_bringup`

- `config/params.yaml`: parameters for `canal_sim`, `trash_detector`, `collector_brain`,
  `metrics_logger`. `canal_length`, `half_width`, `image_size`, `pixels_per_meter` appear
  in more than one node and MUST be equal everywhere.
- `launch/sim.launch.py`: canal_sim only.
- `launch/mission.launch.py`: canal_sim + trash_detector + collector_brain +
  metrics_logger. Declares launch arguments `seed` (default 42) and `n_trash`
  (default 12) that override the YAML values.
  Gotcha: `LaunchConfiguration` yields a string, so wrap the override as
  `ParameterValue(LaunchConfiguration('seed'), value_type=int)`, otherwise the node
  receives a string and crashes.
- `setup.py` `data_files` must install `launch/*.launch.py` and `config/*.yaml`.

Required tests (`test/test_params_consistency.py`): parse `params.yaml` and assert shared
values are equal across nodes; assert both launch files' `generate_launch_description()`
return without error.

## 7. Acceptance criteria (the contract)

`tools/verify.sh` must exit 0. It runs, for seeds 1, 2 and 3 with the frozen settings
(`n_trash=12`, `current=0.05`, canal 60 x 8 m):

- all unit and lint tests pass (`colcon test-result` clean),
- the full mission (`mission.launch.py`) collects **at least 90% of the trash** (11 of
  12) within **420 s**, with **at most 3 bank hits**, measured from the sim's ground-truth
  topics by `tools/acceptance_check.py`.

Frozen values: do not change defaults of `n_trash`, `current`, canal dimensions,
speeds of the sim, `tools/*`, or the thresholds to make the mission pass.

## 8. Milestones and gates

Complete in order. Do not start the next until the gate passes. After each gate, commit
(one commit per milestone, conventional message) and append evidence to
`docs/PROGRESS.md` (command run, real output excerpt, pass/fail).

| # | Deliverable | Gate |
|---|---|---|
| M0 | Skeleton, `.gitignore`, LICENSE, CI file, copy `tools/` and the sim reference code | `colcon build` succeeds; `colcon test` passes (even if trivial) |
| M1 | `canal_sim` + tests + `sim.launch.py` | sim tests pass; `ros2 topic hz /camera/image_raw` is about 10 Hz; save one frame to `docs/img/sim_frame.png` |
| M2 | `detector_core.py`, `trash_detector` node + tests | detector tests pass; with the sim running, `/trash_detections` is non-empty when orange dots are in view |
| M3 | `logic.py`, `collector_brain` node + tests | logic tests pass |
| M4 | `mission.launch.py`, params, bringup tests | `tools/verify.sh` passes for seed 1 at least, then all seeds |
| M5 | `metrics_logger`, `docs/RESULTS.md` | summary.json produced; RESULTS.md table of seeds x `current in {0.0, 0.05, 0.15}` with time, items/min, path length, bank hits |
| M6 | README (build, run, architecture diagram in Mermaid, results), CI green | README commands work from a fresh clone; CI passes |

## 9. Known pitfalls (Jazzy / ament_python)

- OpenCV `fillPoly`/`polylines` need `np.int32` point arrays (int64 raises an error).
- Import order for `ament_flake8` follows Google style, alphabetical by module:
  `cv2`, `cv_bridge`, `geometry_msgs.msg`, `numpy`, `rclpy`, `sensor_msgs.msg`, ...
- Each package needs `test/` with the standard copyright/flake8/pep257 tests plus your own,
  and `<test_depend>` entries (`ament_copyright`, `ament_flake8`, `ament_pep257`,
  `python3-pytest`) in `package.xml`.
- New files in `data_files` require a rebuild even with `--symlink-install`.
- Run ROS-dependent tests under `colcon test`, not bare `pytest`, so the environment is
  sourced.
- Use `ParameterValue(..., value_type=...)` for typed launch overrides (see 6.5).
- `integer_array` parameters: default must be a list of Python ints.
- Shut down cleanly: nodes must exit on SIGINT without tracebacks.
