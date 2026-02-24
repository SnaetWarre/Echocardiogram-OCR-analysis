from __future__ import annotations

import argparse
import json
import sys
import traceback
from dataclasses import dataclass
from pathlib import Path
from typing import Dict, Iterable, List, Set

PROJECT_ROOT = Path(__file__).resolve().parents[2]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from app.models.types import PipelineRequest  # noqa: E402
from app.pipeline.echo_ocr_pipeline import EchoOcrPipeline  # noqa: E402


@dataclass(frozen=True)
class RunConfig:
    retries: int
    pattern: str
    out_dir: Path
    state_path: Path
    failure_dir: Path


def iter_dicom_files(root: Path, pattern: str) -> Iterable[Path]:
    if root.is_file():
        yield root
        return
    for path in root.rglob(pattern):
        if path.is_file():
            yield path


def load_state(path: Path) -> Dict[str, object]:
    if not path.exists():
        return {"done": [], "failed": {}}
    return json.loads(path.read_text(encoding="utf-8"))


def save_state(path: Path, state: Dict[str, object]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(state, indent=2), encoding="utf-8")


def write_failure_artifact(config: RunConfig, dicom_path: Path, error: str) -> None:
    config.failure_dir.mkdir(parents=True, exist_ok=True)
    safe_name = dicom_path.stem.replace(" ", "_")
    payload = {
        "dicom_path": str(dicom_path),
        "error": error,
    }
    artifact = config.failure_dir / f"{safe_name}.failure.json"
    artifact.write_text(json.dumps(payload, indent=2), encoding="utf-8")


def process_one(path: Path, pipeline: EchoOcrPipeline, out_dir: Path, retries: int) -> str:
    last_error = ""
    for _attempt in range(retries + 1):
        result = pipeline.run(PipelineRequest(dicom_path=path, output_dir=out_dir))
        if result.status == "ok":
            return "ok"
        last_error = result.error or "unknown error"
    raise RuntimeError(last_error)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Resumable batch OCR runner for echocardiogram DICOM files.")
    parser.add_argument("root", type=Path, help="DICOM root folder or single file")
    parser.add_argument("--pattern", type=str, default="*.dcm")
    parser.add_argument("--out-dir", type=Path, default=Path("artifacts/echo-ocr"))
    parser.add_argument("--state-path", type=Path, default=Path("artifacts/echo-ocr/state.json"))
    parser.add_argument("--failure-dir", type=Path, default=Path("artifacts/echo-ocr/failures"))
    parser.add_argument("--retries", type=int, default=2)
    parser.add_argument("--max-files", type=int, default=0)
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    cfg = RunConfig(
        retries=max(0, args.retries),
        pattern=args.pattern,
        out_dir=args.out_dir,
        state_path=args.state_path,
        failure_dir=args.failure_dir,
    )
    state = load_state(cfg.state_path)
    done: Set[str] = set(state.get("done", []))
    failed: Dict[str, str] = dict(state.get("failed", {}))

    files = list(iter_dicom_files(args.root, cfg.pattern))
    if args.max_files > 0:
        files = files[: args.max_files]
    pipeline = EchoOcrPipeline()

    for index, path in enumerate(files, start=1):
        path_key = str(path)
        if path_key in done:
            continue
        try:
            process_one(path, pipeline, cfg.out_dir, retries=cfg.retries)
            done.add(path_key)
            failed.pop(path_key, None)
            print(f"[{index}/{len(files)}] ok   {path}")
        except Exception as exc:  # noqa: BLE001
            error = f"{exc}\n{traceback.format_exc(limit=1)}"
            failed[path_key] = str(exc)
            write_failure_artifact(cfg, path, error=error)
            print(f"[{index}/{len(files)}] fail {path} :: {exc}")
        save_state(
            cfg.state_path,
            {
                "done": sorted(done),
                "failed": failed,
            },
        )

    print(f"Done: {len(done)}")
    print(f"Failed: {len(failed)}")
    return 0 if not failed else 1


if __name__ == "__main__":
    raise SystemExit(main())
