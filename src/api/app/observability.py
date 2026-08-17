import json
import logging
from contextvars import ContextVar
from typing import Any

trace_id_context: ContextVar[str] = ContextVar("trace_id", default="unknown")


def log_event(
    logger: logging.Logger,
    level: int,
    event: str,
    **fields: Any,
) -> None:
    logger.log(
        level,
        json.dumps(
            {
                "event": event,
                "traceId": trace_id_context.get(),
                **fields,
            },
            separators=(",", ":"),
        ),
    )
