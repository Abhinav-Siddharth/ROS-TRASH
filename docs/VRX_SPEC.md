# VRX extension contract

Approved 2026-10-29. This extends SPEC.md; the original acceptance contract remains
frozen. All results must identify their backend. Never substitute the reference
camera or kinematic simulator for Gazebo in a VRX acceptance run.

## Environment and dependency policy

Ubuntu 24.04, ROS 2 Jazzy, Gazebo Harmonic. Official VRX v3.1.0 is pinned by SHA in
`dependencies.repos`; its ignored workspace checkout is reproducible. Downloading
that official source and required assets is explicitly approved. The original
no-pip/no-sudo rule remains, with rosdep for declared system dependencies.

## Backend and interfaces

- Keep `mission.launch.py` and `canal_sim` unchanged as the reference baseline.
- Add `trash_boat_vrx`, an ament CMake/Python package. Use upstream VRX Surface and
  SimpleHydrodynamics systems for buoyancy, waves and drag on a compact catamaran.
- Real rigid-body motion, physical bank collisions, rendered RGB camera and physical
  left/right thruster forces. Never teleport the boat to implement its controller.
- Seeded 12 trash items in the original 60 x 8 m canal; current defaults to 0.05 m/s.
  Preserve the original spawn distribution and nominal command speeds.
- Keep the public camera, pose, detections, cmd_vel, collect, state and metrics
  interfaces from SPEC.md. Add `/clock` (rosgraph_msgs/Clock), camera calibration
  (sensor_msgs/CameraInfo), odometry (nav_msgs/Odometry) and individual thruster
  commands (std_msgs/Float64). Gazebo transport carries simulator-only entity poses,
  collection requests, counter values and contact information as needed.
- Ground-truth boat localization is an ideal sensor, as in the reference backend;
  trash locations and scorer counters never feed perception or decision logic.
- Camera projection uses its intrinsics and known mounting geometry onto the water
  plane. Start with a downward camera, with image-up forward and image-left port.
  Use a real perspective rendering, not synthetic dots drawn from positions.
- Visible scoop retains the original collection bounds: forward [0, 1.5] m,
  lateral +/-1.0 m. Collection requires an explicit `/collect` request and trash
  in this intake region. Score each item once and remove it physically from the world.
- Count transitions into actual bank contact. A failed contact sensor is an error,
  not evidence of zero hits. Drift/current forces act on trash; no seeded steering.
- Declare ROS tunables, validate configuration, stop thrusters on stale commands
  or localization, use simulation time throughout, and shut down without tracebacks.

## Milestones and gates

| Gate | Deliverable and required real evidence |
|---|---|
| M0 | Pinned dependencies, contract and bootstrap; existing build/tests pass and VRX plugins build |
| M1 | Generated SDF world, craft, trash, water and scorer; SDF validates; Gazebo runs with VRX plugins, buoyancy, contact sensors and counters |
| M2 | Rendered camera and calibrated detector; live image/detection checks and projection tests pass |
| M3 | Thruster adapter and feedback; pure controller tests plus actual forward/turn/stop physics checks |
| M4 | Integrated autonomous launch; seeded calm-water mission passes the unchanged 90%/420 sim seconds/3 hits criterion and shuts down cleanly |
| M5 | Seeds 1, 2, 3 and current/wave robustness trials; CSV/summary and provenance agree; report successes and failures |
| M6 | One-command GUI/headless launch, course explanation, independent verification runner and reproducible setup; original full verify still passes |

Wave/current robustness runs are additional experiments, not replacements for the
calm-water gate. Changing wave amplitude does not alter the original backend. A
passing calm-water mission does not justify claims of performance on real water.

## Verification and delivery

Add meaningful tests for world geometry, deterministic spawning, scoop boundaries,
camera projection and thruster mixing, command timeouts and simulator integration.
Preserve every existing test and protected tool. New acceptance runs must require
rendered camera data and real node processes, collect measured results, stop the
whole process group reliably, and report both simulation and wall-clock durations.
Document graphics requirements and provide explicit failure diagnostics rather than
silently falling back to the reference simulator or ignoring runtime errors.
