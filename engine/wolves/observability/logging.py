from __future__ import annotations

import logging


def configure_cli_logging() -> None:
    """Standard CLI logging setup. httpx request lines are suppressed because
    The Odds API key travels as a query parameter and must never reach logs."""
    logging.basicConfig(level=logging.INFO, format="%(levelname)s %(name)s: %(message)s")
    logging.getLogger("httpx").setLevel(logging.WARNING)
