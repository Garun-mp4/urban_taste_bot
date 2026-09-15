import logging


def configure_logging(level: str) -> None:
    """Configure concise process-wide logging without exposing secrets."""

    numeric_level = getattr(logging, level.upper(), logging.INFO)
    logging.basicConfig(
        level=numeric_level,
        format="%(asctime)s | %(levelname)s | %(name)s | %(message)s",
    )
