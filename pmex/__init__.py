"""PMEX historical futures data tools.

Two capabilities:

* :mod:`pmex.downloader` — bulk-download OHLC history from the PMEX public
  endpoint, auto-chunking around the server's ~3-month-per-request limit.
* :mod:`pmex.perpetual` — stitch expiry-dated contracts into a single
  continuous (front-month, back-adjusted) series.
"""

__version__ = "0.2.0"
