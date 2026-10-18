"""Calendar dates as days since 1970-01-01 UTC."""

from datetime import date, datetime

EPOCH = date(1970, 1, 1)


def to_day(value: date) -> int:
    return (value - EPOCH).days


def parse_date(value: str | None) -> date | None:
    if not value or not str(value).strip():
        return None
    text = str(value).strip()
    for fmt in ("%Y-%m-%d", "%Y%m%d", "%b %d, %Y", "%B %d, %Y"):
        try:
            return datetime.strptime(text, fmt).date()
        except ValueError:
            continue
    return None


def to_d(value: str | None) -> int | None:
    parsed = parse_date(value)
    if parsed is None:
        return None
    return to_day(parsed)


def to_iso(value: str | None) -> str | None:
    parsed = parse_date(value)
    if parsed is None:
        return None
    return parsed.isoformat()
