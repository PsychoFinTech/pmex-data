# PMEX Top 15 Futures - 16-Year Dataset (2008-2023)

> **Data files are not committed to this repo** — they are generated locally
> via `pmex-download`. See the command below to reproduce the full dataset.

## Reproduce the dataset

```bash
pip install -e .

# Fetch each year (or range) — server returns up to 3 months per request
pmex-download --from 2008-01-01 --to 2023-12-31 -o pmex_raw_2008_2023.csv

# Build continuous front-month perpetuals from the expiry-dated contracts
pmex-perpetual pmex_raw_2008_2023.csv \
  --symbols "CRUDE10,CRUDE100,GO1OZ,GO10OZ,GO100OZ,SL10,SL100OZ,SL500OZ" \
  -o pmex_perpetuals.csv
```

## Dataset stats (when generated)

| Property | Value |
|----------|-------|
| Raw rows | 94,331 |
| Date range | 2008-01-01 → 2023-12-29 |
| Unique trading dates | 4,118 |
| File size | ~5 MB |

## Top 15 Symbols (by frequency across 2008-2023)

| Rank | Symbol | Rows | Type |
|------|--------|------|------|
| 1 | KIBOR3M | 12,237 | Interest Rate |
| 2 | MINIGOLD | 7,086 | Mini Gold |
| 3 | TOLAGOLD | 6,529 | Intraday Gold (day-of-week, not stitchable) |
| 4 | CRUDE100 | 6,051 | Oil (100 bbl) |
| 5 | SL500OZ | 6,038 | Silver (500oz) |
| 6 | GO1OZ | 6,036 | Gold (1oz) |
| 7 | GO100OZ | 6,000 | Gold (100oz) |
| 8 | MTOLAGOLD | 5,737 | Mini Intraday Gold |
| 9 | GOLD | 5,671 | Physical Gold |
| 10 | CRUDE10 | 5,653 | Oil (10 bbl) |
| 11 | SL100OZ | 5,623 | Silver (100oz) |
| 12 | PALMOLEIN | 5,500 | Agricultural |
| 13 | GOLDKILO | 5,434 | Gold (1 kg) |
| 14 | GO10OZ | 5,402 | Gold (10oz) |
| 15 | SL10 | 5,334 | Silver (10oz) |

**Note on stitchability:** KIBOR3M, TOLAGOLD, MTOLAGOLD, MINIGOLD, GOLD, GOLDKILO, and PALMOLEIN
appear in the raw data as bare or intraday symbols (no `<MM><YY>` expiry code), so they
cannot be rolled into perpetuals. The oil and metal contracts (`CRUDE*`, `GO*`, `SL*`) carry
proper expiry codes and produce clean continuous series.

## Output columns

### Raw download (`pmex_raw_*.csv`)
```
TradingDate, Symbol, Open, High, Low, Close, TradedVolume, SettlementPrice, FXRate
```

### Perpetuals (`pmex_perpetuals.csv`)
```
Symbol, TradingDate, Open, High, Low, Close, Volume, FrontContract
```
Prices are back-adjusted (newest contract unadjusted, history shifted) so
returns are continuous across rolls. `FrontContract` records which expiry was
active on each date.
