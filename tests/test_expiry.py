from datetime import date

import pytest

from pmex.expiry import parse_expiry, roll_date, split_symbol


@pytest.mark.parametrize("code,expected", [
    ("JA24", date(2024, 1, 1)),
    ("FE24", date(2024, 2, 1)),
    ("DE23", date(2023, 12, 1)),
    ("AU22", date(2022, 8, 1)),
])
def test_parse_expiry_valid(code, expected):
    assert parse_expiry(code) == expected


@pytest.mark.parametrize("code", [
    "THU", "MON", "FRI",      # intraday day-of-week
    "DE23ID",                 # in-delivery suffix
    "ZZ24",                   # unknown month code
    "FE2",                    # too short
    "FEB24",                  # three-letter month
    "", None,                 # empty / missing
])
def test_parse_expiry_invalid(code):
    assert parse_expiry(code) is None


def test_split_symbol_dated():
    assert split_symbol("CRUDE10-FE24") == ("CRUDE10", date(2024, 2, 1))
    assert split_symbol("GO1OZ-DE23") == ("GO1OZ", date(2023, 12, 1))


@pytest.mark.parametrize("symbol", [
    "CRUDE10",         # bare, no expiry
    "TOLAGOLD-THU",    # intraday
    "CRUDE10-DE23ID",  # in-delivery
    "-FE24",           # empty base
])
def test_split_symbol_rejects_non_expiry(symbol):
    assert split_symbol(symbol) is None


def test_expiry_codes_sort_chronologically_via_date():
    # The exact bug that string-sorting caused: AU22 (Aug 2022) must come
    # before DE23 (Dec 2023), even though "DE23" < "AU22" would be false and
    # "AU22" < "DE23" is only accidentally right — JY22 vs AU22 exposes it.
    codes = ["DE23", "AU22", "JY22", "JA24", "FE24"]
    chrono = sorted(codes, key=parse_expiry)
    assert chrono == ["JY22", "AU22", "DE23", "JA24", "FE24"]


def test_roll_date_is_day_before_delivery_month():
    assert roll_date(date(2024, 2, 1)) == date(2024, 1, 31)
    assert roll_date(date(2024, 1, 1)) == date(2023, 12, 31)
