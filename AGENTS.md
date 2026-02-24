# AGENTS.md

## Purpose
This repository prioritizes maintainable, modular code over large generated blobs.
All agents should follow these guardrails by default.

## Core Standards
- Keep files readable and focused.
- Prefer small modules with one clear responsibility.
- Preserve behavior while refactoring.

## File Size Limits
- Target: `150-300` lines per file.
- Soft limit: `400` lines.
- If a file approaches `350+` lines, split it before adding more.
- Do not create new files above `400` lines.

## Modularity Rules
- Split by responsibility, not arbitrarily.
- Prefer extraction into focused modules:
  - UI composition
  - UI behavior/controllers
  - workers/background tasks
  - I/O readers/loaders
  - normalization/transform helpers
  - metadata/domain adapters
- Keep entry/orchestrator files thin.
- Keep public API/facade modules stable where reasonable.

## Refactor Expectations
- For large or messy files, do incremental extractions that keep behavior intact.
- Remove dead or duplicated code after extraction.
- Keep imports explicit and avoid circular dependencies.
- Keep naming consistent with existing package structure.

## Testing and Validation
- After substantial edits:
  - run available lint checks for touched files
  - run relevant tests for touched modules
  - do a quick line-count audit for changed Python files
- If a test tool is unavailable in the environment, report that clearly.

## Python Project Conventions
- Prefer pure functions for reusable logic.
- Keep Qt/UI classes as composition + orchestration layers.
- Move heavy logic out of large widget/window classes.
- Keep exception messages actionable and specific.

## Change Discipline
- Preserve unrelated existing code and functionality.
- Do not perform destructive git operations.
- Do not commit unless explicitly asked.
- Keep edits scoped to the requested task.
