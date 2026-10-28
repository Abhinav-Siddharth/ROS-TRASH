# Architectural and Design Decisions

This document records key design decisions, rationale, and alternatives considered during the development of `trash_boat`.

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
