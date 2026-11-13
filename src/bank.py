"""
bank.py - Chooses which version of the banking module the tests use.

Set the environment variable BANK_VERSION before running pytest:
    BANK_VERSION=buggy   -> src/bank_buggy.py   (default)
    BANK_VERSION=fixed   -> src/bank_fixed.py
The tests always write `from bank import Account, Bank`, so the SAME tests
run against both versions without any change.
"""

import os

BANK_VERSION = os.environ.get("BANK_VERSION", "buggy").lower()

if BANK_VERSION == "fixed":
    from bank_fixed import Account, Bank
elif BANK_VERSION == "buggy":
    from bank_buggy import Account, Bank
else:
    raise ValueError(f"BANK_VERSION must be 'buggy' or 'fixed', not {BANK_VERSION!r}")

__all__ = ["Account", "Bank", "BANK_VERSION"]
