"""
bank_fixed.py - Corrected banking module (same API as bank_buggy.py).

Fixes:
 BUG-1  Money is a decimal.Decimal rounded to 2 places (paise), never a float.
 BUG-2  withdraw() rejects zero and negative amounts with ValueError.
 BUG-3  The overdraft check compares the exact amounts: amount > balance.
 BUG-4  transfer() to the same account is rejected; a normal transfer is a
        withdraw followed by a deposit, so money is never created.
 BUG-5  apply_interest() rejects negative rates and rounds HALF-UP to the
        nearest paisa instead of truncating.
 BUG-6  deposit() rejects zero and negative amounts with ValueError.
"""

from decimal import Decimal, InvalidOperation, ROUND_HALF_UP

CENT = Decimal("0.01")  # the smallest unit of money: one paisa


def to_decimal(value):
    """Convert value to a finite Decimal, or raise ValueError."""
    try:
        number = Decimal(str(value))   # str() avoids float artefacts
    except InvalidOperation:
        raise ValueError(f"Not a valid number: {value!r}")
    if not number.is_finite():          # rejects NaN and Infinity
        raise ValueError(f"Not a finite number: {value!r}")
    return number


def to_money(value):
    """Convert value to a Decimal rounded to 2 decimal places."""
    return to_decimal(value).quantize(CENT, rounding=ROUND_HALF_UP)


class Account:
    """A single bank account holding a balance in rupees."""

    def __init__(self, account_id, owner, balance=0):
        balance = to_money(balance)
        if balance < 0:
            raise ValueError("Opening balance cannot be negative")
        self.account_id = account_id
        self.owner = owner
        self.balance = balance

    def get_balance(self):
        """Return the current balance."""
        return self.balance

    def deposit(self, amount):
        """Add `amount` to the balance. Amount must be positive."""
        amount = to_money(amount)
        if amount <= 0:
            raise ValueError("Deposit amount must be positive")
        self.balance += amount

    def withdraw(self, amount):
        """Remove `amount` from the balance. Amount must be positive and
        not larger than the balance."""
        amount = to_money(amount)
        if amount <= 0:
            raise ValueError("Withdrawal amount must be positive")
        if amount > self.balance:
            raise ValueError("Insufficient funds")
        self.balance -= amount

    def transfer(self, to_account, amount):
        """Move `amount` from this account to a different account."""
        if to_account is self:
            raise ValueError("Cannot transfer to the same account")
        self.withdraw(amount)      # checks amount > 0 and enough funds
        to_account.deposit(amount)

    def apply_interest(self, rate_percent):
        """Add interest at `rate_percent` % (rounded to the nearest paisa)
        and return the interest added. Negative rates are rejected."""
        rate = to_decimal(rate_percent)
        if rate < 0:
            raise ValueError("Interest rate cannot be negative")
        interest = (self.balance * rate / 100).quantize(CENT, rounding=ROUND_HALF_UP)
        self.balance += interest
        return interest


class Bank:
    """A collection of accounts, looked up by account id."""

    def __init__(self):
        self.accounts = {}

    def open_account(self, account_id, owner, balance=0):
        """Create a new account and return it."""
        if account_id in self.accounts:
            raise ValueError(f"Account {account_id} already exists")
        account = Account(account_id, owner, balance)
        self.accounts[account_id] = account
        return account

    def get_account(self, account_id):
        """Return the account with this id."""
        return self.accounts[account_id]

    def total_money(self):
        """Return the sum of all balances in the bank."""
        return sum((account.balance for account in self.accounts.values()), Decimal("0"))
