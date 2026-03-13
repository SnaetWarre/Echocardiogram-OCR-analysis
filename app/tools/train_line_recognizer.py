from __future__ import annotations

import argparse
import json
import sys
from collections import Counter
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[2]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))


def _read_manifest(path: Path) -> list[dict[str, object]]:
    rows: list[dict[str, object]] = []
    for line in path.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line:
            continue
        payload = json.loads(line)
        if isinstance(payload, dict):
            rows.append(payload)
    return rows


def main() -> None:
    parser = argparse.ArgumentParser(description="Prepare a line recognizer fine-tuning run skeleton")
    parser.add_argument(
        "--manifest",
        default=str(PROJECT_ROOT / "docs" / "ocr_redesign" / "line_recognizer_manifest.jsonl"),
    )
    parser.add_argument(
        "--output-dir",
        default=str(PROJECT_ROOT / "docs" / "ocr_redesign" / "line_recognizer_training"),
    )
    parser.add_argument("--framework", default="trocr", help="Training target framework label")
    parser.add_argument("--base-model", default="microsoft/trocr-base-stage1")
    parser.add_argument("--epochs", type=int, default=12)
    parser.add_argument("--batch-size", type=int, default=8)
    parser.add_argument("--learning-rate", type=float, default=3e-5)
    parser.add_argument("--dry-run", action="store_true", help="Only validate manifest and write run metadata")
    args = parser.parse_args()

    manifest_path = Path(args.manifest)
    if not manifest_path.exists():
        raise SystemExit(f"Manifest not found: {manifest_path}")

    rows = _read_manifest(manifest_path)
    if not rows:
        raise SystemExit(f"Manifest is empty: {manifest_path}")

    output_dir = Path(args.output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)

    split_counts = Counter(str(row.get("split", "unspecified") or "unspecified") for row in rows)
    missing_images = [str(row.get("image_path", "")) for row in rows if not Path(str(row.get("image_path", ""))).exists()]
    plan = {
        "framework": args.framework,
        "base_model": args.base_model,
        "manifest": str(manifest_path),
        "example_count": len(rows),
        "split_counts": dict(sorted(split_counts.items())),
        "epochs": args.epochs,
        "batch_size": args.batch_size,
        "learning_rate": args.learning_rate,
        "missing_image_count": len(missing_images),
        "sample_launch_command": (
            "python -m app.tools.train_line_recognizer "
            f"--manifest {manifest_path} --output-dir {output_dir} "
            f"--framework {args.framework} --base-model {args.base_model}"
        ),
    }
    (output_dir / "run_plan.json").write_text(json.dumps(plan, indent=2, ensure_ascii=True) + "\n", encoding="utf-8")

    train_manifest = output_dir / "train_manifest.jsonl"
    val_manifest = output_dir / "validation_manifest.jsonl"
    with train_manifest.open("w", encoding="utf-8") as train_handle, val_manifest.open("w", encoding="utf-8") as val_handle:
        for row in rows:
            destination = val_handle if str(row.get("split", "")).strip().lower() == "validation" else train_handle
            destination.write(json.dumps(row, ensure_ascii=True) + "\n")

    if args.dry_run:
        print(json.dumps(plan, indent=2, ensure_ascii=True))
        return

    raise SystemExit(
        "Training skeleton prepared. Install the optional training stack in a dedicated mamba environment, "
        "then extend this script with your chosen trainer implementation."
    )


if __name__ == "__main__":
    main()
