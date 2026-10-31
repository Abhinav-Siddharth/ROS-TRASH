# VRX extension evidence

The original M0–M6 evidence remains in PROGRESS.md. This file holds longer extension
notes; each milestone also receives an entry in PROGRESS.md. No original results
are represented as VRX results.

## Initial environment, 2026-10-29

- Read AGENTS.md and all of SPEC.md before editing.
- Explicit plan/download exception approved by the human.
- `ros2`: `/opt/ros/jazzy/bin/ros2`; `gz sim --versions`: `8.15.0`.
- `pkg-config --modversion gz-sim8 gz-transport13 sdformat14`: 8.15.0,
  13.6.0, 14.9.0. ROS/Gazebo bridge and xacro are already installed.
- VRX/WAM-V not installed. Official remote returned v3.1.0 SHA
  `185fd8b427f6ffab625b422ae0be268fb43e1ca8`.
- Sandboxed graphics probe cannot access display :1. With approved desktop access,
  `glxinfo -B` reports accelerated Mesa Intel Graphics (RPL-S), OpenGL 4.6.
  Gazebo graphics and local transports therefore require the same approved local
  execution access as ROS missions; no driver changes are needed.
