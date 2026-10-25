# Meeting Scheduler

Find a meeting time that works for everyone — given several people's busy
calendars, detect conflicts with a proposed meeting, list the common free
time, and suggest the earliest slots of a requested length.

## Problem

Scheduling a meeting across calendars is an interval problem, not a
calendar-app problem. Busy blocks arrive unsorted, overlapping, and nested;
the useful answers are the merged busy time, its complement inside a work
window, and the intersection of "free" across all attendees. This package
solves exactly that, with no dependencies.

## Design decisions

1. **Half-open intervals `[start, end)`.** A meeting ending at 10:00 does
   not conflict with one starting at 10:00. Overlap is therefore strict,
   which matches how people actually book back-to-back meetings.
2. **Merge first, then invert.** All busy blocks are merged into a sorted,
   disjoint list (sweep-line, O(n log n)) before any free-time computation.
   Common free time is then one inversion of the union of everyone's busy
   blocks, instead of pairwise intersections of free slots.
3. **Touching busy blocks merge.** A zero-minute gap between two busy
   blocks can never hold a meeting, so merging them keeps the free-slot
   list honest.
4. **Timezone-naive datetimes.** Callers normalise to one zone (e.g. UTC)
   before constructing intervals; the algorithms only compare datetimes,
   so they stay simple and testable.

## Usage

```python
from datetime import datetime, timedelta
from meeting_scheduler.scheduler import Calendar, Interval, suggest_slots

day = lambda h: datetime(2026, 10, 26, h)
amina = Calendar("Amina", [Interval(day(9), day(10))])
bilal = Calendar("Bilal", [Interval(day(11), day(12))])
window = Interval(day(9), day(17))

suggest_slots([amina, bilal], window, timedelta(minutes=60))
# [Interval(10:00–11:00), Interval(12:00–13:00), ...]
```

### CLI

Busy calendars live in a JSON file (see `examples/calendars.json`):

```bash
PYTHONPATH=src python -m meeting_scheduler.cli suggest examples/calendars.json \
  --start "2026-10-26 09:00" --end "2026-10-26 17:00" --duration 45
# 2026-10-26 10:00 - 2026-10-26 10:45
# 2026-10-26 12:00 - 2026-10-26 12:45
# ...

PYTHONPATH=src python -m meeting_scheduler.cli check examples/calendars.json \
  --start "2026-10-26 09:30" --end "2026-10-26 10:30"
# Conflict (Amina): 2026-10-26 09:00 - 2026-10-26 10:00

PYTHONPATH=src python -m meeting_scheduler.cli free examples/calendars.json \
  --start "2026-10-26 09:00" --end "2026-10-26 17:00"
```

## Running tests

```bash
pip install pytest
PYTHONPATH=src pytest -q
```

## Tech stack

Python 3.10+, standard library only. Tests with pytest.
