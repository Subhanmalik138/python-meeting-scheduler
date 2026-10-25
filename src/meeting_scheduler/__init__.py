"""Meeting scheduler: interval merging, conflict detection, free slots."""

from .scheduler import Calendar, Interval, common_free_slots, merge_intervals, next_available, suggest_slots

__all__ = [
    "Calendar",
    "Interval",
    "common_free_slots",
    "merge_intervals",
    "next_available",
    "suggest_slots",
]
