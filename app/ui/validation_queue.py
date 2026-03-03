from __future__ import annotations

from collections.abc import Iterable
from pathlib import Path


def build_validation_queue(candidates: Iterable[Path], current_path: Path | None) -> list[Path]:
    unique: list[Path] = []
    seen: set[Path] = set()
    for path in candidates:
        resolved = path.resolve()
        if resolved in seen:
            continue
        seen.add(resolved)
        unique.append(path)

    if current_path is None:
        return unique
    if not unique:
        return [current_path]

    for index, candidate in enumerate(unique):
        if candidate == current_path:
            return unique[index:]
    return [current_path, *unique]
