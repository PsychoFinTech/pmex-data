from datetime import date

from pmex.downloader import make_windows, month_index


def _span_months(a, b):
    return month_index(b) - month_index(a)


def test_all_windows_within_server_limit():
    # The server rejects spans of >= 3 calendar months, so every window must
    # span at most 2 month-boundaries.
    windows = list(make_windows(date(2008, 1, 1), date(2024, 12, 31)))
    for d_from, d_to in windows:
        assert _span_months(d_from, d_to) < 3


def test_windows_are_contiguous_and_cover_range():
    start, end = date(2020, 1, 1), date(2021, 6, 30)
    windows = list(make_windows(start, end))
    assert windows[0][0] == start
    assert windows[-1][1] == end
    from datetime import timedelta
    for (_, prev_to), (next_from, _) in zip(windows, windows[1:]):
        assert next_from == prev_to + timedelta(days=1)


def test_clean_three_month_blocks():
    windows = list(make_windows(date(2023, 1, 1), date(2023, 12, 31)))
    assert windows == [
        (date(2023, 1, 1), date(2023, 3, 31)),
        (date(2023, 4, 1), date(2023, 6, 30)),
        (date(2023, 7, 1), date(2023, 9, 30)),
        (date(2023, 10, 1), date(2023, 12, 31)),
    ]


def test_mid_month_start():
    windows = list(make_windows(date(2015, 1, 15), date(2015, 5, 20)))
    assert windows[0] == (date(2015, 1, 15), date(2015, 3, 31))
    assert windows[-1][1] == date(2015, 5, 20)
    for d_from, d_to in windows:
        assert _span_months(d_from, d_to) < 3


def test_single_short_range():
    windows = list(make_windows(date(2023, 2, 1), date(2023, 2, 28)))
    assert windows == [(date(2023, 2, 1), date(2023, 2, 28))]


def test_year_rollover():
    windows = list(make_windows(date(2023, 11, 1), date(2024, 2, 29)))
    for d_from, d_to in windows:
        assert _span_months(d_from, d_to) < 3
    assert windows[0][0] == date(2023, 11, 1)
    assert windows[-1][1] == date(2024, 2, 29)
