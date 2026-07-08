#!/usr/bin/env python3
"""Bulk historical OHLC downloader for PMEX (Pakistan Mercantile Exchange).

The public report page https://mportal.pmex.com.pk/mt5bonew/Home/OHLCReport only
lets you query a window of up to (just under) 3 calendar months at a time. This
module splits an arbitrary date range into server-legal windows, fetches each
one from the underlying JSON endpoint, decodes the (deliberately mislabelled)
field names into real OHLC columns, and stitches everything into a single CSV.

Endpoint reverse-engineered from the page's own AJAX call::

    POST /mt5bonew/Home/GetOHLC
    body: txtFromDate=YYYY-MM-DD&txtEndDate=YYYY-MM-DD
    -> JSON array, or the string "Error" if the window spans >= 3 calendar months.

The server's limit is calendar-month based: it rejects a window when
``(to.year*12 + to.month) - (from.year*12 + from.month) >= 3`` i.e. the
day-of-month is irrelevant; only the month boundary count matters. We therefore
chunk into windows aligned to month starts that each cover exactly 3 calendar
months (Jan 1 -> Mar 31, Apr 1 -> Jun 30, ...), the largest the server accepts.

Nothing here is authenticated — it uses exactly the same public request the
website's "Show" button issues.
"""

from __future__ import annotations

import argparse
import csv
import io
import json
import logging
import sys
import time
from datetime import date, datetime, timedelta

import requests

log = logging.getLogger("pmex.downloader")

BASE = "https://mportal.pmex.com.pk"
REPORT_URL = f"{BASE}/mt5bonew/Home/OHLCReport"
DATA_URL = f"{BASE}/mt5bonew/Home/GetOHLC"

# The endpoint reuses JSON keys from an unrelated report, so the names are
# meaningless. This maps each raw key to the real column, decoded from the
# order in which the page's JavaScript renders them into the results table.
FIELD_MAP = [
    ("Post_Date", "TradingDate"),
    ("Trader_Id", "Symbol"),
    ("acc_type", "Open"),
    ("Trans_Id", "High"),
    ("Amount", "Low"),
    ("Status", "Close"),
    ("Verified_Date", "TradedVolume"),
    ("Trader_Name", "SettlementPrice"),
    ("Trans_Date", "FXRate"),
]
COLUMNS = [real for _, real in FIELD_MAP]

USER_AGENT = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/120.0 Safari/537.36"
)

_ONE_DAY = timedelta(days=1)


def month_index(d: date) -> int:
    """Absolute month number, for comparing calendar-month distance."""
    return d.year * 12 + (d.month - 1)


