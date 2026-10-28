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
