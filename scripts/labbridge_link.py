#!/usr/bin/env python3
"""Local coordinator CLI for BetterBoard -> Engineering Lab -> OpenPenguin.

Examples:
  python3 scripts/labbridge_link.py --project /path/to/project.physlab --status
  python3 scripts/labbridge_link.py --project /path/to/project.physlab --watch
  python3 scripts/labbridge_link.py --project /path/to/project.physlab --ask "What should I inspect next?"

The watcher never auto-ingests BetterBoard evidence. AI recording is opt-in with
``--record`` and ActionProposal execution is intentionally unsupported here.
"""
from __future__ import annotations

import argparse
import json
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
UI_ROOT = ROOT / "src-tauri" / "resources" / "ui"
if str(UI_ROOT) not in sys.path:
    sys.path.insert(0, str(UI_ROOT))

from physical_lab_labbridge_link import ask_openguin_about_project, bridge_status  # noqa: E402


def emit(value: object) -> None:
    print(json.dumps(value, indent=2, sort_keys=True, ensure_ascii=False))


def main() -> int:
    parser = argparse.ArgumentParser(description="Coordinate BetterBoard, Engineering Lab and OpenPenguin through LabBridge v1")
    parser.add_argument("--project", required=True, help="Engineering Lab .physlab project directory")
    parser.add_argument("--measurement-root", default="", help="Optional BetterBoard measurement root override")
    parser.add_argument("--status", action="store_true", help="Run one non-destructive bridge status pass")
    parser.add_argument("--watch", action="store_true", help="Continue status passes locally")
    parser.add_argument("--interval", type=float, default=2.0, help="Watch interval in seconds (minimum 0.5)")
    parser.add_argument("--ask", default="", help="Ask OpenPenguin using canonical Engineering Lab AIContext")
    parser.add_argument("--focus", default="", help="Optional AIContext focus")
    parser.add_argument("--profile", default="", help="Optional Engineering Lab profile")
    parser.add_argument("--model", default="", help="Explicit installed local model")
    parser.add_argument("--record", action="store_true", help="Explicitly record AI response as an advisory LabBridge packet")
    parser.add_argument("--allow-ollama-fallback", action="store_true", help="Allow external loopback Ollama if OpenPenguin private runtime is unavailable")
    args = parser.parse_args()

    project = Path(args.project).expanduser().resolve()
    measurement_root = Path(args.measurement_root).expanduser().resolve() if args.measurement_root else None

    if args.ask:
        emit(ask_openguin_about_project(
            project,
            question=args.ask,
            focus=args.focus,
            profile=args.profile,
            model=args.model,
            record=args.record,
            allow_ollama_fallback=args.allow_ollama_fallback,
        ))
        return 0

    interval = max(0.5, float(args.interval))
    while True:
        status = bridge_status(project, measurement_root=measurement_root)
        if args.watch:
            emit({
                "schema": status["schema"],
                "valid_new_measurements": len(status["betterboard"]["valid_new"]),
                "inbox_counts": status["betterboard"]["counts"],
                "openguin": status["openguin"]["openpenguin"],
                "automatic_actions": status["automatic_actions"],
            })
        else:
            emit(status)
            return 0
        time.sleep(interval)


if __name__ == "__main__":
    raise SystemExit(main())