def add_months(d: date, n: int) -> date:
    """First day of the month n months after d's month."""
    idx = month_index(d) + n
    return date(idx // 12, idx % 12 + 1, 1)


def last_day_of_month(d: date) -> date:
    return add_months(d, 1) - _ONE_DAY


def make_windows(start: date, end: date):
    """Yield ``(from, to)`` pairs covering ``[start, end]``.

    Each window stays within the server's limit (span < 3 calendar months).
    Windows are aligned to month ends so every window after the first covers a
    clean 3-calendar-month block, which is the widest the server accepts.
    """
    cur = start
    while cur <= end:
        # Largest legal end: last day of (cur's month + 2).
        win_end = last_day_of_month(add_months(cur, 2))
        if win_end > end:
            win_end = end
        yield cur, win_end
        cur = win_end + _ONE_DAY


def new_session() -> requests.Session:
    s = requests.Session()
    s.headers.update(
        {
            "User-Agent": USER_AGENT,
            "X-Requested-With": "XMLHttpRequest",
            "Referer": REPORT_URL,
            "Origin": BASE,
        }
    )
    # Prime any cookies the site sets on the report page.
    try:
        s.get(REPORT_URL, timeout=30)
    except requests.RequestException:
        pass
    return s


def fetch_window(session: requests.Session, d_from: date, d_to: date, retries: int = 4):
    """Fetch a single window, returning a list of raw JSON records."""
    payload = {"txtFromDate": d_from.isoformat(), "txtEndDate": d_to.isoformat()}
    delay = 2.0
    last_err = None
    for attempt in range(1, retries + 1):
        try:
            r = session.post(DATA_URL, data=payload, timeout=90)
            r.raise_for_status()
            text = r.text.strip()
            if text in ('"Error"', "Error"):
                raise ValueError(
                    f"server rejected window {d_from}..{d_to} as out of range"
                )
            data = r.json()
            if isinstance(data, str):  # e.g. "Error"
                raise ValueError(f"server returned {data!r} for window {d_from}..{d_to}")
            return data
        except (requests.RequestException, json.JSONDecodeError) as e:
            last_err = e
            if attempt < retries:
                log.warning("window %s..%s failed (%s), retry %d/%d in %.0fs",
                            d_from, d_to, e, attempt, retries, delay)
                time.sleep(delay)
                delay *= 2
            else:
                raise
    raise last_err  # pragma: no cover


def parse_trading_date(raw: str) -> str:
    """Post_Date arrives as dd/mm/yyyy; normalise to ISO yyyy-mm-dd for sorting."""
    raw = (raw or "").strip()
    for fmt in ("%d/%m/%Y", "%Y-%m-%d", "%m/%d/%Y"):
        try:
            return datetime.strptime(raw, fmt).date().isoformat()
        except ValueError:
            continue
    return raw  # leave untouched if format is unexpected


def decode_record(raw: dict) -> dict:
    out = {}
    for src, dst in FIELD_MAP:
        val = raw.get(src, "")
        out[dst] = parse_trading_date(val) if dst == "TradingDate" else val
    return out


def _compile_symbol_filter(symbol_filter):
    """Return ``(exact_set, substring)``; at most one is non-None."""
    if not symbol_filter:
        return None, None
    if "|" in symbol_filter:
        return {s.strip().upper() for s in symbol_filter.split("|")}, None
    return None, symbol_filter.upper()


def scrape(start: date, end: date, symbol_filter=None, delay=0.7, verbose=True):
    session = new_session()
    seen = set()
    rows = []
    windows = list(make_windows(start, end))
    symbol_set, substring = _compile_symbol_filter(symbol_filter)

    for i, (d_from, d_to) in enumerate(windows, 1):
        raw = fetch_window(session, d_from, d_to)
        added = 0
        for rec in raw:
            row = decode_record(rec)
            sym = row["Symbol"].upper()
            if symbol_set is not None and sym not in symbol_set:
                continue
            if substring is not None and substring not in sym:
                continue
            key = (row["TradingDate"], row["Symbol"])
            if key in seen:
                continue
            seen.add(key)
            rows.append(row)
            added += 1
        if verbose:
            log.info("[%d/%d] %s .. %s  +%d rows (total %d)",
                     i, len(windows), d_from, d_to, added, len(rows))
        if i < len(windows) and delay:
            time.sleep(delay)
    rows.sort(key=lambda r: (r["TradingDate"], r["Symbol"]))
    return rows


def write_csv(rows, out):
    w = csv.DictWriter(out, fieldnames=COLUMNS)
    w.writeheader()
    w.writerows(rows)


def parse_date_arg(s: str) -> date:
    try:
        return datetime.strptime(s, "%Y-%m-%d").date()
    except ValueError as e:
        raise argparse.ArgumentTypeError(f"date must be YYYY-MM-DD, got {s!r}") from e


def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(
        prog="pmex-download",
        description="Bulk-download historical OHLC futures data from PMEX, "
        "bypassing the 3-month-per-request limit by auto-chunking.",
    )
    p.add_argument("--from", dest="d_from", required=True, type=parse_date_arg,
                   help="start date YYYY-MM-DD")
    p.add_argument("--to", dest="d_to", required=True, type=parse_date_arg,
                   help="end date YYYY-MM-DD")
    p.add_argument("-o", "--output", default="-", help="output file (default: stdout)")
    p.add_argument("--format", choices=["csv", "json"], default="csv",
                   help="output format (default: csv)")
    p.add_argument("--symbol", default=None,
                   help="only keep symbols: pipe-separated exact list "
                        "(e.g. CRUDE10|GOLD) or a single substring (e.g. GOLD). "
                        "Case-insensitive.")
    p.add_argument("--delay", type=float, default=0.7,
                   help="seconds to sleep between requests (default: 0.7)")
    p.add_argument("--quiet", action="store_true", help="suppress progress output")
    return p


def main(argv=None):
    args = build_parser().parse_args(argv)

    logging.basicConfig(
        level=logging.WARNING if args.quiet else logging.INFO,
        format="%(message)s",
        stream=sys.stderr,
    )

    if args.d_from > args.d_to:
        build_parser().error("--from must be on or before --to")

    rows = scrape(
        args.d_from,
        args.d_to,
        symbol_filter=args.symbol,
        delay=args.delay,
        verbose=not args.quiet,
    )

    if args.format == "json":
        text = json.dumps(rows, indent=2)
        if args.output == "-":
            sys.stdout.write(text + "\n")
        else:
            with open(args.output, "w", encoding="utf-8") as f:
                f.write(text)
    else:
        if args.output == "-":
            buf = io.StringIO()
            write_csv(rows, buf)
            sys.stdout.write(buf.getvalue())
        else:
            with open(args.output, "w", newline="", encoding="utf-8") as f:
                write_csv(rows, f)

    dest = "stdout" if args.output == "-" else args.output
    log.info("Done: %d rows -> %s", len(rows), dest)


if __name__ == "__main__":
    main()
