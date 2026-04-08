from __future__ import annotations

import argparse
import subprocess
import sys
from pathlib import Path

from app.tools.runtime.log_run import append_run_log


def main() -> None:
    parser = argparse.ArgumentParser(description="Run a command and append JSONL run logs")
    parser.add_argument("--log", required=True, help="Path to the JSONL log file")
    parser.add_argument("--phase", required=True, help="Implementation phase or activity")
    parser.add_argument("--workdir", default="", help="Working directory")
    parser.add_argument("--kind", default="command", help="Entry kind")
    parser.add_argument("command", nargs=argparse.REMAINDER, help="Command to execute")
    args = parser.parse_args()

    command = list(args.command)
    if command and command[0] == "--":
        command = command[1:]
    if not command:
        raise SystemExit("No command provided.")

    log_path = Path(args.log)
    workdir = args.workdir or None
    command_text = subprocess.list2cmdline(command)

    append_run_log(
        log_path,
        phase=args.phase,
        command=command_text,
        status="started",
        workdir=workdir,
        kind=args.kind,
    )

    completed = subprocess.run(command, cwd=workdir)
    status = "ok" if completed.returncode == 0 else "failed"
    append_run_log(
        log_path,
        phase=args.phase,
        command=command_text,
        status=status,
        workdir=workdir,
        exit_code=completed.returncode,
        kind=args.kind,
    )
    raise SystemExit(completed.returncode)


if __name__ == "__main__":
    main()
