#!/usr/bin/env python3
"""Stitch expiry-dated PMEX contracts into a continuous front-month series.

For each base symbol we take all its dated contracts (e.g. ``CRUDE10-JA24``,
``CRUDE10-FE24``, ...) and build a single continuous series:

1. **Chronological ordering.** Contracts are ordered by their real expiry date
   (parsed from the code), never by the raw string — ``AU22`` sorts before
   ``DE23`` correctly.
2. **Strict contract validation.** Only genuine ``<MM><YY>`` expiries are
   included; intraday (``-THU``) and in-delivery (``-DE23ID``) suffixes and bare
   symbols are ignored.
3. **Front-month roll.** On each trading date the active contract is the nearest
   expiry that has not yet rolled (roll happens the day before the delivery
   month). This yields exactly one bar per date with no duplicates.
4. **Back-adjustment.** Roll gaps are removed so returns are continuous. The
   newest contract is left unadjusted, so the most recent price is the real
   market price; history is shifted to match (standard convention).

Adjustment methods:

* ``back-adjust`` (default) — additive Panama: subtract the cumulative roll gap.
* ``ratio`` — proportional: multiply by the cumulative roll ratio.
* ``none`` — raw front-month splice with no gap removal (for reference/plotting).

Pre-2020 bare history
---------------------

Before ~26 Oct 2020 PMEX published contracts without expiry codes (bare
``GOLD``, ``CRUDE10``, ...), one bar per symbol per date — effectively an
already-continuous front-month series with no visible rolls. With ``extend_bare``
these bars are spliced onto the *old* end of the dated series. Because the bare
and dated blocks never share a trading date (the seam is a clean adjacent-day
boundary), the seam gap is measured from the last bare bar to the first dated
bar and removed, so returns stay continuous across the 2020 relabelling.
"""

from __future__ import annotations

import argparse
import csv
import logging
import sys
from collections import defaultdict
from datetime import date, datetime

from pmex.expiry import roll_date, split_symbol

log = logging.getLogger("pmex.perpetual")

METHODS = ("back-adjust", "ratio", "none")


def parse_date(date_str: str) -> date:
    """Parse a trading date in ISO or dd/mm/yyyy form."""
    for fmt in ("%Y-%m-%d", "%d/%m/%Y"):
        try:
            return datetime.strptime(date_str, fmt).date()
        except ValueError:
            continue
    raise ValueError(f"cannot parse date: {date_str!r}")


def read_contracts(csv_file, base_symbol):
    """Read every dated contract for ``base_symbol``.

    Returns ``{expiry_date: {trading_date: bar}}`` where each bar is a dict with
    ``open/high/low/close/volume``. Rows with a non-expiry suffix, the wrong
    base, or non-positive prices are skipped.
    """
    contracts: dict[date, dict[date, dict]] = defaultdict(dict)

    with open(csv_file, newline="") as f:
        for row in csv.DictReader(f):
            parsed = split_symbol(row["Symbol"])
            if parsed is None:
                continue
            sym_base, expiry = parsed
            if sym_base != base_symbol:
                continue
            try:
                d = parse_date(row["TradingDate"])
                o = float(row["Open"]) if row["Open"] else None
                h = float(row["High"]) if row["High"] else None
                low = float(row["Low"]) if row["Low"] else None
                c = float(row["Close"]) if row["Close"] else None
                vol = float(row["TradedVolume"]) if row["TradedVolume"] else 0.0
            except (ValueError, KeyError):
                continue
            if any(x is None or x <= 0 for x in (o, h, low, c)):
                continue
            contracts[expiry][d] = {
                "open": o, "high": h, "low": low, "close": c, "volume": vol,
            }
    return contracts


def read_bare_series(csv_file, base_symbol):
    """Read the pre-labelling *bare* bars for ``base_symbol``.

    A bare bar is a row whose Symbol is exactly ``base_symbol`` with no expiry
    code or other suffix (e.g. ``CRUDE10``, never ``CRUDE10-DE20`` or
    ``CRUDE10-THU``). Returns ``{trading_date: bar}``; non-positive prices are
    skipped. Pre-2020 PMEX lists exactly one such bar per date.
    """
    target = base_symbol.upper()
    series: dict[date, dict] = {}
    with open(csv_file, newline="") as f:
        for row in csv.DictReader(f):
            if row["Symbol"].strip().upper() != target:
                continue
            try:
                d = parse_date(row["TradingDate"])
                o = float(row["Open"]) if row["Open"] else None
                h = float(row["High"]) if row["High"] else None
                low = float(row["Low"]) if row["Low"] else None
                c = float(row["Close"]) if row["Close"] else None
                vol = float(row["TradedVolume"]) if row["TradedVolume"] else 0.0
            except (ValueError, KeyError):
                continue
            if any(x is None or x <= 0 for x in (o, h, low, c)):
                continue
            series[d] = {"open": o, "high": h, "low": low, "close": c, "volume": vol}
    return series


