"""Хелперы: даты, числа, форматирование."""

from __future__ import annotations

from datetime import date, datetime, timedelta, timezone


def to_float(value, default: float = 0.0) -> float:
    try:
        if value is None or value == "":
            return default
        return float(value)
    except (TypeError, ValueError):
        return default


def to_int(value, default: int = 0) -> int:
    try:
        if value is None or value == "":
            return default
        return int(float(value))
    except (TypeError, ValueError):
        return default


def parse_date(value) -> date | None:
    if isinstance(value, date):
        return value
    if not value:
        return None
    text = str(value)[:10]
    try:
        return date.fromisoformat(text)
    except ValueError:
        return None


def daterange(start: date, end: date):
    cursor = start
    while cursor <= end:
        yield cursor
        cursor += timedelta(days=1)


def utc_now() -> datetime:
    return datetime.now(timezone.utc)


def utc_today() -> date:
    """Текущая дата в UTC: Ozon считает аналитику в UTC, не в локальной зоне."""
    return utc_now().date()


def utc_now_iso() -> str:
    return utc_now().strftime("%Y-%m-%d %H:%M:%S UTC")


def iso_day(value: date | datetime) -> str:
    return value.strftime("%Y-%m-%d")


def api_datetime(value: date | datetime, *, end_of_day: bool = False) -> str:
    """Формат даты для финансовых методов Ozon: 2024-01-31T23:59:59.000Z."""
    time_part = "23:59:59.999" if end_of_day else "00:00:00.000"
    return f"{value.strftime('%Y-%m-%d')}T{time_part}Z"


def safe_div(numerator: float, denominator: float) -> float:
    return numerator / denominator if denominator else 0.0


def fmt_int(value) -> str:
    return f"{int(round(to_float(value))):,}".replace(",", " ")


def fmt_money(value, currency: str = "₽") -> str:
    return f"{fmt_int(value)} {currency}"


def fmt_pct(value, digits: int = 1) -> str:
    return f"{to_float(value) * 100:.{digits}f}%"


def fmt_days(value) -> str:
    v = to_float(value)
    return "—" if v <= 0 else f"{v:.0f} дн."


def fmt_delta(current, previous) -> str:
    cur, prev = to_float(current), to_float(previous)
    if prev <= 0:
        return ""
    diff = (cur - prev) / prev
    sign = "+" if diff > 0 else ""
    return f"{sign}{diff * 100:.1f}%"
