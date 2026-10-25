"""Tests for the meeting scheduler core."""

from datetime import datetime, timedelta

import pytest

from meeting_scheduler.scheduler import (
    Calendar,
    Interval,
    common_free_slots,
    merge_intervals,
    next_available,
    suggest_slots,
)


def dt(hour: int, minute: int = 0) -> datetime:
    return datetime(2026, 10, 26, hour, minute)


def iv(sh: int, eh: int, sm: int = 0, em: int = 0) -> Interval:
    return Interval(dt(sh, sm), dt(eh, em))


# --- Interval basics -------------------------------------------------------

def test_invalid_interval_rejected():
    with pytest.raises(ValueError):
        Interval(dt(10), dt(10))
    with pytest.raises(ValueError):
        Interval(dt(11), dt(10))


def test_touching_intervals_do_not_overlap():
    assert not iv(9, 10).overlaps(iv(10, 11))
    assert not iv(10, 11).overlaps(iv(9, 10))


def test_partial_and_nested_overlap():
    assert iv(9, 11).overlaps(iv(10, 12))
    assert iv(9, 12).overlaps(iv(10, 11))
    assert iv(9, 11).intersection(iv(10, 12)) == iv(10, 11)


def test_no_intersection_for_touching_intervals():
    assert iv(9, 10).intersection(iv(10, 11)) is None


# --- Merging ---------------------------------------------------------------

def test_merge_unsorted_overlapping_and_nested():
    merged = merge_intervals([iv(13, 14), iv(9, 11), iv(10, 12)])
    assert merged == [iv(9, 12), iv(13, 14)]


def test_merge_touching_blocks():
    # Zero-minute gap can never hold a meeting, so touching blocks merge.
    assert merge_intervals([iv(9, 10), iv(10, 11)]) == [iv(9, 11)]


def test_merge_disjoint_kept_separate():
    assert merge_intervals([iv(9, 10), iv(12, 13)]) == [iv(9, 10), iv(12, 13)]


def test_merge_empty():
    assert merge_intervals([]) == []


# --- Calendar conflicts ----------------------------------------------------

def test_conflicts_found_and_reported():
    cal = Calendar("Amina", [iv(9, 10), iv(13, 14)])
    assert cal.conflicts(iv(9, 10, 30)) == [iv(9, 10)]
    assert cal.conflicts(iv(10, 11)) == []  # touching the 09-10 block is fine
    assert cal.is_free(iv(11, 12))


def test_calendar_merges_on_read():
    cal = Calendar("Bilal", [
        iv(11, 12),
        iv(9, 10),
        Interval(dt(9), datetime(2026, 10, 26, 10, 30)),
    ])
    assert cal.busy == [Interval(dt(9), datetime(2026, 10, 26, 10, 30)), iv(11, 12)]


# --- Free slots ------------------------------------------------------------

def test_free_slots_are_complement_within_window():
    cal = Calendar("Amina", [iv(10, 11), iv(13, 14)])
    assert cal.free_slots(iv(9, 17)) == [iv(9, 10), iv(11, 13), iv(14, 17)]


def test_busy_outside_window_clipped():
    cal = Calendar("Amina", [iv(8, 10), iv(16, 18)])
    assert cal.free_slots(iv(9, 17)) == [iv(10, 16)]


def test_empty_calendar_is_fully_free():
    assert Calendar("Free").free_slots(iv(9, 17)) == [iv(9, 17)]


def test_fully_busy_window_has_no_free_slots():
    assert Calendar("Busy", [iv(9, 17)]).free_slots(iv(9, 17)) == []


# --- Common free time / suggestions ----------------------------------------

def test_common_free_requires_everyone_free():
    a = Calendar("A", [iv(9, 10)])
    b = Calendar("B", [iv(12, 13)])
    assert common_free_slots([a, b], iv(9, 17)) == [iv(10, 12), iv(13, 17)]


def test_common_free_with_no_calendars_is_whole_window():
    assert common_free_slots([], iv(9, 17)) == [iv(9, 17)]


def test_suggest_returns_earliest_slots_of_exact_length():
    a = Calendar("A", [iv(9, 10)])
    b = Calendar("B", [iv(12, 13)])
    slots = suggest_slots([a, b], iv(9, 17), timedelta(minutes=60), limit=2)
    assert slots == [Interval(dt(10), dt(11)), Interval(dt(13), dt(14))]


def test_suggest_skips_free_stretches_shorter_than_duration():
    a = Calendar("A", [Interval(dt(9), datetime(2026, 10, 26, 16, 30))])
    slots = suggest_slots([a], iv(9, 17), timedelta(minutes=60))
    assert slots == []  # only a 30-minute gap remains


def test_suggest_limit_respected():
    cal = Calendar("A", [iv(10, 11), iv(13, 14)])
    slots = suggest_slots([cal], iv(9, 17), timedelta(minutes=30), limit=1)
    assert slots == [Interval(dt(9), dt(9, 30))]


def test_suggest_rejects_non_positive_duration_and_limit():
    with pytest.raises(ValueError):
        suggest_slots([], iv(9, 17), timedelta(0))
    with pytest.raises(ValueError):
        suggest_slots([], iv(9, 17), timedelta(minutes=30), limit=0)


# --- Next available ----------------------------------------------------------

def test_next_available_skips_busy_blocks():
    cal = Calendar("A", [iv(9, 12)])
    slot = next_available(cal, dt(9), timedelta(minutes=60))
    assert slot == Interval(dt(12), dt(13))


def test_next_available_from_free_moment_starts_there():
    cal = Calendar("A", [iv(13, 14)])
    slot = next_available(cal, dt(10), timedelta(minutes=30))
    assert slot == Interval(dt(10), dt(10, 30))
