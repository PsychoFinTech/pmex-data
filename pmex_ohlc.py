#!/usr/bin/env python3
"""Backward-compatible entry point. Logic lives in :mod:`pmex.downloader`.

Prefer the installed console script ``pmex-download`` (see pyproject.toml).
"""

from pmex.downloader import main

if __name__ == "__main__":
    main()
