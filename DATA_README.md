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
  --symbols "USDGOLD,EURGOLD,GBPGOLD,JPYGOLD,CADGOLD,AUDGOLD,CHFGOLD,CRUDE10,GO1OZ,NSDQ100,CRUDE100,SL10,GO10OZ,GOLDUSDJPY,GOLDGBPUSD" \
  -o pmex_perpetuals.csv
```

## Dataset stats (when generated)

| Property | Value |
|----------|-------|
| Raw rows | 94,331 |
| Date range | 2008-01-01 → 2023-12-29 |
| Unique trading dates | 4,118 |
| File size | ~5 MB |

## Top 15 Symbols (by total traded volume across 2008-2023)

| Rank | Symbol | Total Volume | Type |
|------|--------|-------------|------|
| 1 | USDGOLD | 9,367,028,572 | FX Gold (USD) |
| 2 | EURGOLD | 4,627,021,390 | FX Gold (EUR) |
| 3 | GBPGOLD | 4,257,713,982 | FX Gold (GBP) |
| 4 | JPYGOLD | 3,078,220,150 | FX Gold (JPY) |
| 5 | CADGOLD | 516,833,703 | FX Gold (CAD) |
| 6 | AUDGOLD | 233,512,987 | FX Gold (AUD) |
| 7 | CHFGOLD | 225,049,412 | FX Gold (CHF) |
| 8 | CRUDE10 | 2,874,526 | Oil (10 bbl) |
| 9 | GO1OZ | 2,758,790 | Gold (1oz) |
| 10 | NSDQ100 | 1,871,294 | NASDAQ 100 Index |
| 11 | CRUDE100 | 609,159 | Oil (100 bbl) |
| 12 | SL10 | 517,686 | Silver (10oz) |
| 13 | GO10OZ | 389,687 | Gold (10oz) |
| 14 | GOLDUSDJPY | 382,629 | Gold FX (USD/JPY) |
| 15 | GOLDGBPUSD | 367,918 | Gold FX (GBP/USD) |

All 15 carry proper `<MM><YY>` expiry codes and can be rolled into continuous
perpetual series. FX Gold pairs (ranks 1–7) dominate volume by orders of
magnitude — they represent leveraged gold contracts denominated in major
currencies and are by far the most actively traded instruments on PMEX.

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
