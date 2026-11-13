"""
bank_buggy.py - Banking module WITH SIX SEEDED BUGS.

This is the "System Under Test" in its faulty form. Every bug below is the
kind of mistake a real developer could make. None of them is caught by the
hand-written example tests in tests/test_example_based.py, but each one is
caught by at least one Hypothesis property in tests/test_property_based.py.

=============================================================================
 SEEDED BUG LIST
=============================================================================
 BUG-1  Money is stored as a binary float.
        What goes wrong : 0.1 + 0.2 = 0.30000000000000004, so balances drift
                          away from whole paise after deposits/withdrawals.
        Why examples miss: the example tests use "nice" numbers like 100, 50
                          and 10.50 that are exact in binary floating point.
        Caught by        : test_deposit_then_withdraw_is_round_trip,
                          test_balance_always_has_at_most_two_decimal_places

 BUG-2  withdraw() does not reject negative amounts.
        What goes wrong : withdraw(-50) ADDS 50 to the balance.
        Why examples miss: nobody writes a test that withdraws a negative sum.
        Caught by        : test_withdraw_of_negative_amount_is_rejected

 BUG-3  The overdraft check compares whole rupees only (int(...)).
        What goes wrong : with a balance of 0.00 you can withdraw 0.01-0.99,
                          and with 10.40 you can withdraw 10.45, so the
                          balance goes negative by less than one rupee.
        Why examples miss: the examples test 150 from 100 (rejected) and 100
                          from 100 (allowed); the bug only lives in the
                          fractional gap just above the balance.
        Caught by        : test_balance_never_negative_after_withdraw

 BUG-4  transfer() to the SAME account creates money.
        What goes wrong : both new balances are computed from the old values
                          before either is saved; when sender == receiver
                          the second assignment overwrites the first, so the
                          account ends up with balance + amount.
        Why examples miss: the examples only transfer between two different
                          accounts.
        Caught by        : test_transfer_to_self_leaves_balance_unchanged,
                          test_transfer_conserves_total_money

 BUG-5  apply_interest() accepts negative rates AND truncates instead of
        rounding.
        What goes wrong : a rate of -5 silently removes money; interest of
                          0.005 becomes 0.00 instead of 0.01 (always rounded
                          down, so customers lose fractions of a paisa).
        Why examples miss: the examples use 5% of 1000 (= exactly 50) and 0%.
        Caught by        : test_interest_never_decreases_balance,
                          test_interest_is_rounded_to_nearest_paisa

 BUG-6  deposit() accepts zero and negative amounts.
        What goes wrong : deposit(-100) quietly takes money OUT.
        Why examples miss: the examples only deposit positive amounts.
        Caught by        : test_deposit_of_zero_or_negative_is_rejected
=============================================================================
"""


class Account:
    """A single bank account holding a balance in rupees."""

    def __init__(self, account_id, owner, balance=0):
        self.account_id = account_id
        self.owner = owner
        self.balance = float(balance)          # BUG-1: float, not Decimal

    def get_balance(self):
        """Return the current balance."""
        return self.balance

    def deposit(self, amount):
        """Add `amount` to the balance."""
        # BUG-6: no check that the amount is positive
        self.balance += float(amount)          # BUG-1: float arithmetic

    def withdraw(self, amount):
        """Remove `amount` from the balance if there is enough money."""
        amount = float(amount)
        # BUG-2: no check for a negative amount
        # BUG-3: compares whole rupees only, so 0.45 > 0.40 is NOT noticed
        if int(amount) > int(self.balance):
            raise ValueError("Insufficient funds")
        self.balance -= amount

    def transfer(self, to_account, amount):
        """Move `amount` from this account to `to_account`."""
        amount = float(amount)
        if amount <= 0:
            raise ValueError("Transfer amount must be positive")
        if amount > self.balance:
            raise ValueError("Insufficient funds")
        # BUG-4: both new balances are worked out first, then saved.
        # If to_account is self, the second line overwrites the first.
        new_from_balance = self.balance - amount
        new_to_balance = to_account.balance + amount
        self.balance = new_from_balance
        to_account.balance = new_to_balance

    def apply_interest(self, rate_percent):
        """Add interest at `rate_percent` % and return the interest added."""
        rate = float(rate_percent)
        # BUG-5: negative rates are not rejected, and int() truncates
        # (always rounds towards zero) instead of rounding to nearest paisa.
        interest = int(self.balance * rate) / 100
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
        return sum(account.balance for account in self.accounts.values())
