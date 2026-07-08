import csv
from datetime import date

import pytest

from pmex.perpetual import read_contracts, stitch_perpetual

JA24 = date(2024, 1, 1)  # roll_date 2023-12-31
FE24 = date(2024, 2, 1)  # roll_date 2024-01-31


def _bar(close, o=None, h=None, low=None, vol=1):
    o = close if o is None else o
    h = close if h is None else h
    low = close if low is None else low
    return {"open": o, "high": h, "low": low, "close": close, "volume": vol}


def _two_contract_book():
    # JA24 and FE24 overlap; a roll happens across the Dec/Jan boundary.
    return {
        JA24: {
            date(2023, 12, 29): _bar(101),
            date(2023, 12, 31): _bar(102),
        },
        FE24: {
            date(2023, 12, 29): _bar(103),
            date(2023, 12, 31): _bar(104),
            date(2024, 1, 2): _bar(105),
        },
    }


def test_one_bar_per_date_sorted_and_unique():
    out = stitch_perpetual(_two_contract_book(), method="none")
    dates = [b["date"] for b in out]
    assert dates == sorted(dates)
    assert len(dates) == len(set(dates))          # no duplicate calendar dates
    assert dates == [date(2023, 12, 29), date(2023, 12, 31), date(2024, 1, 2)]


def test_front_month_selection():
    # Before the roll the nearer expiry (JA24) is front; after, FE24 takes over.
    out = stitch_perpetual(_two_contract_book(), method="none")
    by_date = {b["date"]: b for b in out}
    assert by_date[date(2023, 12, 29)]["contract"] == "24-01"  # JA24
    assert by_date[date(2023, 12, 31)]["contract"] == "24-01"  # JA24 (roll day)
    assert by_date[date(2024, 1, 2)]["contract"] == "24-02"    # FE24


def test_raw_splice_has_the_roll_jump():
    out = stitch_perpetual(_two_contract_book(), method="none")
    closes = [b["close"] for b in out]
    assert closes == [101, 102, 105]  # 102 -> 105 contains the artificial gap


def test_back_adjust_removes_roll_gap_and_keeps_newest_true():
    out = stitch_perpetual(_two_contract_book(), method="back-adjust")
    by_date = {b["date"]: b["close"] for b in out}
    # Newest contract (FE24) is left untouched.
    assert by_date[date(2024, 1, 2)] == pytest.approx(105)
    # History shifted up by the roll gap (FE-JA on 2023-12-31 = 104-102 = 2).
    assert by_date[date(2023, 12, 31)] == pytest.approx(104)
    assert by_date[date(2023, 12, 29)] == pytest.approx(103)


def test_ratio_adjust_keeps_newest_true():
    out = stitch_perpetual(_two_contract_book(), method="ratio")
    by_date = {b["date"]: b["close"] for b in out}
    assert by_date[date(2024, 1, 2)] == pytest.approx(105)
    assert by_date[date(2023, 12, 31)] == pytest.approx(102 * 104 / 102)
    assert by_date[date(2023, 12, 29)] == pytest.approx(101 * 104 / 102)


def test_empty_book():
    assert stitch_perpetual({}, method="back-adjust") == []


def test_unknown_method_raises():
    with pytest.raises(ValueError):
        stitch_perpetual(_two_contract_book(), method="nonsense")


def _write_csv(path, rows):
    cols = ["TradingDate", "Symbol", "Open", "High", "Low", "Close",
            "TradedVolume", "SettlementPrice", "FXRate"]
    with open(path, "w", newline="") as f:
        w = csv.DictWriter(f, fieldnames=cols)
        w.writeheader()
        w.writerows(rows)


def test_read_contracts_skips_intraday_and_bare(tmp_path):
    p = tmp_path / "data.csv"
    _write_csv(p, [
        # genuine dated contract -> kept
        {"TradingDate": "2023-12-29", "Symbol": "TOLAGOLD-DE23",
         "Open": "100", "High": "101", "Low": "99", "Close": "100",
         "TradedVolume": "5", "SettlementPrice": "100", "FXRate": "1"},
        # intraday day-of-week -> skipped
        {"TradingDate": "2023-12-29", "Symbol": "TOLAGOLD-THU",
         "Open": "100", "High": "101", "Low": "99", "Close": "100",
         "TradedVolume": "5", "SettlementPrice": "100", "FXRate": "1"},
        # in-delivery -> skipped
        {"TradingDate": "2023-12-29", "Symbol": "TOLAGOLD-DE23ID",
         "Open": "100", "High": "101", "Low": "99", "Close": "100",
         "TradedVolume": "5", "SettlementPrice": "100", "FXRate": "1"},
    ])
    contracts = read_contracts(str(p), "TOLAGOLD")
    assert list(contracts) == [date(2023, 12, 1)]  # only the DE23 expiry survives
    assert len(contracts[date(2023, 12, 1)]) == 1


def test_read_contracts_skips_nonpositive_prices(tmp_path):
    p = tmp_path / "data.csv"
    _write_csv(p, [
        {"TradingDate": "2023-12-29", "Symbol": "CRUDE10-DE23",
         "Open": "0", "High": "0", "Low": "0", "Close": "0",
         "TradedVolume": "5", "SettlementPrice": "0", "FXRate": "1"},
    ])
    assert read_contracts(str(p), "CRUDE10") == {}
