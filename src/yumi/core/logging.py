"""
Structured logging configuration for Yumi.
Uses structlog as the frontend and stdlib logging as the backend,
so all log output (including uvicorn and LangChain) goes through
a single unified pipeline.
Usage:
    from yumi.core.logging import get_logger
    log = get_logger(__name__)
    log.info("model_loaded", model="silero_vad")
    log.warning("audio_too_short", duration_sec=0.3, minimum=0.7)
    log.error("tts_failed", provider="ElevenLabs", error=str(e))
"""
from __future__ import annotations
import logging
import os
import sys
import structlog
def configure_logging() -> None:
    """Configure structlog + stdlib logging. Call once at process startup."""
    log_level_name = os.environ.get("YUMI_LOG_LEVEL", "INFO").upper()
    log_level = getattr(logging, log_level_name, logging.INFO)
    # ── stdlib root logger ────────────────────────────────────────────────────
    # Route stdlib loggers (uvicorn, httpx, LangChain, etc.) through structlog.
    logging.basicConfig(
        format="%(message)s",
        stream=sys.stdout,
        level=log_level,
    )
    # Silence noisy third-party loggers at WARNING unless the user wants DEBUG
    for noisy in ("httpx", "httpcore", "urllib3", "asyncio", "multipart"):
        logging.getLogger(noisy).setLevel(logging.WARNING)
    # ── structlog shared processors ───────────────────────────────────────────
    shared_processors: list = [
        structlog.contextvars.merge_contextvars,
        structlog.stdlib.add_log_level,
        structlog.stdlib.add_logger_name,
        structlog.processors.TimeStamper(fmt="%H:%M:%S", utc=False),
        structlog.processors.StackInfoRenderer(),
    ]
    structlog.configure(
        processors=shared_processors
        + [
            structlog.stdlib.ProcessorFormatter.wrap_for_formatter,
        ],
        logger_factory=structlog.stdlib.LoggerFactory(),
        wrapper_class=structlog.stdlib.BoundLogger,
        cache_logger_on_first_use=True,
    )
    formatter = structlog.stdlib.ProcessorFormatter(
        processor=structlog.dev.ConsoleRenderer(colors=True),
        foreign_pre_chain=shared_processors,
    )
    handler = logging.StreamHandler(sys.stdout)
    handler.setFormatter(formatter)
    root_logger = logging.getLogger()
    root_logger.handlers.clear()
    root_logger.addHandler(handler)
    root_logger.setLevel(log_level)
def get_logger(name: str) -> structlog.stdlib.BoundLogger:
    """Return a structlog logger bound to *name* (typically ``__name__``)."""
    return structlog.get_logger(name)
