from __future__ import annotations

import argparse
import json
from datetime import datetime, timezone
from pathlib import Path


def _utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


def append_run_log(
    log_path: Path,
    *,
    phase: str,
    command: str,
    status: str,
    workdir: str | None = None,
    exit_code: int | None = None,
    notes: str | None = None,
    kind: str = "command",
) -> Path:
    payload = {
        "timestamp_utc": _utc_now(),
        "phase": phase.strip() or "unspecified",
        "kind": kind.strip() or "command",
        "command": command,
        "status": status.strip() or "unknown",
    }
    if workdir:
        payload["workdir"] = workdir
    if exit_code is not None:
        payload["exit_code"] = int(exit_code)
    if notes:
        payload["notes"] = notes

    log_path.parent.mkdir(parents=True, exist_ok=True)
    with log_path.open("a", encoding="utf-8") as handle:
        handle.write(json.dumps(payload, ensure_ascii=True) + "\n")
    return log_path


def main() -> None:
    parser = argparse.ArgumentParser(description="Append a command run entry to a JSONL log")
    parser.add_argument("--log", required=True, help="Path to the JSONL log file")
    parser.add_argument("--phase", required=True, help="Implementation phase or activity name")
    parser.add_argument("--command", required=True, help="Executed command or action description")
    parser.add_argument("--status", default="ok", help="Run status")
    parser.add_argument("--workdir", default="", help="Working directory")
    parser.add_argument("--exit-code", type=int, default=None, help="Exit code when available")
    parser.add_argument("--notes", default="", help="Optional free-form notes")
    parser.add_argument("--kind", default="command", help="Entry kind")
    args = parser.parse_args()

    append_run_log(
        Path(args.log),
        phase=args.phase,
        command=args.command,
        status=args.status,
        workdir=args.workdir or None,
        exit_code=args.exit_code,
        notes=args.notes or None,
        kind=args.kind,
    )


if __name__ == "__main__":
    main()
