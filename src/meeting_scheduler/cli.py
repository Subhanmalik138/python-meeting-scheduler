"""Command-line interface.

Busy calendars are given as a JSON file::

    {"calendars": [
      {"name": "Amina", "busy": [["2026-10-26 09:00", "2026-10-26 10:00"]]},
      {"name": "Bilal", "busy": [["2026-10-26 11:00", "2026-10-26 12:00"]]}
    ]}

Commands::

    python -m meeting_scheduler.cli suggest calendars.json \\
        --window-start "2026-10-26 09:00" --window-end "2026-10-26 17:00" \\
        --duration 45
    python -m meeting_scheduler.cli check calendars.json \\
        --start "2026-10-26 09:30" --end "2026-10-26 10:30"
"""

from __future__ import annotations

import argparse
import json
import sys
from datetime import datetime, timedelta
from pathlib import Path

from .scheduler import Calendar, Interval, common_free_slots, suggest_slots

TIME_FMT = "%Y-%m-%d %H:%M"


def _parse_time(text: str) -> datetime:
    try:
        return datetime.strptime(text, TIME_FMT)
    except ValueError as exc:
        raise argparse.ArgumentTypeError(
            f"expected 'YYYY-MM-DD HH:MM', got {text!r}"
        ) from exc


def _load_calendars(path: Path) -> list[Calendar]:
    data = json.loads(path.read_text(encoding="utf-8"))
    calendars: list[Calendar] = []
    for entry in data.get("calendars", []):
        busy = [
            Interval(_parse_time(start), _parse_time(end))
            for start, end in entry.get("busy", [])
        ]
        calendars.append(Calendar(entry.get("name", "unnamed"), busy))
    return calendars


def _fmt(interval: Interval) -> str:
    return f"{interval.start.strftime(TIME_FMT)} - {interval.end.strftime(TIME_FMT)}"


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        prog="meeting-scheduler",
        description="Find meeting times that work for everyone.",
    )
    sub = parser.add_subparsers(dest="command", required=True)

    for name in ("suggest", "free", "check"):
        p = sub.add_parser(name)
        p.add_argument("calendars", type=Path, help="JSON calendars file")
        p.add_argument("--start", type=_parse_time, required=True,
                       help="window/proposed start 'YYYY-MM-DD HH:MM'")
        p.add_argument("--end", type=_parse_time, required=True,
                       help="window/proposed end 'YYYY-MM-DD HH:MM'")
        if name != "check":
            p.add_argument("--duration", type=int, default=30,
                           help="meeting length in minutes (suggest only)")
        if name == "suggest":
            p.add_argument("--limit", type=int, default=5,
                           help="max suggestions to print")

    args = parser.parse_args(argv)
    try:
        calendars = _load_calendars(args.calendars)
        window = Interval(args.start, args.end)
    except (ValueError, OSError, json.JSONDecodeError, KeyError) as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 2

    if args.command == "check":
        clashes = {
            cal.name: cal.conflicts(window) for cal in calendars
        }
        clashes = {k: v for k, v in clashes.items() if v}
        if not clashes:
            print(f"Free: {_fmt(window)} works for everyone.")
            return 0
        for name, blocks in clashes.items():
            for block in blocks:
                print(f"Conflict ({name}): {_fmt(block)}")
        return 1

    if args.command == "free":
        for slot in common_free_slots(calendars, window):
            print(_fmt(slot))
        return 0

    # suggest
    try:
        slots = suggest_slots(
            calendars, window, timedelta(minutes=args.duration), args.limit
        )
    except ValueError as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 2
    if not slots:
        print("No slot of that length fits in the window.")
        return 1
    for slot in slots:
        print(_fmt(slot))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
