from __future__ import annotations

import argparse
import json
import os
import sys
from pathlib import Path
from typing import Any

import numpy as np

from app.io.dicom_loader import load_dicom_series


def _write_json(payload: dict[str, Any]) -> None:
    sys.stdout.write(json.dumps(payload, ensure_ascii=False) + "\n")
    sys.stdout.flush()


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Decode a single DICOM frame in a subprocess and write it to disk."
    )
    parser.add_argument("path", type=str, help="Path to a .dcm file")
    parser.add_argument("--frame", type=int, default=0, help="Frame index to decode")
    parser.add_argument(
        "--out",
        type=str,
        required=True,
        help="Output .npy path for the decoded frame",
    )
    parser.add_argument(
        "--force",
        action="store_true",
        help="Force reading invalid DICOM files",
    )
    parser.add_argument(
        "--read-frame-only",
        action="store_true",
        help="Use pydicom get_frame for lazy frame decoding when possible",
    )
    parser.add_argument(
        "--read-all",
        action="store_true",
        help="Decode full pixel array instead of a single frame",
    )
    parser.add_argument(
        "--cache-frames",
        action="store_true",
        help="Cache decoded frames in memory (lazy path)",
    )
    parser.add_argument(
        "--no-cache",
        action="store_true",
        help="Disable frame cache in lazy path",
    )
    parser.add_argument(
        "--debug",
        action="store_true",
        help="Include exception details in stdout JSON on failure",
    )
    return parser.parse_args()


def configure_env(args: argparse.Namespace) -> None:
    os.environ["DICOM_SUBPROCESS_DECODE"] = "0"

    if args.read_all:
        os.environ["DICOM_LAZY_FRAME_ONLY"] = "0"
    elif args.read_frame_only:
        os.environ["DICOM_LAZY_FRAME_ONLY"] = "1"

    if args.no_cache:
        os.environ["DICOM_LAZY_CACHE_FRAMES"] = "0"
    elif args.cache_frames:
        os.environ["DICOM_LAZY_CACHE_FRAMES"] = "1"


def main() -> int:
    args = parse_args()
    configure_env(args)

    path = Path(args.path)
    out_path = Path(args.out)

    if not path.exists():
        _write_json({"status": "error", "error": f"File not found: {path}"})
        return 1

    try:
        series = load_dicom_series(
            path,
            load_pixels=False,
            force=args.force,
        )
        frame = series.get_frame(args.frame)
        out_path.parent.mkdir(parents=True, exist_ok=True)
        np.save(out_path, frame)
        _write_json(
            {
                "status": "ok",
                "path": str(path),
                "frame_index": args.frame,
                "frame_count": series.frame_count,
                "shape": list(frame.shape),
                "dtype": str(frame.dtype),
                "out": str(out_path),
                "transfer_syntax": series.metadata.transfer_syntax,
            }
        )
        return 0
    except Exception as exc:
        payload = {"status": "error", "error": str(exc)}
        if args.debug:
            payload["type"] = type(exc).__name__
        _write_json(payload)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
