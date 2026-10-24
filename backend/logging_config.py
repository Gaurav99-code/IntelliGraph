"""Small, local-only rotating log setup for the IntelliGraph demo."""

from __future__ import annotations

import logging
from logging.handlers import RotatingFileHandler
from pathlib import Path


LOG_FORMAT = "%(asctime)s | %(levelname)s | %(name)s | %(message)s"
LOG_MAX_BYTES = 2 * 1024 * 1024
LOG_BACKUP_COUNT = 3


def configure_logging(log_dir: Path) -> None:
    """Create separate backend and frontend log files without duplicating handlers."""

    log_dir.mkdir(parents=True, exist_ok=True)
    formatter = logging.Formatter(LOG_FORMAT)
    for logger_name, filename in (
        ("intelligraph.backend", "backend.log"),
        ("intelligraph.frontend", "frontend.log"),
    ):
        logger = logging.getLogger(logger_name)
        logger.setLevel(logging.INFO)
        logger.propagate = False
        if logger.handlers:
            continue
        handler = RotatingFileHandler(
            log_dir / filename,
            maxBytes=LOG_MAX_BYTES,
            backupCount=LOG_BACKUP_COUNT,
            encoding="utf-8",
        )
        handler.setFormatter(formatter)
        logger.addHandler(handler)


def read_log_lines(log_dir: Path, source: str, limit: int = 250) -> dict[str, list[str]]:
    """Read only the last bounded lines from the requested local log files."""

    sources = ("backend", "frontend") if source == "all" else (source,)
    logs: dict[str, list[str]] = {}
    for name in sources:
        path = log_dir / f"{name}.log"
        if not path.exists():
            logs[name] = []
            continue
        try:
            lines = path.read_text(encoding="utf-8", errors="replace").splitlines()
        except OSError:
            lines = []
        logs[name] = lines[-limit:]
    return logs
