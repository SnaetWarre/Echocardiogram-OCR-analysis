from __future__ import annotations

import json
import os
import subprocess
import sys
import tempfile
from pathlib import Path
from threading import RLock
from typing import Callable, Dict, Optional

import numpy as np
import pydicom
from pydicom.errors import InvalidDicomError

from app.io.dicom_reader import extract_pixel_array, get_frame_count
from app.io.errors import DicomLoadError
from app.io.normalization import normalize_frames

try:
    from pydicom.pixel_data_handlers.util import get_frame as default_dicom_get_frame
except Exception:
    default_dicom_get_frame = None


def build_lazy_frame_loader(
    path: Path,
    *,
    force: bool = False,
    read_frame_only: bool = True,
    cache_frames: bool = True,
    get_frame_fn=default_dicom_get_frame,
) -> Callable[[int], np.ndarray]:
    ds_cache: Dict[str, Optional[pydicom.Dataset]] = {"ds": None}
    frames_cache: Dict[str, Optional[np.ndarray]] = {"frames": None}
    lock = RLock()

    def _load(index: int) -> np.ndarray:
        with lock:
            ds = ds_cache["ds"]
            if ds is None:
                try:
                    ds = pydicom.dcmread(str(path), force=force)
                except InvalidDicomError as exc:
                    raise DicomLoadError(f"Invalid DICOM: {exc}") from exc
                except Exception as exc:
                    raise DicomLoadError(f"Failed to read DICOM: {exc}") from exc
                ds_cache["ds"] = ds

            frame_count = get_frame_count(ds)
            photometric = getattr(ds, "PhotometricInterpretation", None)
            if index < 0 or index >= frame_count:
                raise IndexError(f"Frame index out of range: {index}")

            if read_frame_only:
                try:
                    if get_frame_fn is not None and frame_count > 1:
                        raw = get_frame_fn(ds, index)
                    else:
                        raw = ds.pixel_array[index] if frame_count > 1 else ds.pixel_array
                except Exception as exc:
                    raise DicomLoadError(f"Failed to decode pixel data: {exc}") from exc
                frame = normalize_frames(raw, photometric)
                return frame[0]

            frames = frames_cache["frames"]
            if frames is None:
                frames = normalize_frames(extract_pixel_array(ds), photometric)
                if cache_frames:
                    frames_cache["frames"] = frames

            if frames.shape[0] <= 1:
                return frames[0]
            return frames[index]

    return _load


def build_subprocess_frame_loader(
    path: Path,
    *,
    force: bool = False,
    timeout_s: float = 20.0,
) -> Callable[[int], np.ndarray]:
    def _load(index: int) -> np.ndarray:
        with tempfile.TemporaryDirectory() as tmpdir:
            out_path = Path(tmpdir) / "frame.npy"
            cmd = [
                sys.executable,
                "-m",
                "app.tools.dicom_decode_frame",
                str(path),
                "--frame",
                str(index),
                "--out",
                str(out_path),
            ]
            if force:
                cmd.append("--force")

            child_env = os.environ.copy()
            child_env["DICOM_SUBPROCESS_DECODE"] = "0"
            overrides = os.getenv("DICOM_SUBPROCESS_ENV_JSON")
            if overrides:
                try:
                    parsed = json.loads(overrides)
                    if isinstance(parsed, dict):
                        for key, value in parsed.items():
                            child_env[str(key)] = str(value)
                except Exception:
                    pass

            timeout_value = timeout_s
            timeout_override = os.getenv("DICOM_SUBPROCESS_TIMEOUT_S")
            if timeout_override:
                try:
                    timeout_value = float(timeout_override)
                except ValueError:
                    timeout_value = timeout_s

            try:
                result = subprocess.run(
                    cmd,
                    capture_output=True,
                    text=True,
                    timeout=timeout_value,
                    env=child_env,
                )
            except subprocess.TimeoutExpired as exc:
                raise DicomLoadError(f"Subprocess decode timed out: {exc}") from exc

            stdout = (result.stdout or "").strip().splitlines()
            payload = None
            if stdout:
                try:
                    payload = json.loads(stdout[-1])
                except Exception:
                    payload = None

            if result.returncode != 0:
                error = None
                if payload and isinstance(payload, dict):
                    error = payload.get("error")
                if not error:
                    error = (result.stderr or "").strip() or "Subprocess decode failed"
                raise DicomLoadError(f"Subprocess decode failed: {error}")

            if not out_path.exists():
                raise DicomLoadError("Subprocess decode failed: output frame missing")

            return np.load(out_path)

    return _load
