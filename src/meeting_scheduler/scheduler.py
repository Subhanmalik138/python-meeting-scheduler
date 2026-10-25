"""Meeting scheduling over time intervals.

The core problem is a classic one: given several people's busy calendars,
when can they all meet, and does a proposed meeting clash with anything?

All times are timezone-naive ``datetime`` objects. Callers that care about
timezones should normalise to a single zone (e.g. UTC) before constructing
intervals; the algorithms here are zone-agnostic and only compare datetimes.

Two boundary rules, chosen deliberately and tested:

* Overlap is strict: ``[09:00, 10:00)`` and ``[10:00, 11:00)`` do *not*
  conflict. A meeting ending exactly when another starts is fine.
* Merging is inclusive of touching intervals: busy blocks that touch are
  merged into one block, because the gap between them is zero minutes and
  can never hold a meeting anyway.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timedelta


@dataclass(frozen=True, order=True)
class Interval:
    """A half-open time interval ``[start, end)``.

    ``order=True`` sorts by ``start`` first, which is exactly what the
    sweep-line merge needs.
    """

    start: datetime
    end: datetime

    def __post_init__(self) -> None:
        if self.end <= self.start:
            raise ValueError(
                f"interval end ({self.end}) must be after start ({self.start})"
            )

    @property
    def duration(self) -> timedelta:
        return self.end - self.start

    def overlaps(self, other: "Interval") -> bool:
        """Strict overlap: touching intervals do not overlap."""
        return self.start < other.end and other.start < self.end

    def intersection(self, other: "Interval") -> "Interval | None":
        """The shared part of two intervals, or None if they don't overlap."""
        if not self.overlaps(other):
            return None
        return Interval(max(self.start, other.start), min(self.end, other.end))

    def __str__(self) -> str:  # pragma: no cover - cosmetic
        return f"{self.start:%Y-%m-%d %H:%M} - {self.end:%H:%M}"


def merge_intervals(intervals: list[Interval]) -> list[Interval]:
    """Merge overlapping or touching intervals into a sorted, disjoint list.

    Sweep-line algorithm: sort by start, then walk once, extending the
    current block whenever the next interval starts at or before it ends.
    O(n log n) because of the sort; the sweep itself is O(n).
    """
    merged: list[Interval] = []
    for interval in sorted(intervals):
        if merged and interval.start <= merged[-1].end:
            current = merged[-1]
            if interval.end > current.end:
                merged[-1] = Interval(current.start, interval.end)
        else:
            merged.append(interval)
    return merged


def invert_intervals(
    busy: list[Interval], window: Interval
) -> list[Interval]:
    """Free time inside ``window``: the complement of ``busy`` clipped to it."""
    free: list[Interval] = []
    cursor = window.start
    for block in merge_intervals(busy):
        block = block.intersection(window)
        if block is None:
            continue
        if block.start > cursor:
            free.append(Interval(cursor, block.start))
        cursor = max(cursor, block.end)
    if cursor < window.end:
        free.append(Interval(cursor, window.end))
    return free


class Calendar:
    """One person's busy schedule."""

    def __init__(self, name: str, busy: list[Interval] | None = None) -> None:
        self.name = name
        self._busy: list[Interval] = list(busy or [])

    def add(self, interval: Interval) -> None:
        self._busy.append(interval)

    @property
    def busy(self) -> list[Interval]:
        """Busy blocks, merged and sorted."""
        return merge_intervals(self._busy)

    def conflicts(self, proposed: Interval) -> list[Interval]:
        """Busy blocks that clash with ``proposed`` (empty = it fits)."""
        return [block for block in self.busy if block.overlaps(proposed)]

    def is_free(self, proposed: Interval) -> bool:
        return not self.conflicts(proposed)

    def free_slots(self, window: Interval) -> list[Interval]:
        """Maximal free intervals inside ``window``."""
        return invert_intervals(self._busy, window)


def common_free_slots(
    calendars: list[Calendar], window: Interval
) -> list[Interval]:
    """Times when *every* calendar is free inside ``window``.

    Merging all busy blocks first, then inverting once, is both simpler
    and faster than intersecting each calendar's free slots pairwise.
    """
    all_busy = [block for cal in calendars for block in cal.busy]
    return invert_intervals(all_busy, window)


def suggest_slots(
    calendars: list[Calendar],
    window: Interval,
    duration: timedelta,
    limit: int = 5,
) -> list[Interval]:
    """Earliest slots of exactly ``duration`` inside the common free time.

    Each free interval contributes slots starting at its beginning; a
    long free stretch yields one slot (the earliest start), not a
    sliding window of back-to-back options, so suggestions stay readable.
    """
    if duration <= timedelta(0):
        raise ValueError("duration must be positive")
    if limit < 1:
        raise ValueError("limit must be at least 1")
    suggestions: list[Interval] = []
    for free in common_free_slots(calendars, window):
        if free.duration >= duration:
            suggestions.append(Interval(free.start, free.start + duration))
            if len(suggestions) == limit:
                break
    return suggestions


def next_available(
    calendar: Calendar, after: datetime, duration: timedelta
) -> Interval:
    """Earliest slot of ``duration`` for one calendar starting at ``after``.

    Searches from ``after`` in the calendar's own free time; the window
    end is generous (one year) because the caller, not this function,
    should decide how far ahead is reasonable.
    """
    if duration <= timedelta(0):
        raise ValueError("duration must be positive")
    window = Interval(after, after + timedelta(days=365))
    for free in calendar.free_slots(window):
        if free.duration >= duration:
            return Interval(free.start, free.start + duration)
    raise ValueError("no free slot found")  # unreachable with a 1-year window
