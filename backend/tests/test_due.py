from datetime import UTC, datetime, timedelta

from app.ingest.runner import is_due

NOW = datetime(2026, 10, 14, 2, 0, tzinfo=UTC)


def ago(minutes: float) -> datetime:
    return NOW - timedelta(minutes=minutes)


def test_never_attempted_is_due():
    assert is_due(10080, None, None, NOW)


def test_weekly_source_waits_a_week():
    assert not is_due(10080, ago(60 * 24), None, NOW)
    assert is_due(10080, ago(10080), None, NOW)


def test_slack_keeps_a_15_minute_source_on_a_15_minute_schedule():
    assert not is_due(15, ago(14.8), None, NOW)
    assert is_due(15, ago(14.8), None, NOW, slack_minutes=5)
    assert not is_due(30, ago(15), None, NOW, slack_minutes=5)


def test_failed_source_retries_within_the_hour():
    assert not is_due(10080, ago(30), "503", NOW)
    assert is_due(10080, ago(60), "503", NOW)
    assert not is_due(15, ago(5), "503", NOW, slack_minutes=5)
