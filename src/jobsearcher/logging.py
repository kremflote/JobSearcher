"""JSON-line logging to DATA_DIR/logs/jobsearcher-YYYY-MM-DD.log (ARCHITECTURE §12)."""

from __future__ import annotations

import json
import logging
import logging.handlers
from datetime import UTC, datetime

from jobsearcher.config import env

_configured = False


class JsonFormatter(logging.Formatter):
    def format(self, record: logging.LogRecord) -> str:
        entry = {
            "ts": datetime.fromtimestamp(record.created, UTC).isoformat(timespec="seconds"),
            "level": record.levelname.lower(),
            "logger": record.name,
            "msg": record.getMessage(),
        }
        if record.exc_info:
            entry["exc"] = self.formatException(record.exc_info)
        extra = getattr(record, "data", None)
        if extra:
            entry["data"] = extra
        return json.dumps(entry, ensure_ascii=False, default=str)


def setup_logging(level: int = logging.INFO, console: bool = True) -> None:
    """Idempotent. Daily rotating JSON file, 30 days kept, plus plain console output."""
    global _configured
    if _configured:
        return
    logs = env().logs_dir
    logs.mkdir(parents=True, exist_ok=True)
    root = logging.getLogger()
    root.setLevel(level)

    file_handler = logging.handlers.TimedRotatingFileHandler(
        logs / "jobsearcher.log", when="midnight", backupCount=30, encoding="utf-8", utc=True
    )
    file_handler.namer = lambda name: str(
        logs / f"jobsearcher-{name.rsplit('.', 1)[-1]}.log"
    )
    file_handler.setFormatter(JsonFormatter())
    root.addHandler(file_handler)

    if console:
        stream = logging.StreamHandler()
        stream.setFormatter(logging.Formatter("%(asctime)s %(levelname)s %(name)s: %(message)s"))
        root.addHandler(stream)
    logging.getLogger("httpx").setLevel(logging.WARNING)
    logging.getLogger("alembic").setLevel(logging.WARNING)
    _configured = True
