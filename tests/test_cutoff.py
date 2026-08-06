from datetime import datetime, timezone

from ai_work_automation.cutoff import is_after_cutoff


def test_before_cutoff_is_blocked():
    created = datetime(2024, 7, 7, tzinfo=timezone.utc)
    cutoff = datetime(2026, 12, 1, tzinfo=timezone.utc)
    assert is_after_cutoff(created, cutoff) is False


def test_on_or_after_cutoff_is_allowed():
    created = datetime(2026, 12, 1, tzinfo=timezone.utc)
    cutoff = datetime(2026, 12, 1, tzinfo=timezone.utc)
    assert is_after_cutoff(created, cutoff) is True
