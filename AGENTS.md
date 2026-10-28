# AGENTS.md: Rules for all coding agents on this repo

You are implementing `trash_boat`, a ROS 2 Jazzy simulation. **`SPEC.md` is the source of
truth.** Read it completely before writing any code. These rules are mandatory.

## 1. Workflow

1. **Plan first.** Before touching files, produce a short implementation plan mapped to
   milestones M0-M6 in `SPEC.md` and wait for human approval.
2. **One milestone at a time**, in order. A milestone is done only when its gate in
   `SPEC.md` passes with real command output.
3. After each milestone: commit (`feat(sim): ...`, `test(control): ...`), then append to
   `docs/PROGRESS.md`: milestone, commands run, a short real output excerpt, result.
4. If a requirement is ambiguous, pick the most conservative reading, log it in
   `docs/DECISIONS.md` (what, why, alternatives), and continue. If a requirement seems
   impossible or contradictory, STOP and ask the human instead of working around it.
5. Work in the Ubuntu 24.04 + ROS 2 Jazzy environment. If `ros2` is not available in your
   terminal, stop and tell the human. Do not pretend, and do not write code you cannot
   build.

## 2. Hard prohibitions (violations invalidate the work)

- **No ground-truth leakage.** `trash_detector` and `collector_brain` must never subscribe
  to `/trash_remaining`, `/trash_collected`, or `/bank_hits`, import from
  `trash_boat_sim`, or read trash positions from anywhere except the camera image.
- **Do not edit** `tools/verify.sh`, `tools/acceptance_check.py`, or the thresholds in
  `SPEC.md` section 7.
- **Do not make the task easier.** No changes to the frozen values (`n_trash`, `current`,
  canal size, seeds, sim speeds), no auto-collect in the sim, no hardcoded trash
  positions, no seed-specific logic, no inflating the scoop region.
- **Do not weaken verification.** No deleted, skipped, `xfail`ed, or loosened tests;
  no blanket `# noqa` or lint-config exclusions; no `|| true` to hide failures; no mocking
  that replaces the real node in the acceptance run.
- **No fabricated results.** Never write output you did not actually see. If a command
  fails or you cannot run it, say so plainly in `docs/PROGRESS.md` and in your report.
- **No `sudo`, `pip install`, or global system changes** beyond `rosdep install` for
  declared dependencies. No network downloads of code or models.
- **No scope creep.** No new topics, message types, packages, or features beyond
  `SPEC.md` without a `docs/DECISIONS.md` entry and human approval.
- Never commit `build/`, `install/`, `log/`, bags, or `log_mission_*.txt`.

## 3. Code standards

- Python 3.12, single quotes, max 99 columns, type hints on public functions,
  Google-style import order (see `SPEC.md` section 9).
- Decision logic and image processing live in **pure modules** (`logic.py`,
  `detector_core.py`) with no ROS imports; ROS nodes are thin wrappers.
- Every tunable is a declared ROS parameter whose default matches `SPEC.md`. No magic
  numbers in logic.
- Use `self.get_logger()` and the node clock. No `print`, no `time.sleep` in callbacks.
- Nodes shut down cleanly on SIGINT (no tracebacks).
- Each `package.xml` has accurate description, maintainer, license, and all
  `<depend>`/`<exec_depend>`/`<test_depend>` entries.

## 4. Testing and verification

- Write the tests listed in `SPEC.md` section 6 alongside the code, not afterwards.
- Run before every commit: `colcon build --symlink-install && colcon test &&
  colcon test-result --verbose`.
- Final gate: `./tools/verify.sh` must exit 0 (it runs three seeded end-to-end missions).
  Quick unit-only pass: `./tools/verify.sh --no-integration`.
- If the mission fails the acceptance check, **fix the algorithm** (controller logic,
  detector thresholds, parameters in the control/perception packages). Diagnose with
  `/brain_state`, `/trash_detector/debug_image`, and `ros2 bag` before changing anything.

## 5. Self-review checklist (run before declaring any milestone done)

- [ ] Gate commands for this milestone were actually run, and output is in `PROGRESS.md`
- [ ] `colcon test-result` shows 0 errors, 0 failures, 0 skipped that you introduced
- [ ] `git diff` touches nothing under `tools/` and no frozen values
- [ ] `grep -R "trash_remaining\|trash_collected\|bank_hits" src/trash_boat_perception
      src/trash_boat_control/trash_boat_control/logic.py` finds nothing in those
      packages' decision code (only `metrics_logger` may use them)
- [ ] No new topics beyond the interface table
- [ ] Parameters and YAML defaults match `SPEC.md`
- [ ] `git status` is clean of build artefacts

## 6. Final report format (when M6 is done)

Reply with: (1) milestone checklist with pass/fail, (2) the real final output of
`./tools/verify.sh`, (3) list of assumptions from `DECISIONS.md`, (4) known limitations,
(5) anything you could not verify. Be candid; a truthful "not verified" is better than an
unsupported "done".