def _front_series(contracts):
    """Select one front-month bar per trading date.

    On each date the front contract is the nearest expiry that still has a bar
    that day and whose roll date has not passed. Past every roll date (the tail
    of the last contract) the latest expiry is used.
    """
    all_dates = set()
    for by_date in contracts.values():
        all_dates.update(by_date)

    series = []  # (trading_date, expiry, bar)
    for d in sorted(all_dates):
        present = [e for e, by_date in contracts.items() if d in by_date]
        if not present:
            continue
        not_rolled = [e for e in present if roll_date(e) >= d]
        chosen = min(not_rolled) if not_rolled else max(present)
        series.append((d, chosen, contracts[chosen][d]))
    return series


def _segments(series):
    """Group the front series into consecutive runs of the same expiry."""
    segments = []
    for d, expiry, bar in series:
        if not segments or segments[-1][0] != expiry:
            segments.append((expiry, []))
        segments[-1][1].append((d, bar))
    return segments


def _roll_gap(older_expiry, newer_expiry, contracts, boundary_date):
    """Return ``(additive_gap, ratio)`` between two contracts at the roll.

    Both are evaluated on a shared trading date — the latest common date on or
    before ``boundary_date``, else the earliest common date. ``gap`` is
    ``newer.close - older.close`` and ``ratio`` is ``newer.close / older.close``.
    Falls back to a no-op (0.0, 1.0) if the contracts never overlap.
    """
    older = contracts[older_expiry]
    newer = contracts[newer_expiry]
    common = sorted(set(older) & set(newer))
    if not common:
        return 0.0, 1.0
    on_or_before = [d for d in common if d <= boundary_date]
    ref = on_or_before[-1] if on_or_before else common[0]
    older_close = older[ref]["close"]
    newer_close = newer[ref]["close"]
    if older_close <= 0:
        return 0.0, 1.0
    return newer_close - older_close, newer_close / older_close


def _splice_bare(out, bare, method):
    """Prepend adjusted pre-2020 bare bars onto the dated series ``out``.

    ``out`` is the already-adjusted dated series (ascending). Only bare bars
    strictly before the first dated date are used. The seam gap is taken between
    the last bare bar and the first (adjusted) dated bar and removed, so the
    splice is continuous. Returns the combined ascending series.
    """
    if not out or not bare:
        return out
    boundary = out[0]["date"]
    before = {d: b for d, b in bare.items() if d < boundary}
    if not before:
        return out

    raw_last = before[max(before)]["close"]
    anchor = out[0]["close"]  # first dated bar, already adjusted
    if method == "back-adjust":
        offset, factor = anchor - raw_last, 1.0
    elif method == "ratio":
        if raw_last <= 0:
            return out
        offset, factor = 0.0, anchor / raw_last
    else:  # none — raw splice
        offset, factor = 0.0, 1.0

    bare_bars = []
    for d in sorted(before):
        bar = before[d]
        if method == "ratio":
            adj = {k: bar[k] * factor for k in ("open", "high", "low", "close")}
        else:
            adj = {k: bar[k] + offset for k in ("open", "high", "low", "close")}
        adj["date"] = d
        adj["volume"] = bar["volume"]
        adj["contract"] = None  # bare / pre-labelling
        bare_bars.append(adj)
    return bare_bars + out


