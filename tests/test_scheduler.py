from datetime import UTC, datetime

from jobsearcher.config import load_settings
from jobsearcher.db.models import ScrapeRun
from jobsearcher.scheduler import run_missed


def test_run_missed_only_after_daily_time_without_a_run(session):
    s = load_settings()  # 07:00 Europe/Oslo = 05:00 UTC in October
    assert not run_missed(session, s, datetime(2026, 10, 12, 4, 30, tzinfo=UTC))
    assert run_missed(session, s, datetime(2026, 10, 12, 9, 0, tzinfo=UTC))
    session.add(ScrapeRun(trigger="manual", source="nav", started_at=datetime(2026, 10, 12, 6, 0, tzinfo=UTC)))
    session.commit()
    assert not run_missed(session, s, datetime(2026, 10, 12, 9, 0, tzinfo=UTC))
    assert run_missed(session, s, datetime(2026, 10, 13, 9, 0, tzinfo=UTC))
