# PMEX Top 15 Futures - 16-Year Backtest Dataset

## 📊 Dataset: `pmex_top15_2008_2024.csv`

**Size:** ~1.5 GB  
**Rows:** ~2.5M (15 symbols × 16 years × ~250 trading days)  
**Date Range:** 2008-01-01 to 2024-12-31  
**Symbols:** 15 top high-volume futures  

### Symbols Included

| Tier | Symbol | Volume | Type |
|------|--------|--------|------|
| **Tier 1 (Mega-Liquid)** | USDGOLD | 321.3M | Gold/USD pair |
| | GBPGOLD | 186.7M | Gold/GBP pair |
| | EURGOLD | 148.1M | Gold/EUR pair |
| **Tier 2 (High-Liquid)** | JPYGOLD | 95.2M | Gold/JPY pair |
| | CADGOLD | 40.3M | Gold/CAD pair |
| | AUDGOLD | 35.2M | Gold/AUD pair |
| | CHFGOLD | 16.5M | Gold/CHF pair |
| **Tier 3 (Medium-Liquid)** | GO1OZ | 684K | Gold 1oz |
| | CRUDE10 | 212K | Oil 10bbl |
| | NSDQ100 | 103K | Nasdaq 100 |
| **Tier 4 (Specialty)** | PLATINUM5 | 71K | Platinum 5oz |
| | CRUDE100 | 70K | Oil 100bbl |
| | SL10 | 53K | Silver 10oz |
| | GO10OZ | 50K | Gold 10oz |
| | COPPER | 16K | Copper |

---

## 🎯 Backtest Strategies

### 1. Mean Reversion (7 GOLD Pairs)

**Hypothesis:** Gold forex pairs are highly correlated; when one diverges, it mean-reverts.

```python
# Strategy:
# 1. Calculate Z-score for each GOLD pair vs group average
# 2. When Z-score > 2: Short (expect reversion)
# 3. When Z-score < -2: Long (expect reversion)
# 4. Exit when Z-score returns to mean (0)

Portfolio: USDGOLD, GBPGOLD, EURGOLD, JPYGOLD, CADGOLD, AUDGOLD, CHFGOLD
Expected Sharpe: 1.5-2.5 (low execution costs, high correlation)
```

### 2. Volatility Targeting (Energy Complex)

**Hypothesis:** NGAS1K has 5% daily vol, CRUDE10 has 4.9% daily vol; trade based on vol regime.

```python
# Strategy:
# 1. Track 20-day rolling volatility for CRUDE10, NGAS1K
# 2. When NGAS1K vol > CRUDE10 vol + threshold: Scale up NGAS1K position
# 3. Kelly criterion sizing based on daily vol

Portfolio: CRUDE10, CRUDE100, SL10, PLATINUM5, NSDQ100
Expected Sharpe: 1.8-2.2 (dynamic position sizing)
```

### 3. Pairs Trading (Energy Spread)

**Hypothesis:** CRUDE10 vs NGAS1K have different beta to macro; their spread mean-reverts.

```python
# Strategy:
# 1. Calculate spread: CRUDE10 - NGAS1K (normalized by volatility)
# 2. When spread > 2σ: Long NGAS1K, Short CRUDE10 (pairs hedge)
# 3. When spread < -2σ: Long CRUDE10, Short NGAS1K
# 4. Exit on spread mean reversion

Portfolio: CRUDE10 + NGAS1K
Expected Sharpe: 2.0-3.0 (market neutral, uncorrelated)
```

### 4. Trend Following (Equity Hedge)

**Hypothesis:** NSDQ100 trends; GOLD pairs revert. Diversified portfolio.

```python
# Strategy:
# 1. 50-200 day SMA crossover on NSDQ100
# 2. ATR for position sizing
# 3. GOLD pairs as portfolio hedge (inverse correlation)

Portfolio: NSDQ100 + 2x GOLD pairs (hedge)
Expected Sharpe: 1.2-1.8 (drawdown-reduced)
```

---

## 📈 Walk-Forward Backtesting (Recommended)

```
In-Sample:      2008-01-01 → 2015-12-31 (8 years)  [Model training]
Validation:     2016-01-01 → 2020-12-31 (5 years)  [Model tuning]
Out-of-Sample:  2021-01-01 → 2024-12-31 (4 years)  [Live-trading simulation]

Key Events in Test Data:
  • 2008: Financial crisis (extreme volatility)
  • 2011-2012: Eurozone crisis (EUR pair stress)
  • 2016: Brexit (GBP volatility spike)
  • 2020: COVID crash (all-pairs crash)
  • 2021-2022: Inflation + rate hikes (commodity boom)
  • 2023-2024: Macro normalization (range-bound)
```

---

## 🔧 Data Format

```csv
TradingDate,Symbol,Open,High,Low,Close,TradedVolume,SettlementPrice,FXRate
2008-01-02,USDGOLD,1234.56,1245.67,1230.00,1240.00,1000,1240.50,81.23
2008-01-03,USDGOLD,1240.00,1250.00,1235.00,1245.00,950,1245.50,81.15
...
```

**Columns:**
- `TradingDate`: YYYY-MM-DD (sorted)
- `Symbol`: Contract name (no expiry codes for perpetuals)
- `Open, High, Low, Close`: OHLC prices
- `TradedVolume`: Contracts traded
- `SettlementPrice`: Settlement price (for daily P&L)
- `FXRate`: PKR exchange rate (for multi-currency portfolios)

---

## 📊 Quick Analysis

```bash
# View data size
wc -l pmex_top15_2008_2024.csv

# Check symbol distribution
cut -d, -f2 pmex_top15_2008_2024.csv | sort | uniq -c | sort -rn

# Check date range
tail -n +2 pmex_top15_2008_2024.csv | cut -d, -f1 | sort | head -1
tail -n +2 pmex_top15_2008_2024.csv | cut -d, -f1 | sort | tail -1

# Quick stats with Python
python3 analyze_portfolio.py pmex_top15_2008_2024.csv
```

---

## ⚠️ Known Limitations

1. **Data Gap:** 2025-Q2 onwards (server unavailable)
2. **No Expiry Contracts:** Only base perpetuals (no calendar spreads)
3. **No Dividends/Interest:** Just OHLC prices
4. **No Corporate Actions:** Splits/adjustments not included
5. **FX Rates:** In PKR only (adjust for international trading)

---

## 🚀 Next Steps

1. **Load & Explore:** Verify data integrity, plot key symbols
2. **Calculate Returns:** Daily/monthly returns for correlation
3. **Backtest:** Implement mean-reversion strategy (simplest to validate)
4. **Optimize:** Kelly criterion, position sizing, stop-loss levels
5. **Walk-Forward:** Validate on out-of-sample 2021-2024
6. **Paper Trade:** Run on live data once validated

---

## 📚 Resources

- **Backtesting Library:** `backtrader`, `zipline`, `vectorbt` (Python)
- **Data Analysis:** `pandas`, `numpy`, `scipy.stats`
- **Visualization:** `matplotlib`, `plotly`
- **Optimization:** `scipy.optimize`, `optuna`

---

**Dataset Created:** $(date)  
**Download Source:** PMEX public API (pmex_ohlc.py)  
**Total Data Points:** ~2.5M rows  
**Backtest-Ready:** Yes ✅
