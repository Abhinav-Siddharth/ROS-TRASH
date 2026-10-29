# Architectural and Design Decisions

This document records key design decisions, rationale, and alternatives considered during the development of `trash_boat`.

### DECISION-007: Approved VRX simulation extension

- **Date**: 2026-10-29
- **Authorization**: The human requested "Implement everything you think is required.
  I should receive the simulation ready" after the VRX recommendation, then explicitly
  answered "Approve plan and VRX downloads" to the M0–M6 plan and dependency exception.
- **What**: Add a separate Gazebo Harmonic / ROS 2 Jazzy backend using official VRX
  v3.1.0, pinned to commit `03eae362bb544f630595acd53b931e4a7060dffd`.
  Permit its official source and bundled asset download inside ignored `external/`.
  Add one integration package, including a C++ Gazebo scoring plugin, Python world
  generator, sensor projection, thruster controller, launch/configuration and tests.
  C++ is necessary for direct Gazebo entity/physics access; existing packages remain
  Python. New simulator transport and ROS interfaces are listed in `VRX_SPEC.md`.
- **Why**: The new user instruction expands the original pure-Python scope. A compact
  custom catamaran fits the frozen 8 m canal better than the larger stock WAM-V.
  Use upstream VRX buoyancy/hydrodynamics rather than describing a kinematic model
  as a physics simulation. Use locally generated primitive geometry, with no Fuel
  model fetches or downloaded perception models.
- **Preserved**: Original verification tools, acceptance thresholds, simulator class,
  controller state machine, default speeds, seeds, trash count, and canal size.
  No trash ground truth enters perception or control. Existing results apply only
  to the original backend until separate VRX trials establish measured results.
- **Alternatives**: Stonefish was considered but VRX directly targets surface craft
  and explicitly supports this installed ROS/Gazebo combination. Replacing the
  original simulator would lose the fast verified regression baseline.
- **Gates**: Follow `docs/VRX_SPEC.md` M0–M6 in order; record actual commands and
  failures in `PROGRESS.md`. System dependencies remain limited to declared rosdep
  dependencies; no pip, sudo, or other global changes are authorized.

---

### DECISION-001: Creation of `tools/verify.sh` and implementation of `canal_sim.py`

- **Date**: 2026-10-28
- **Context**: `SPEC.md` states that `acceptance_check.py` and `tools/verify.sh` are provided, and that a reference implementation for `canal_sim.py` is provided. However, only `acceptance_check.py`, `AGENTS.md`, and `SPEC.md` were present in the workspace.
- **Decision**:
  1. Move `acceptance_check.py` to `tools/acceptance_check.py` without modifying its threshold logic.
  2. Implement `tools/verify.sh` adhering strictly to Section 4 and Section 7 of `SPEC.md` (supporting `--no-integration` for unit tests and the 3-seeded integration verification for acceptance).
  3. Implement `canal_sim.py` strictly according to the physics, topics, and parameters specified in Section 6.1.
- **Alternatives Considered**:
  - Halting and waiting indefinitely: The human user explicitly instructed to proceed and make files as per requirements.
- **Consequences**: Implementation remains fully compliant with the frozen constants and interfaces in `SPEC.md`.

### DECISION-002: Use system Python packages and isolate verification runs

- **Date**: 2026-10-28
- **What**: Run build, tests, and missions with `PYTHONNOUSERSITE=1`. Use a dedicated
  `ROS_DOMAIN_ID` for verification and a writable `ROS_LOG_DIR` when necessary.
- **Why**: The current user's NumPy 2.5.0 overrides the distribution NumPy 1.26.4 and
  crashes Jazzy's `cv_bridge`. The system OpenCV/NumPy pair passes an actual image
  round trip. Disabling user site packages avoids global changes. A separate domain
  prevents unrelated ROS workspaces from contributing messages to acceptance runs.
- **Alternatives**: Uninstalling or changing global/user Python packages was rejected;
  changing dependencies with pip is prohibited. All simulation settings remain fixed.
- **Verification note**: The execution sandbox blocks ROS log writes in the default
  home directory and blocks DDS sockets. Real mission checks therefore run with
  approved local execution permissions; unit checks use a writable temporary log path.

### DECISION-003: Treat supplied metrics as separate historical evidence

- **Date**: 2026-10-28
- **What**: Do not merge the supplied Downloads `metrics.csv` and `summary.json` into
  acceptance or experiment results without matching run provenance.
- **Why**: The CSV reaches 12 items at 86.0 s, continues until 8975.5 s and 7173.397 m,
  while the summary reports 410.89 s and 321.45 m. Neither identifies a seed/current.
- **Alternatives**: Inferring the seed or claiming the files prove all three acceptance
  missions would be unsupported. Fresh runs provide attributable results instead.

### DECISION-004: Preserve SIGINT delivery and orderly node shutdown

- **Date**: 2026-10-28
- **What**: Restore the normal Python SIGINT handler in mission launch when Bash
  has inherited it as ignored. Nodes handle SIGINT/SIGTERM as Python interrupts,
  finish spinning, and destroy their ROS context in `finally`. A bounded 0.1 s
  executor wait lets an idle subscriber process pending Python signals even after
  the simulator stops publishing.
- **Why**: The unchanged verifier's background launch collected 12/12 for seed 1
  but ignored its cleanup SIGINT. A separate stop exposed a detector publishing
  against a context that rclpy's asynchronous signal handler had already shut down.
- **Alternatives**: Editing the protected verification script, changing global ROS
  libraries, or ignoring errors during normal operation were rejected. These changes
  affect process lifecycle only, not simulator physics, collection, or acceptance.

### DECISION-005: Reproducible current experiments using existing node parameters

