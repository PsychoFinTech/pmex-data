#!/usr/bin/env python3
"""
stitch_expirations.py — Convert expiry-based futures into continuous contracts.

PMEX trades most commodities as monthly expirations (NGAS1K-JA21, NGAS1K-FE21, etc).
This tool stitches them chronologically to create "perpetual" contracts for backtesting.

Usage:
    python3 stitch_expirations.py --symbol NGAS1K --input pmex_2020_2021.csv -o NGAS1K_continuous.csv
    python3 stitch_expirations.py --symbol CRUDE10 --input pmex_2020_2021.csv -o CRUDE10_continuous.csv
"""

import csv
import argparse
from datetime import datetime
from collections import defaultdict
import sys

# Month code to month number: JA=1, FE=2, MA=3, ..., DE=12
MONTH_CODE = {
    'JA': 1, 'FE': 2, 'MA': 3, 'AP': 4, 'MY': 5, 'JU': 6,
    'JY': 7, 'AU': 8, 'SE': 9, 'OC': 10, 'NO': 11, 'DE': 12
}


def parse_expiry_code(code):
    """Parse expiry code (e.g., 'JA21' → (2021, 1, 31))"""
    if len(code) < 4:
        return None
    month_str = code[:2]
    year_str = code[2:4]

    if month_str not in MONTH_CODE:
        return None

    month = MONTH_CODE[month_str]
    year = 2000 + int(year_str)

    # Get last day of month (crude/gas expiry)
    if month == 12:
        last_day = 31
    else:
        # Simple approximation; doesn't account for all edge cases
        import calendar
        last_day = calendar.monthrange(year, month)[1]

    return (year, month, last_day)


def read_expiry_contracts(csv_file, base_symbol):
    """Read all expiry contracts for a symbol, organized by expiry date."""
    contracts = defaultdict(lambda: {"bars": [], "expiry": None})

    with open(csv_file, 'r') as f:
        reader = csv.DictReader(f)
        for row in reader:
            symbol = row['Symbol']

            # Match base symbol + expiry code
            if not symbol.startswith(base_symbol + '-'):
                continue

            expiry_code = symbol.split('-')[1]
            expiry_date = parse_expiry_code(expiry_code)

            if not expiry_date:
                continue

            contracts[expiry_code]['expiry'] = expiry_date
            contracts[expiry_code]['bars'].append(row)

    return contracts


def stitch_contracts(contracts, adjustment_method='forward-fill'):
    """
    Stitch multiple expiry contracts into one continuous series.

    adjustment_method:
      'forward-fill': No adjustment (creates jumps on roll)
      'back-adjust': Subtract roll spread from entire previous contract
      'panama': Multiply by ratio (most realistic)
    """
    if not contracts:
        return []

    # Sort by expiry date
    sorted_codes = sorted(
        contracts.keys(),
        key=lambda code: contracts[code]['expiry']
    )

    continuous_rows = []
    prev_close = None
    adjustment_cumulative = 0  # For back-adjustment

    for code in sorted_codes:
        contract = contracts[code]
        bars = contract['bars']

        if not bars:
            continue

        # Sort bars by date
        bars_sorted = sorted(bars, key=lambda r: r['TradingDate'])

        for i, row in enumerate(bars_sorted):
            new_row = row.copy()

            # Apply adjustment if not the first contract
            if prev_close is not None and i == 0:
                # First bar of new contract: calculate roll adjustment
                try:
                    curr_open = float(row['Close']) if row['Close'] else 0
                    if curr_open > 0:
                        roll_spread = prev_close - curr_open

                        if adjustment_method == 'back-adjust':
                            adjustment_cumulative += roll_spread
                        elif adjustment_method == 'panama':
                            # Multiply previous cumulative by ratio
                            if prev_close > 0:
                                ratio = (prev_close - roll_spread) / prev_close
                                adjustment_cumulative *= ratio
                except ValueError:
                    pass

            # Apply cumulative adjustment to all OHLC
            if adjustment_cumulative != 0:
                for col in ['Open', 'High', 'Low', 'Close']:
                    try:
                        val = float(new_row[col]) if new_row[col] else 0
                        new_row[col] = str(val + adjustment_cumulative)
                    except ValueError:
                        pass

            continuous_rows.append(new_row)

            # Track last close for next contract
            try:
                prev_close = float(row['Close']) if row['Close'] else None
            except ValueError:
                prev_close = None

    return continuous_rows


def write_continuous_csv(rows, output_file):
    """Write stitched data to CSV."""
    if not rows:
        print(f"No data to write to {output_file}", file=sys.stderr)
        return

    fieldnames = rows[0].keys()
    with open(output_file, 'w', newline='', encoding='utf-8') as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(rows)


def main(argv=None):
    p = argparse.ArgumentParser(
        description="Stitch expiry-based futures into continuous contracts."
    )
    p.add_argument('--symbol', required=True, help='Base symbol (e.g., NGAS1K, CRUDE10)')
    p.add_argument('--input', required=True, help='Input CSV file')
    p.add_argument('-o', '--output', required=True, help='Output CSV file')
    p.add_argument('--method', choices=['forward-fill', 'back-adjust', 'panama'],
                   default='forward-fill', help='Adjustment method (default: forward-fill)')

    args = p.parse_args(argv)

    print(f"Reading {args.symbol} expirations from {args.input}...", file=sys.stderr)
    contracts = read_expiry_contracts(args.input, args.symbol)

    if not contracts:
        print(f"No expiry contracts found for {args.symbol}", file=sys.stderr)
        return 1

    print(f"Found {len(contracts)} expiry variants", file=sys.stderr)
    for code in sorted(contracts.keys()):
        expiry = contracts[code]['expiry']
        bars_count = len(contracts[code]['bars'])
        print(f"  {args.symbol}-{code:6s} → {expiry[0]}-{expiry[1]:02d}-{expiry[2]:02d} ({bars_count} bars)",
              file=sys.stderr)

    print(f"Stitching with '{args.method}' adjustment...", file=sys.stderr)
    continuous = stitch_contracts(contracts, adjustment_method=args.method)

    # Sort by date
    continuous.sort(key=lambda r: r['TradingDate'])

    write_continuous_csv(continuous, args.output)
    print(f"Wrote {len(continuous)} continuous bars to {args.output}", file=sys.stderr)

    # Summary
    dates = [r['TradingDate'] for r in continuous if r['TradingDate']]
    if dates:
        print(f"Date range: {min(dates)} to {max(dates)}", file=sys.stderr)


if __name__ == '__main__':
    main()
