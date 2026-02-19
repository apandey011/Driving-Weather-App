from __future__ import annotations

import json
import logging
from contextvars import ContextVar, Token
from datetime import datetime, timezone
from typing import Any, Literal

_request_id_ctx: ContextVar[str] = ContextVar("request_id", default="-")
_logging_configured = False


def get_request_id() -> str:
    return _request_id_ctx.get()


def set_request_id(request_id: str) -> Token[str]:
    return _request_id_ctx.set(request_id)


def reset_request_id(token: Token[str]) -> None:
    _request_id_ctx.reset(token)


class RequestContextFilter(logging.Filter):
    def filter(self, record: logging.LogRecord) -> bool:
        if not hasattr(record, "request_id"):
            record.request_id = get_request_id()
        return True


class JsonLogFormatter(logging.Formatter):
    def format(self, record: logging.LogRecord) -> str:
        payload: dict[str, Any] = {
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "level": record.levelname,
            "logger": record.name,
            "message": record.getMessage(),
            "request_id": getattr(record, "request_id", get_request_id()),
            "path": getattr(record, "path", None),
            "method": getattr(record, "method", None),
            "status_code": getattr(record, "status_code", None),
            "duration_ms": getattr(record, "duration_ms", None),
        }
        if record.exc_info:
            payload["exc_info"] = self.formatException(record.exc_info)
        return json.dumps(payload, default=str)


class PlainLogFormatter(logging.Formatter):
    def format(self, record: logging.LogRecord) -> str:
        timestamp = datetime.now(timezone.utc).isoformat()
        request_id = getattr(record, "request_id", get_request_id())
        path = getattr(record, "path", "-")
        method = getattr(record, "method", "-")
        status_code = getattr(record, "status_code", "-")
        duration_ms = getattr(record, "duration_ms", "-")
        message = record.getMessage()
        base = (
            f"{timestamp} {record.levelname} [{record.name}] request_id={request_id} "
            f"path={path} method={method} status_code={status_code} duration_ms={duration_ms} "
            f"{message}"
        )
        if record.exc_info:
            return f"{base}\n{self.formatException(record.exc_info)}"
        return base


def configure_logging(log_format: Literal["plain", "json"]) -> None:
    global _logging_configured
    if _logging_configured:
        return

    handler = logging.StreamHandler()
    handler.addFilter(RequestContextFilter())
    if log_format == "json":
        handler.setFormatter(JsonLogFormatter())
    else:
        handler.setFormatter(PlainLogFormatter())

    root_logger = logging.getLogger()
    root_logger.handlers.clear()
    root_logger.setLevel(logging.INFO)
    root_logger.addHandler(handler)

    _logging_configured = True
