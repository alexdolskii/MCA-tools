#!/usr/bin/env python3
"""Compatibility launcher; implementation lives in the mca_tools package."""

from mca_tools.cli import shg_analysis

if __name__ == "__main__":
    raise SystemExit(shg_analysis())
