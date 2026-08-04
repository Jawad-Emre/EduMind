"""Central logging setup for EduMind.

Replaces SQLAlchemy's verbose per-query echo with concise, human-friendly
messages emitted by the routes themselves (login, signup, chat, uploads,
errors, rate limits). Call setup_logging() once at startup.
"""
import logging
import sys


def setup_logging(level: int = logging.INFO) -> None:
    logging.basicConfig(
        level=level,
        format="%(asctime)s | %(levelname)-7s | %(name)-22s | %(message)s",
        datefmt="%H:%M:%S",
        stream=sys.stdout,
        force=True,  # override uvicorn's default handlers so our format wins
    )

    # The main source of the long, messy logs: silence the query-by-query SQL
    # echo. WARNING still surfaces real DB problems.
    logging.getLogger("sqlalchemy.engine").setLevel(logging.WARNING)
    logging.getLogger("sqlalchemy.pool").setLevel(logging.WARNING)

    # Trim other chatty third-party loggers.
    logging.getLogger("httpx").setLevel(logging.WARNING)
    logging.getLogger("hpack").setLevel(logging.WARNING)


def get_logger(name: str) -> logging.Logger:
    """Convenience accessor so routes can do `logger = get_logger(__name__)`."""
    return logging.getLogger(name)
