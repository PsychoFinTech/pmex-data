#!/usr/bin/env python3
"""
create_perpetuals.py — Convert expiry-based contracts into continuous perpetuals.

Takes PMEX OHLC data and stitches multiple expiration months for each base symbol
into a single continuous contract using Panama/Ratio adjustment method.

Usage:
    python3 create_perpetuals.py pmex_2020_2023_top15.csv --symbols "CRUDE10,GOLD,KIBOR3M"
"""

import csv
import sys
from collections import defaultdict
from datetime import datetime
import argparse


def parse_date(date_str):
    """Parse trading date from CSV format."""
    for fmt in ['%Y-%m-%d', '%d/%m/%Y']:
        try:
            return datetime.strptime(date_str, fmt).date()
        except ValueError:
            pass
    raise ValueError(f"Cannot parse date: {date_str}")


def expiry_to_date(expiry_code):
    """
    Parse expiry code (e.g., 'DE23' -> December 2023, 'JA24' -> January 2024).
    Returns (year, month) tuple.
    """
    month_map = {
        'JA': 1, 'FE': 2, 'MA': 3, 'AP': 4, 'MY': 5, 'JU': 6,
        'JY': 7, 'AU': 8, 'SE': 9, 'OC': 10, 'NO': 11, 'DE': 12
    }

    if len(expiry_code) < 4:
        return None

    month_code = expiry_code[:2]
    year_code = expiry_code[2:]

    if month_code not in month_map:
        return None

    try:
        year = 2000 + int(year_code)
        month = month_map[month_code]
        return (year, month)
    except ValueError:
        return None


def read_contracts(csv_file, base_symbol):
    """
    Read all contracts for a base symbol from the CSV file.
    Returns dict: {expiry_date: [(date, open, high, low, close), ...]}
    """
    contracts = defaultdict(lambda: [])

    with open(csv_file, 'r') as f:
        reader = csv.DictReader(f)
        for row in reader:
            symbol = row['Symbol']

            # Extract base and expiry
            parts = symbol.split('-')
            if len(parts) != 2:
                continue

            sym_base, expiry = parts
            if sym_base != base_symbol:
                continue

            # Parse date
            try:
                date = parse_date(row['TradingDate'])
            except ValueError:
                continue

            # Parse OHLC
            try:
                open_price = float(row['Open']) if row['Open'] else None
                high = float(row['High']) if row['High'] else None
                low = float(row['Low']) if row['Low'] else None
                close = float(row['Close']) if row['Close'] else None
                volume = float(row['TradedVolume']) if row['TradedVolume'] else 0

                if any(x is None or x <= 0 for x in [open_price, high, low, close]):
                    continue

                contracts[expiry].append({
                    'date': date,
                    'open': open_price,
                    'high': high,
                    'low': low,
                    'close': close,
                    'volume': volume,
                })
            except (ValueError, KeyError):
                continue

    # Sort each contract by date
    for expiry in contracts:
        contracts[expiry].sort(key=lambda x: x['date'])

    return contracts


def stitch_perpetual(contracts, method='panama'):
    """
    Stitch multiple expiry contracts into one continuous contract.

    Methods:
    - forward-fill: Use previous contract's last close (creates gaps)
    - back-adjust: Subtract roll spread from entire previous contract
    - panama: Multiply by ratio (most realistic)
    """
    if not contracts:
        return []

    # Sort expirations by date (earliest first)
    sorted_expiries = sorted(contracts.keys())

    perpetual = []
    adjustment_factor = 1.0
    prev_close = None

    for expiry in sorted_expiries:
        bars = contracts[expiry]
        if not bars:
            continue

        for bar in bars:
            adjusted = bar.copy()

            if method == 'panama':
                # Ratio adjustment: multiply all prices by factor
                if prev_close is not None and bar['close'] > 0:
                    # Calculate roll ratio at rollover point
                    ratio = prev_close / bar['open']
                    adjustment_factor *= ratio

                adjusted['open'] *= adjustment_factor
                adjusted['high'] *= adjustment_factor
                adjusted['low'] *= adjustment_factor
                adjusted['close'] *= adjustment_factor

            elif method == 'back-adjust':
                # Back-adjust: shift previous contract down by roll spread
                if prev_close is not None:
                    spread = prev_close - bar['open']
                    adjusted['open'] += spread
                    adjusted['high'] += spread
                    adjusted['low'] += spread
                    adjusted['close'] += spread

            # forward-fill method has no adjustment

            adjusted['expiry'] = expiry
            perpetual.append(adjusted)
            prev_close = bar['close']

    return perpetual


