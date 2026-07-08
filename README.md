# PMEX historical futures data tools

Two command-line tools for working with Pakistan Mercantile Exchange (PMEX)
futures history:

- **`pmex-download`** — bulk-download OHLC history, auto-chunking around the
  public report page's ~3-month-per-request limit.
- **`pmex-perpetual`** — stitch expiry-dated contracts into a single continuous
  (front-month, back-adjusted) series.
  [pmex_perpetuals_2008_2024_Q1.csv](https://github.com/user-attachments/files/29802021/pmex_perpetuals_2008_2024_Q1.csv)


No login required — the downloader issues the exact same public request the
site's **Show** button makes.

## Install

```bash
pip install -e .          # runtime (just `requests`)
pip install -e ".[dev]"   # + pytest and ruff for development
```

This exposes the `pmex-download` and `pmex-perpetual` commands. The root
`pmex_ohlc.py` and `create_perpetuals.py` scripts remain as thin wrappers, so
existing `python3 pmex_ohlc.py ...` invocations keep working.

## Download OHLC history

```bash
# Ten years of everything into one CSV
pmex-download --from 2015-01-01 --to 2024-12-31 -o pmex_ohlc.csv

# One year, gold contracts only (substring match)
pmex-download --from 2023-01-01 --to 2023-12-31 --symbol GOLD -o gold_2023.csv

# Several exact symbols (pipe-separated)
pmex-download --from 2023-01-01 --to 2023-12-31 --symbol "CRUDE10|CRUDE100" -o oil.csv

# JSON output to stdout
pmex-download --from 2024-01-01 --to 2024-03-31 --format json
```

### Options

| Flag | Description |
|------|-------------|
| `--from YYYY-MM-DD` | Start date (required) |
| `--to YYYY-MM-DD` | End date (required) |
| `-o, --output` | Output file (default: stdout) |
| `--format {csv,json}` | Output format (default: csv) |
| `--symbol` | Pipe-separated **exact** list (`CRUDE10\|GOLD`) *or* a single **substring** (`GOLD`). Case-insensitive. |
| `--delay SECONDS` | Politeness delay between requests (default: 0.7) |
| `--quiet` | Suppress progress output |

### Output columns

`TradingDate, Symbol, Open, High, Low, Close, TradedVolume, SettlementPrice, FXRate`

`TradingDate` is normalised to `YYYY-MM-DD`. Rows are sorted by date then symbol,
and duplicates across window boundaries are removed.

## Build continuous perpetuals

PMEX lists futures as monthly dated contracts (`CRUDE10-JA24`, `CRUDE10-FE24`,
…). `pmex-perpetual` stitches them into one continuous front-month series:

```bash
pmex-perpetual pmex_ohlc.csv --symbols "CRUDE10,GO1OZ,SL10" -o perpetuals.csv
```

| Flag | Description |
|------|-------------|
| `input_csv` | A CSV produced by `pmex-download` (positional) |
| `--symbols` | Comma-separated base symbols (default: all discovered) |
| `--method {back-adjust,ratio,none}` | Roll-gap adjustment (default: `back-adjust`) |
| `-o, --output` | Output file (default: `pmex_perpetuals.csv`) |
| `--limit N` | Process at most N symbols |
| `--quiet` | Suppress progress output |

What it does, and why it's correct:

1. **Chronological ordering** by real expiry date (parsed from the code), so
   `AU22` sorts before `DE23` — never by raw string.
2. **Strict validation** — only genuine `<MM><YY>` expiries are stitched;
   intraday (`-THU`), in-delivery (`-DE23ID`), and bare symbols are skipped.
3. **Front-month roll** — on each date the active contract is the nearest expiry
   that hasn't rolled (roll is the day before the delivery month), giving exactly
   one bar per date with no duplicates.
4. **Back-adjustment** — roll gaps are removed so returns are continuous. The
   newest contract is left unadjusted, so the latest price is the real market
   price and history is shifted to match (standard convention).

Adjustment methods: `back-adjust` (additive Panama, default), `ratio`
(proportional), `none` (raw front-month splice).

Output columns: `Symbol, TradingDate, Open, High, Low, Close, Volume, FrontContract`.

## How the downloader works

The report page's JavaScript posts to a hidden endpoint:

```
POST /mt5bonew/Home/GetOHLC
body: txtFromDate=YYYY-MM-DD&txtEndDate=YYYY-MM-DD
```

It returns a JSON array — or the literal string `"Error"` when the window is too
wide. The width check is **calendar-month based**: the server rejects a window
when `(to.year*12 + to.month) - (from.year*12 + from.month) >= 3`, so the
day-of-month is irrelevant and the widest legal window spans exactly 3 calendar
months. The tool aligns windows to month ends (`Jan 1 → Mar 31`, `Apr 1 → Jun
30`, …) to use the maximum size and minimise requests, with exponential-backoff
retries on transient failures.

The endpoint's JSON keys are recycled from an unrelated report and are
mislabelled (`Trader_Id`, `acc_type`, `Amount`, …); the tool remaps them to the
real OHLC columns using the order in which the page renders them. History goes
back to **2008** (PMEX's first trading year).

## Project layout

```
pmex/
  expiry.py       expiry-code parsing and symbol splitting (shared)
  downloader.py   OHLC download + windowing  (pmex-download)
  perpetual.py    continuous-contract stitching (pmex-perpetual)
tests/            pytest suite
pmex_ohlc.py          thin wrapper -> pmex.downloader
create_perpetuals.py  thin wrapper -> pmex.perpetual
```

## Development

```bash
pip install -e ".[dev]"
ruff check .
python3 -m pytest -q
```

CI runs lint + tests on Python 3.9–3.12 (`.github/workflows/ci.yml`).

## Notes

- Be considerate: the default 0.7s delay keeps server load light. Ten years is
  ~40 requests.
- This scrapes a public endpoint for personal/research use. Respect PMEX's terms
  of use and don't hammer the server.