- **Date**: 2026-10-28
- **What**: Expose `current` and `output_dir` as typed mission launch arguments for
  the required M5 experiment matrix. Their defaults remain `0.05` and
  `~/trash_boat_metrics`, matching the specification and YAML. Each experiment uses
  a separate output directory and the unchanged acceptance probe.
- **Why**: The specification requires three current values and attributable metrics.
  Explicit overrides avoid editing the frozen default configuration between runs.
  No topics, message types, packages, or ROS parameters are added.
- **Alternatives**: Mutating the installed YAML for every experiment was rejected as
  error-prone. The official acceptance run continues to use its frozen defaults.
- **Metrics interpretation**: CSV `remaining=-1` means simulator status has not arrived;
  it must not be interpreted as successful completion. Shutdown appends a final row
  before summary generation. Duration includes startup and the probe's settling time;
  collection times derived from the 2 Hz CSV have 0.5 s sampling resolution.

### DECISION-006: Initialize explicit executors before announcing readiness

- **Date**: 2026-10-28
- **What**: Each node owns an explicit `SingleThreadedExecutor`, adds its node before
  spinning, and shuts down that executor before destroying the node/context. The
  metrics logger announces its output path only after executor setup is complete.
- **Why**: Clean-clone verification exposed a race: immediate SIGINT/SIGTERM after
  the logger's readiness message could interrupt lazy global-executor construction,
  producing an `AttributeError` in `SingleThreadedExecutor.__del__`. Both real-process
  tests correctly failed on the traceback even though the process returned zero.
- **Alternatives**: Delaying the tests, ignoring stderr, or weakening their assertions
  was rejected. Explicit lifecycle ownership fixes the underlying initialization order.
  Algorithms, topics, frozen simulator values, and acceptance tools remain unchanged.

### DECISION-008: Physical footprint clearance and repeated shutdown signals

- **Date**: 2026-10-29
- **Evidence**: The first autonomous VRX seed-1 run collected 12/12 at 90.8 simulated
  seconds with one bank contact. CSV first records that contact at y=-2.789 m while
  APPROACH turns the finite-size catamaran; its rotated hull/deck can extend about
  1.21 m laterally, unlike the reference simulator's point/unicycle footprint.
  Recorded and inspected brain states, rendered debug images and an eight-topic
  14.24 s rosbag (1960 messages); the bag stays in ignored log storage.
- **Decision**: Override only the VRX brain's existing `bank_margin` parameter to
  1.4 m (enter avoidance at |y|>2.6), keeping speeds, geometry, scoop and all reference
  defaults unchanged. This changes the algorithm's clearance, not the environment
  or collision scorer. Verify all seeds again; no contact counter filtering.
- **Shutdown evidence**: The mission monitor's process-group SIGINT reached children
  directly and launch forwarded another SIGINT during node destruction, yielding
  real KeyboardInterrupt tracebacks. The monitor now signals launch once, leaving
  forwarding to launch, with process-group termination only as failure fallback.
  All node main functions ignore further SIGINT/SIGTERM only after entering their
  `finally` cleanup, allowing orderly teardown and metrics flush to finish. No
  simulator class or decision class is altered. Add repeated-signal regression.
- **Metrics precision**: Existing logger CSV path is rounded to 1 mm, summary path
  to 1 cm. The new provenance checker permits the combined 0.006 m rounding bound;
  this is not a mission/path performance threshold. Counts and bank hits stay exact.

### DECISION-009: Camera-derived safe approach waypoints for the physical hull

- **Evidence**: VRX-only margin 1.4 still failed: seed 1 reached four contact
  transitions at 39.615 s, collected 4/12. Shutdown was now clean, with no runtime
  errors. CSV shows AVOID_BANK entered, but momentum and rotation carried the
  centre to |y|=2.838 m; the finite hull then contacted the bank while turning.
  Increasing a trigger margin alone does not solve the approach geometry.
- **Decision**: Add a pure marine approach adapter around the unchanged reference
  decision class. From camera detections and boat pose, compute a waypoint alongside
  shoreline trash, clamped to a safe boat-centre corridor. Approach that waypoint,
  brake, then turn in place toward the actual detected trash. Collection eligibility
  is still checked against the actual image-derived detection by the reference
  logic; the waypoint can never trigger collection. Preserve all state names,
  original cooldown, speed limits, scoop bounds and priorities. No ground-truth
  trash input and no seed-specific tuning.
- **Defaults**: shore clearance 1.8 m (safe centre |y|<=2.2), end clearance 1.4 m,
  waypoint arrival 0.25 m, in-place alignment within 1.1 m of actual trash. These
  are declared ROS parameters in the separate marine wrapper. Original backend
  keeps its original node, class and parameters.

### DECISION-010: Controlled final docking and retreat

- The first waypoint implementation prevented collisions but stalled on a physical
  item pushed toward the bank: live image-derived target [-0.180,-1.323] m while
  the boat stayed near y=-2.37. A fixed stand-off waypoint cannot put all shoreline
  objects within the unchanged collection trigger. Stopped this diagnostic trial
  after about 140 s rather than claiming success or waiting to exhaust its deadline.
- Keep safe staging, then latch a docking phase: align in place at safe clearance,
  creep forward at 0.3 m/s only while the real target bearing is within 0.15 rad,
  collect using the unchanged reference trigger, hold its cooldown, and reverse at
  0.3 m/s into the safe corridor before turning again. Hard docking clearance is
  1.1 m from banks/end walls. This accounts for physical displacement of floating
  objects rather than artificially clamping them or enlarging the scoop.
- Restore the reference 0.8 bank margin in the VRX fallback; the staged docking
  corridor handles normal collision avoidance. The old 1.4 override conflicted
  with the controlled close approach. All changes are to camera-derived planning;
  scorer, physics, distribution, currents, speeds' upper bounds and tests remain.
