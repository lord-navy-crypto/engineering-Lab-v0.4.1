#!/usr/bin/env python3
"""Run Physical Lab dynamics frequency-response studies from the command line."""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
UI = ROOT / "src-tauri" / "resources" / "ui"
sys.path.insert(0, str(UI))

from physical_lab_frequency_response import (  # noqa: E402
    duffing_frequency_sweep,
    linear_forced_response_sweep,
)


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Physical Lab frequency-response simulation")
    sub = parser.add_subparsers(dest="model", required=True)

    linear = sub.add_parser("linear", help="forced linear oscillator with analytic reference")
    linear.add_argument("--omega-n", type=float, default=2.0)
    linear.add_argument("--zeta", type=float, default=0.05)
    linear.add_argument("--force", type=float, default=1.0)
    linear.add_argument("--start", type=float, default=0.6)
    linear.add_argument("--stop", type=float, default=3.2)
    linear.add_argument("--points", type=int, default=25)
    linear.add_argument("--settle-cycles", type=int, default=24)
    linear.add_argument("--observe-cycles", type=int, default=8)
    linear.add_argument("--points-per-cycle", type=int, default=72)
    linear.add_argument("--out", type=Path, help="optional JSON output path")

    duffing = sub.add_parser("duffing", help="hardening Duffing forward/reverse continuation sweep")
    duffing.add_argument("--omega-0", type=float, default=1.0)
    duffing.add_argument("--zeta", type=float, default=0.05)
    duffing.add_argument("--beta", type=float, default=1.0)
    duffing.add_argument("--force", type=float, default=0.30)
    duffing.add_argument("--start", type=float, default=0.70)
    duffing.add_argument("--stop", type=float, default=1.60)
    duffing.add_argument("--points", type=int, default=25)
    duffing.add_argument("--settle-cycles", type=int, default=35)
    duffing.add_argument("--observe-cycles", type=int, default=8)
    duffing.add_argument("--points-per-cycle", type=int, default=60)
    duffing.add_argument("--out", type=Path, help="optional JSON output path")
    return parser


def main() -> int:
    args = build_parser().parse_args()
    if args.model == "linear":
        result = linear_forced_response_sweep(
            omega_n=args.omega_n,
            zeta=args.zeta,
            force_amplitude=args.force,
            frequency_start=args.start,
            frequency_stop=args.stop,
            frequency_points=args.points,
            settle_cycles=args.settle_cycles,
            observe_cycles=args.observe_cycles,
            points_per_cycle=args.points_per_cycle,
        )
    else:
        result = duffing_frequency_sweep(
            omega_0=args.omega_0,
            zeta=args.zeta,
            cubic_stiffness=args.beta,
            force_amplitude=args.force,
            frequency_start=args.start,
            frequency_stop=args.stop,
            frequency_points=args.points,
            settle_cycles=args.settle_cycles,
            observe_cycles=args.observe_cycles,
            points_per_cycle=args.points_per_cycle,
        )

    encoded = json.dumps(result, indent=2, sort_keys=True, allow_nan=False) + "\n"
    if args.out:
        args.out.write_text(encoded, encoding="utf-8")
        print(f"Wrote {args.out}")
    else:
        print(encoded, end="")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
