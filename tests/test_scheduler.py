from datetime import UTC, datetime

from jobsearcher.config import load_settings
from jobsearcher.db.models import ScrapeRun
from jobsearcher.scheduler import jitter_delay, run_missed


def test_run_missed_only_after_daily_time_without_a_run(session):
    s = load_settings()  # 07:00 Europe/Oslo = 05:00 UTC in October
    assert not run_missed(session, s, datetime(2026, 10, 12, 4, 30, tzinfo=UTC))
    assert run_missed(session, s, datetime(2026, 10, 12, 9, 0, tzinfo=UTC))
    session.add(ScrapeRun(trigger="manual", source="nav", started_at=datetime(2026, 10, 12, 6, 0, tzinfo=UTC)))
    session.commit()
    assert not run_missed(session, s, datetime(2026, 10, 12, 9, 0, tzinfo=UTC))
    assert run_missed(session, s, datetime(2026, 10, 13, 9, 0, tzinfo=UTC))


def test_jitter_delay_is_within_window():
    import random
    from datetime import timedelta

    rng = random.Random(1)
    delays = [jitter_delay(40, rng) for _ in range(200)]
    assert all(timedelta(0) <= d <= timedelta(minutes=40) for d in delays)
    assert len({d for d in delays}) > 100
    assert jitter_delay(0) == timedelta(0)
    assert load_settings().schedule.jitter_minutes == 40
