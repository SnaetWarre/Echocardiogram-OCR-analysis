from __future__ import annotations

import argparse
import time
from collections.abc import Iterable
from dataclasses import dataclass
from pathlib import Path

from app.io.dicom_loader import load_dicom_series  # noqa: E402
from app.io.errors import DicomLoadError  # noqa: E402


@dataclass
class LoadResult:
    path: Path
    ok: bool
    duration_s: float
    error: str | None = None
    frame_count: int | None = None
    shape: tuple[int, ...] | None = None


def iter_dicom_files(root: Path, pattern: str) -> Iterable[Path]:
    if root.is_file():
        if root.match(pattern):
            yield root
        return
    for path in root.rglob(pattern):
        if path.is_file():
            yield path


def load_single(
    path: Path,
    load_pixels: bool,
    force: bool,
    decode_first_frame: bool,
) -> LoadResult:
    start = time.perf_counter()
    try:
        series = load_dicom_series(path, load_pixels=load_pixels, force=force)
        first_frame_shape: tuple[int, ...] | None = None
        if decode_first_frame:
            frame = series.get_frame(0)
            first_frame_shape = tuple(frame.shape)
        duration = time.perf_counter() - start
        shape: tuple[int, ...] | None = None
        if series.raw_frames is not None:
            shape = tuple(series.raw_frames.shape)
        elif first_frame_shape is not None:
            shape = first_frame_shape
        return LoadResult(
            path=path,
            ok=True,
            duration_s=duration,
            frame_count=series.frame_count,
            shape=shape,
        )
    except DicomLoadError as exc:
        duration = time.perf_counter() - start
        return LoadResult(path=path, ok=False, duration_s=duration, error=str(exc))
    except Exception as exc:
        duration = time.perf_counter() - start
        return LoadResult(path=path, ok=False, duration_s=duration, error=f"Unhandled error: {exc}")


def summarize(results: list[LoadResult]) -> None:
    total = len(results)
    failures = [r for r in results if not r.ok]
    successes = [r for r in results if r.ok]
    total_time = sum(r.duration_s for r in results)
    slowest = sorted(results, key=lambda r: r.duration_s, reverse=True)[:5]

    print("\nSummary")
    print("-------")
    print(f"Total files:     {total}")
    print(f"Successes:       {len(successes)}")
    print(f"Failures:        {len(failures)}")
    print(f"Total time:      {total_time:.2f}s")
    if results:
        print(f"Avg time/file:   {total_time / total:.3f}s")
    if slowest:
        print("Slowest files:")
        for r in slowest:
            status = "OK" if r.ok else "FAIL"
            print(f"  {status:<4} {r.duration_s:.3f}s  {r.path}")

    if failures:
        print("\nFailures")
        print("--------")
        for r in failures:
            print(f"{r.path}: {r.error}")


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Bulk DICOM loader test. Loads many .dcm files and reports failures/slow loads."
    )
    parser.add_argument(
        "root",
        type=Path,
        help="Root directory or file to load. Directories are scanned recursively.",
    )
    parser.add_argument(
        "--pattern",
        default="*.dcm",
        help="Glob pattern to match files (default: *.dcm).",
    )
    parser.add_argument(
        "--max-files",
        type=int,
        default=0,
        help="Stop after loading this many files (0 means no limit).",
    )
    parser.add_argument(
        "--no-pixels",
        action="store_true",
        help="Only load metadata (lazy frame loading).",
    )
    parser.add_argument(
        "--decode-first-frame",
        action="store_true",
        help="Decode the first frame after loading metadata.",
    )
    parser.add_argument(
        "--force",
        action="store_true",
        help="Pass force=True to pydicom.dcmread.",
    )
    parser.add_argument(
        "--print-each",
        action="store_true",
        help="Print a line per file as it loads.",
    )

    args = parser.parse_args()
    root: Path = args.root

    if not root.exists():
        print(f"Path not found: {root}")
        return 2

    load_pixels = not args.no_pixels

    files = list(iter_dicom_files(root, args.pattern))
    if not files:
        print("No matching DICOM files found.")
        return 1

    if args.max_files > 0:
        files = files[: args.max_files]

    results: list[LoadResult] = []
    for idx, path in enumerate(files, start=1):
        result = load_single(
            path,
            load_pixels=load_pixels,
            force=args.force,
            decode_first_frame=args.decode_first_frame,
        )
        results.append(result)
        if args.print_each:
            status = "OK" if result.ok else "FAIL"
            extra = ""
            if result.ok and result.shape is not None:
                extra = f" shape={result.shape}"
            print(f"[{idx}/{len(files)}] {status:<4} {result.duration_s:.3f}s {path}{extra}")

    summarize(results)
    return 0 if all(r.ok for r in results) else 1


if __name__ == "__main__":
    raise SystemExit(main())
