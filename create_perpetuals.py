#!/usr/bin/env python3
"""Backward-compatible entry point. Logic lives in :mod:`pmex.perpetual`.

Prefer the installed console script ``pmex-perpetual`` (see pyproject.toml).
"""

from pmex.perpetual import main

if __name__ == "__main__":
    main()