def write_perpetuals(perpetuals_dict, output_file):
    """Write stitched perpetuals to CSV file."""
    with open(output_file, 'w', newline='', encoding='utf-8') as f:
        writer = None

        for base_symbol in sorted(perpetuals_dict.keys()):
            bars = perpetuals_dict[base_symbol]
            if not bars:
                continue

            if writer is None:
                fieldnames = ['Symbol', 'TradingDate', 'Open', 'High', 'Low', 'Close', 'Volume', 'Expiry']
                writer = csv.DictWriter(f, fieldnames=fieldnames)
                writer.writeheader()

            for bar in bars:
                row = {
                    'Symbol': base_symbol,
                    'TradingDate': bar['date'].strftime('%Y-%m-%d'),
                    'Open': f"{bar['open']:.2f}",
                    'High': f"{bar['high']:.2f}",
                    'Low': f"{bar['low']:.2f}",
                    'Close': f"{bar['close']:.2f}",
                    'Volume': f"{bar['volume']:.0f}",
                    'Expiry': bar.get('expiry', ''),
                }
                writer.writerow(row)


def main():
    p = argparse.ArgumentParser(
        description="Stitch expiry-based PMEX contracts into continuous perpetuals"
    )
    p.add_argument("input_csv", help="Input PMEX CSV file")
    p.add_argument("--symbols", default=None, help="Comma-separated symbols to process")
    p.add_argument("--method", choices=['forward-fill', 'back-adjust', 'panama'],
                   default='panama', help="Stitching method")
    p.add_argument("-o", "--output", default="pmex_perpetuals.csv", help="Output file")
    p.add_argument("--limit", type=int, default=None, help="Limit to N symbols")

    args = p.parse_args()

    # Determine which symbols to process
    if args.symbols:
        symbols_to_process = [s.strip() for s in args.symbols.split(',')]
    else:
        # Extract all unique base symbols from the input file
        symbols_to_process = set()
        with open(args.input_csv, 'r') as f:
            reader = csv.DictReader(f)
            for row in reader:
                symbol = row['Symbol']
                if '-' in symbol:
                    base = symbol.split('-')[0]
                    symbols_to_process.add(base)
        symbols_to_process = sorted(symbols_to_process)

    if args.limit:
        symbols_to_process = symbols_to_process[:args.limit]

    print(f"Processing {len(symbols_to_process)} symbols...", file=sys.stderr)

    perpetuals = {}

    for i, base_symbol in enumerate(symbols_to_process, 1):
        print(f"[{i}/{len(symbols_to_process)}] {base_symbol}...", end=' ',
              file=sys.stderr, flush=True)

        contracts = read_contracts(args.input_csv, base_symbol)
        if not contracts:
            print("NO DATA", file=sys.stderr)
            continue

        stitched = stitch_perpetual(contracts, method=args.method)
        if stitched:
            perpetuals[base_symbol] = stitched
            print(f"{len(stitched)} bars ({len(contracts)} expirations)", file=sys.stderr)
        else:
            print("FAILED", file=sys.stderr)

    print(f"\nWriting {len(perpetuals)} perpetuals to {args.output}...", file=sys.stderr)
    write_perpetuals(perpetuals, args.output)

    # Summary statistics
    total_bars = sum(len(bars) for bars in perpetuals.values())
    print(f"\nDone: {total_bars} bars across {len(perpetuals)} symbols -> {args.output}",
          file=sys.stderr)


if __name__ == '__main__':
    main()
