#!/usr/bin/env python3
"""Standalone wrapper for the autodev release readiness gate.

Delegates to autodev.release_readiness_gate.main so we have a single
source of truth that works both from source tree and from PyPI install.
"""
from autodev.release_readiness_gate import main

if __name__ == "__main__":
    main()
