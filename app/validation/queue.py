from __future__ import annotations

from collections.abc import Iterable
from pathlib import Path


def collect_dicom_files(root: Path) -> list[Path]:
    if root.is_file():
        return [root] if root.suffix.lower() == ".dcm" else []
    if not root.is_dir():
        return []
    return sorted(
        path for path in root.rglob("*") if path.is_file() and path.suffix.lower() == ".dcm"
    )


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