def stitch_perpetual(contracts, method="back-adjust", bare=None):
    """Build a continuous, back-adjusted front-month series.

    Returns a list of bars (dicts with ``date, open, high, low, close, volume,
    contract``) in ascending date order, one per trading date. When ``bare`` (a
    ``{date: bar}`` map from :func:`read_bare_series`) is given, the pre-2020
    unlabelled history is spliced onto the old end (see module docstring).
    """
    if method not in METHODS:
        raise ValueError(f"unknown method {method!r}; choose from {METHODS}")
    if not contracts:
        return []

    series = _front_series(contracts)
    segments = _segments(series)

    # Walk segments newest -> oldest, accumulating the adjustment that keeps the
    # newest contract's prices unchanged.
    offset = 0.0   # additive
    factor = 1.0   # multiplicative
    adjustments = [None] * len(segments)
    for i in range(len(segments) - 1, -1, -1):
        adjustments[i] = (offset, factor)
        if i > 0:
            older_expiry = segments[i - 1][0]
            newer_expiry = segments[i][0]
            boundary_date = segments[i - 1][1][-1][0]
            gap, ratio = _roll_gap(older_expiry, newer_expiry, contracts, boundary_date)
            offset += gap
            factor *= ratio

    out = []
    for (expiry, bars), (seg_offset, seg_factor) in zip(segments, adjustments):
        for d, bar in bars:
            if method == "back-adjust":
                adj = {k: bar[k] + seg_offset for k in ("open", "high", "low", "close")}
            elif method == "ratio":
                adj = {k: bar[k] * seg_factor for k in ("open", "high", "low", "close")}
            else:  # none
                adj = {k: bar[k] for k in ("open", "high", "low", "close")}
            adj["date"] = d
            adj["volume"] = bar["volume"]
            adj["contract"] = f"{expiry.year % 100:02d}-{expiry.month:02d}"
            out.append(adj)

    if bare:
        out = _splice_bare(out, bare, method)
    return out


def write_perpetuals(perpetuals, output_file):
    fieldnames = ["Symbol", "TradingDate", "Open", "High", "Low", "Close",
                  "Volume", "FrontContract"]
    with open(output_file, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        for base_symbol in sorted(perpetuals):
            for bar in perpetuals[base_symbol]:
                contract = bar["contract"]
                front = base_symbol if contract is None else f"{base_symbol}-{contract}"
                writer.writerow({
                    "Symbol": base_symbol,
                    "TradingDate": bar["date"].strftime("%Y-%m-%d"),
                    "Open": f"{bar['open']:.4f}",
                    "High": f"{bar['high']:.4f}",
                    "Low": f"{bar['low']:.4f}",
                    "Close": f"{bar['close']:.4f}",
                    "Volume": f"{bar['volume']:.0f}",
                    "FrontContract": front,
                })


def discover_symbols(csv_file):
    """Return the sorted set of base symbols that have at least one dated contract."""
    bases = set()
    with open(csv_file, newline="") as f:
        for row in csv.DictReader(f):
            parsed = split_symbol(row["Symbol"])
            if parsed is not None:
                bases.add(parsed[0])
    return sorted(bases)


def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(
        prog="pmex-perpetual",
        description="Stitch expiry-dated PMEX contracts into continuous "
                    "front-month, back-adjusted series.",
    )
    p.add_argument("input_csv", help="input PMEX OHLC CSV")
    p.add_argument("--symbols", default=None,
                   help="comma-separated base symbols (default: all discovered)")
    p.add_argument("--method", choices=METHODS, default="back-adjust",
                   help="roll-gap adjustment (default: back-adjust)")
    p.add_argument("--extend-bare", action="store_true",
                   help="splice the pre-2020 unlabelled (bare) history onto the "
                        "old end of each series, seam-adjusted for continuity")
    p.add_argument("-o", "--output", default="pmex_perpetuals.csv", help="output file")
    p.add_argument("--limit", type=int, default=None, help="process at most N symbols")
    p.add_argument("--quiet", action="store_true", help="suppress progress output")
    return p


def main(argv=None):
    args = build_parser().parse_args(argv)
    logging.basicConfig(
        level=logging.WARNING if args.quiet else logging.INFO,
        format="%(message)s",
        stream=sys.stderr,
    )

    if args.symbols:
        symbols = [s.strip() for s in args.symbols.split(",") if s.strip()]
    else:
        symbols = discover_symbols(args.input_csv)
    if args.limit:
        symbols = symbols[:args.limit]

    log.info("Processing %d symbols (method=%s)...", len(symbols), args.method)
    perpetuals = {}
    for i, base in enumerate(symbols, 1):
        contracts = read_contracts(args.input_csv, base)
        if not contracts:
            log.info("[%d/%d] %s: no dated contracts", i, len(symbols), base)
            continue
        bare = read_bare_series(args.input_csv, base) if args.extend_bare else None
        stitched = stitch_perpetual(contracts, method=args.method, bare=bare)
        if stitched:
            perpetuals[base] = stitched
            n_bare = sum(1 for b in stitched if b["contract"] is None)
            extra = f", +{n_bare} bare" if n_bare else ""
            log.info("[%d/%d] %s: %d bars (%d expiries%s)",
                     i, len(symbols), base, len(stitched), len(contracts), extra)

    write_perpetuals(perpetuals, args.output)
    total = sum(len(b) for b in perpetuals.values())
    log.info("Done: %d bars across %d symbols -> %s",
             total, len(perpetuals), args.output)


if __name__ == "__main__":
    main()
