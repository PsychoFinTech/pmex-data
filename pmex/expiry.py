"""Parsing of PMEX contract symbols and expiry codes.

PMEX contract symbols look like ``CRUDE10-FE24`` (base ``CRUDE10``, expiry
February 2024). The expiry code is a two-letter month followed by a two-digit
year. Some symbols carry non-expiry suffixes that must *not* be treated as
expiries when building a continuous series:

* day-of-week intraday products, e.g. ``TOLAGOLD-THU``;
* in-delivery variants, e.g. ``CRUDE10-DE23ID``;
* bare symbols with no suffix at all, e.g. ``CRUDE10``.

:func:`parse_expiry` accepts only a strict ``<MM><YY>`` code and returns the
first day of the expiry month; everything else returns ``None``.
"""

from __future__ import annotations

import re
from datetime import date

# Two-letter month codes used by PMEX expiry symbols.
MONTH_CODES: dict[str, int] = {
    "JA": 1, "FE": 2, "MA": 3, "AP": 4, "MY": 5, "JU": 6,
    "JY": 7, "AU": 8, "SE": 9, "OC": 10, "NO": 11, "DE": 12,
}

# A valid expiry code is exactly two uppercase letters then two digits.
_EXPIRY_RE = re.compile(r"^([A-Z]{2})(\d{2})$")

# Two-digit years are interpreted in this century.
_YEAR_BASE = 2000


def parse_expiry(code: str) -> date | None:
    """Return the first day of the expiry month for ``code``, or ``None``.

    >>> parse_expiry("FE24")
    datetime.date(2024, 2, 1)
    >>> parse_expiry("THU") is None
    True
    >>> parse_expiry("DE23ID") is None
    True
    """
    if code is None:
        return None
    m = _EXPIRY_RE.match(code.strip())
    if not m:
        return None
    month_code, year_code = m.group(1), m.group(2)
    month = MONTH_CODES.get(month_code)
    if month is None:
        return None
    return date(_YEAR_BASE + int(year_code), month, 1)


def split_symbol(symbol: str) -> tuple[str, date] | None:
    """Split ``BASE-EXPIRY`` into ``(base, expiry_date)``.

    Returns ``None`` for bare symbols (no dash) and for symbols whose suffix is
    not a valid expiry code (intraday, in-delivery, etc.), so callers can skip
    anything that is not a genuine dated contract.

    >>> split_symbol("CRUDE10-FE24")
    ('CRUDE10', datetime.date(2024, 2, 1))
    >>> split_symbol("TOLAGOLD-THU") is None
    True
    >>> split_symbol("CRUDE10") is None
    True
    """
    if not symbol or "-" not in symbol:
        return None
    base, _, suffix = symbol.rpartition("-")
    expiry = parse_expiry(suffix)
    if base == "" or expiry is None:
        return None
    return base, expiry


def roll_date(expiry: date) -> date:
    """Last calendar day a contract is front month: the day before its
    delivery month begins.

    ``expiry`` is the first day of the delivery month, so the roll date is
    simply the day before it.

    >>> roll_date(date(2024, 2, 1))
    datetime.date(2024, 1, 31)
    """
    from datetime import timedelta

    return expiry - timedelta(days=1)
