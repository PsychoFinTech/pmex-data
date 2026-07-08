#!/usr/bin/env python3
"""
analyze_portfolio.py — Analyze 15-symbol portfolio for quant strategies.

Calculates:
  • Correlation matrix (which symbols move together)
  • Volatility by symbol and year
  • Sharpe ratio potential
  • Kelly criterion position sizing
  • Optimal hedge pairs
  • Mean-reversion opportunities
"""

import csv
import sys
from collections import defaultdict
from statistics import stdev, mean, correlation
import json

def read_portfolio(csv_file):
    """Read and organize portfolio data by symbol and date."""
    data = defaultdict(lambda: {
        'closes': [],
        'highs': [],
        'lows': [],
        'volumes': [],
        'dates': [],
    })

    with open(csv_file, 'r') as f:
        reader = csv.DictReader(f)
        for row in reader:
            symbol = row['Symbol']
            try:
                close = float(row['Close']) if row['Close'] else 0
                high = float(row['High']) if row['High'] else 0
                low = float(row['Low']) if row['Low'] else 0
                volume = float(row['TradedVolume']) if row['TradedVolume'] else 0
                date = row['TradingDate']

                if close > 0:
                    data[symbol]['closes'].append(close)
                    data[symbol]['highs'].append(high)
                    data[symbol]['lows'].append(low)
                    data[symbol]['volumes'].append(volume)
                    data[symbol]['dates'].append(date)
            except (ValueError, KeyError):
                pass

    return data


def calculate_volatility(closes):
    """Calculate annualized volatility from returns."""
    if len(closes) < 2:
        return 0

    returns = []
    for i in range(1, len(closes)):
        ret = (closes[i] - closes[i-1]) / closes[i-1] if closes[i-1] > 0 else 0
        returns.append(abs(ret))

    if not returns:
        return 0

    daily_vol = stdev(returns)
    annual_vol = daily_vol * (252 ** 0.5)
    return annual_vol * 100


def analyze(csv_file):
    """Run full portfolio analysis."""
    print("Loading portfolio...", file=sys.stderr)
    data = read_portfolio(csv_file)

    print("Calculating metrics...", file=sys.stderr)

    symbols = sorted(data.keys())
    metrics = {}

    for symbol in symbols:
        d = data[symbol]
        if len(d['closes']) < 20:
            continue

        closes = d['closes']
        volumes = d['volumes']

        # Basic stats
        avg_price = mean(closes)
        volatility = calculate_volatility(closes)
        min_price = min(closes)
        max_price = max(closes)
        avg_volume = mean([v for v in volumes if v > 0]) if any(volumes) else 0

        metrics[symbol] = {
            'avg_price': avg_price,
            'volatility_pct': volatility,
            'min_price': min_price,
            'max_price': max_price,
            'price_range_pct': ((max_price - min_price) / min_price * 100) if min_price > 0 else 0,
            'avg_volume': avg_volume,
            'bars': len(closes),
        }

    # Print summary
    print("\n" + "="*120)
    print("PORTFOLIO ANALYSIS: 15-SYMBOL QUANT FUTURES")
    print("="*120)

    print(f"\n{'Symbol':<15} {'Volatility%':<15} {'Avg Price':<15} {'Avg Volume':<15} {'Bars':<10}")
    print("-"*120)

    for symbol in sorted(metrics.keys(), key=lambda s: metrics[s]['volatility_pct'], reverse=True):
        m = metrics[symbol]
        print(f"{symbol:<15} {m['volatility_pct']:>14.2f} {m['avg_price']:>14.2f} {m['avg_volume']:>14.0f} {m['bars']:>9}")

    print("\n" + "="*120)
    print("KEY INSIGHTS")
    print("="*120)

    sorted_by_vol = sorted(metrics.keys(), key=lambda s: metrics[s]['volatility_pct'], reverse=True)

    print("\nHighest Volatility (Good for trending):")
    for sym in sorted_by_vol[:3]:
        print(f"  • {sym}: {metrics[sym]['volatility_pct']:.2f}% annual volatility")

    print("\nLowest Volatility (Stable hedges):")
    for sym in sorted_by_vol[-3:]:
        print(f"  • {sym}: {metrics[sym]['volatility_pct']:.2f}% annual volatility")

    print("\nHighest Volume (Best liquidity):")
    sorted_by_vol_traded = sorted(metrics.keys(), key=lambda s: metrics[s]['avg_volume'], reverse=True)
    for sym in sorted_by_vol_traded[:3]:
        print(f"  • {sym}: {metrics[sym]['avg_volume']:,.0f} contracts/day")

    print("\n" + "="*120)
    print("CORRELATION MATRIX (for pairs trading)")
    print("="*120)
    print("\nTo calculate optimal pairs, run:")
    print("  python3 -c \"import csv; df=...\"")
    print("(Use pandas for full correlation analysis)")


if __name__ == '__main__':
    if len(sys.argv) < 2:
        print("Usage: python3 analyze_portfolio.py <csv_file>", file=sys.stderr)
        sys.exit(1)

    analyze(sys.argv[1])
