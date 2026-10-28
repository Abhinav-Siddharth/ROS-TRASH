# trash_boat

Autonomous canal trash-collection boat in pure ROS 2 Jazzy simulation.

## Overview
A simulated boat patrols a 60m x 8m canal, detects floating trash blobs using an on-board top-down camera, and maneuvers to scoop them up while avoiding canal banks.

## Architecture
- `trash_boat_sim`: Canal simulator (`canal_sim`) simulating boat kinematics, trash drift, bank contacts, and camera feed.
- `trash_boat_perception`: Visual trash detector (`trash_detector` / `detector_core`) detecting orange blobs in HSV space.
- `trash_boat_control`: Control logic (`collector_brain` / `logic`) running a hierarchical finite state machine, and `metrics_logger`.
- `trash_boat_bringup`: Launch files (`sim.launch.py`, `mission.launch.py`) and parameters (`config/params.yaml`).

## Build & Test
```bash
colcon build --symlink-install
colcon test && colcon test-result --verbose
./tools/verify.sh
```
