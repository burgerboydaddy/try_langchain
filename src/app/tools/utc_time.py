from datetime import datetime, timezone

from langchain_core.tools import tool


@tool
def utc_time(_: str = "") -> str:
    """Return current UTC time in ISO-8601 format."""
    return datetime.now(tz=timezone.utc).isoformat()
