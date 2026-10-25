"""Small, local-only rotating log setup for the IntelliGraph demo."""

from __future__ import annotations

import logging
import json
from datetime import datetime, timezone
from logging.handlers import RotatingFileHandler
from pathlib import Path
from typing import Any


LOG_FORMAT = "%(asctime)s | %(levelname)s | %(name)s | %(message)s"
LOG_MAX_BYTES = 2 * 1024 * 1024
LOG_BACKUP_COUNT = 3
ACTIVITY_LOG_FILENAME = "activity.jsonl"


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
        if path.exists():
            try:
                lines = path.read_text(encoding="utf-8", errors="replace").splitlines()
            except OSError:
                lines = []
        else:
            lines = []
        if not lines:
            # Tests, temporary workspaces, and a log directory moved while the
            # server is running may have structured activity but no raw file
            # handler attached to the new location. Keep the legacy response
            # useful by projecting those events into readable log lines.
            lines = [
                f"{event.get('timestamp', '')} | INFO | intelligraph.{name} | "
                f"{event.get('action', 'activity')} | {event.get('message', '')}"
                for event in reversed(read_activity_events(log_dir, name, limit))
            ]
        logs[name] = lines[-limit:]
    return logs


def record_activity(
    log_dir: Path,
    *,
    source: str,
    action: str,
    message: str,
    details: dict[str, Any] | None = None,
    level: str = "info",
) -> None:
    """Persist a safe, structured activity event for the user-facing log viewer."""

    event = {
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "source": source,
        "action": action,
        "message": message.replace("\r", " ").replace("\n", " ")[:2000],
        "details": details or {},
    }
    log_dir.mkdir(parents=True, exist_ok=True)
    path = log_dir / ACTIVITY_LOG_FILENAME
    with path.open("a", encoding="utf-8") as handle:
        handle.write(json.dumps(event, ensure_ascii=False, default=str) + "\n")

    activity_logger = logging.getLogger(f"intelligraph.{source}")
    safe_level = level.lower().strip()
    if safe_level not in {"debug", "info", "warning", "error", "critical"}:
        safe_level = "info"
    getattr(activity_logger, safe_level)("%s | %s", action, event["message"])


def read_activity_events(log_dir: Path, source: str, limit: int = 250) -> list[dict[str, Any]]:
    """Read newest structured activity events, ignoring malformed lines safely."""

    path = log_dir / ACTIVITY_LOG_FILENAME
    if not path.exists():
        return []
    try:
        lines = path.read_text(encoding="utf-8", errors="replace").splitlines()
    except OSError:
        return []

    events: list[dict[str, Any]] = []
    for line in reversed(lines):
        try:
            event = json.loads(line)
        except json.JSONDecodeError:
            continue
        if not isinstance(event, dict):
            continue
        if source != "all" and event.get("source") != source:
            continue
        events.append(event)
        if len(events) >= limit:
            break
    return events
