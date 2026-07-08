# PMEX historical OHLC bulk downloader

The PMEX public OHLC report page
([mportal.pmex.com.pk/mt5bonew/Home/OHLCReport](https://mportal.pmex.com.pk/mt5bonew/Home/OHLCReport))
only lets you pull **just under 3 calendar months** of futures data per request,
which makes collecting years of history painfully manual.

`pmex_ohlc.py` automates it: give it any start and end date and it splits the
range into server-legal windows, downloads each one from the page's own JSON
endpoint, decodes the columns, de-duplicates, and stitches everything into a
single CSV (or JSON).

No login required — it issues the exact same public request the site's **Show**
button makes.

## Install

```bash
pip install -r requirements.txt   # just `requests`
```

## Usage

```bash
# Ten years of everything into one CSV
python3 pmex_ohlc.py --from 2015-01-01 --to 2024-12-31 -o pmex_ohlc.csv

# One year, gold contracts only
python3 pmex_ohlc.py --from 2023-01-01 --to 2023-12-31 --symbol GOLD -o gold_2023.csv

# JSON output to stdout
python3 pmex_ohlc.py --from 2024-01-01 --to 2024-03-31 --format json
```

### Options

| Flag | Description |
|------|-------------|
| `--from YYYY-MM-DD` | Start date (required) |
| `--to YYYY-MM-DD` | End date (required) |
| `-o, --output` | Output file (default: stdout) |
| `--format {csv,json}` | Output format (default: csv) |
| `--symbol SUBSTR` | Keep only symbols containing this substring, case-insensitive (e.g. `GOLD`, `CRUDE`, `KIBOR`) |
| `--delay SECONDS` | Politeness delay between requests (default: 0.7) |
| `--quiet` | Suppress progress output |

## Output columns

`TradingDate, Symbol, Open, High, Low, Close, TradedVolume, SettlementPrice, FXRate`

`TradingDate` is normalised to `YYYY-MM-DD`. Rows are sorted by date then symbol,
and duplicates across window boundaries are removed.

## How it works

The page's JavaScript posts to a hidden endpoint:

```
POST /mt5bonew/Home/GetOHLC
body: txtFromDate=YYYY-MM-DD&txtEndDate=YYYY-MM-DD
```

It returns a JSON array — or the literal string `"Error"` when the window is too
wide. The width check is **calendar-month based**: the server rejects a window
when `(to.year*12 + to.month) - (from.year*12 + from.month) >= 3`, so the
day-of-month is irrelevant and the widest legal window spans exactly 3 calendar
months. The tool aligns windows to month ends (`Jan 1 → Mar 31`,
`Apr 1 → Jun 30`, …) to use the maximum size and minimise the number of
requests.

The endpoint's JSON keys are recycled from an unrelated report and are
mislabelled (`Trader_Id`, `acc_type`, `Amount`, …); the tool remaps them to the
real OHLC columns using the order in which the page renders them.

History appears to go back to at least 2010.

## Notes

- Be considerate: the default 0.7s delay between requests keeps the load light.
  Ten years is ~40 requests.
- This scrapes a public endpoint for personal/research use. Respect PMEX's terms
  of use and don't hammer the server.
