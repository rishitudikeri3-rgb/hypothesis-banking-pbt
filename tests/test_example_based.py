"""
test_example_based.py - Traditional, hand-written PyTest unit tests.

These are the tests a typical developer writes: pick a few inputs, work out
the answer by hand, and assert it. They ALL PASS on the buggy version, which
is the central point of this project: passing example tests do not prove
the code is correct. They only prove it works for the inputs we thought of.

Each docstring has three parts (read by scripts/run_experiment.py to build
the test-case table in the report):
    first line  -> description
    Input:      -> the input used
    Expected:   -> the expected outcome
"""

import pytest

from bank import Account, Bank


def test_new_account_has_opening_balance():
    """A new account starts with the opening balance given.
    Input: open account with balance 500
    Expected: balance is 500
    """
    acc = Account("A1", "Asha", 500)
    assert acc.get_balance() == 500


def test_new_account_default_balance_is_zero():
    """A new account opened without a balance starts at zero.
    Input: open account with no balance argument
    Expected: balance is 0
    """
    acc = Account("A1", "Asha")
    assert acc.get_balance() == 0


def test_deposit_increases_balance():
    """Depositing money increases the balance by that amount.
    Input: balance 0, deposit 100
    Expected: balance is 100
    """
    acc = Account("A1", "Asha", 0)
    acc.deposit(100)
    assert acc.get_balance() == 100


def test_multiple_deposits_add_up():
    """Several deposits add up correctly.
    Input: balance 0, deposit 100, 250, 50
    Expected: balance is 400
    """
    acc = Account("A1", "Asha", 0)
    acc.deposit(100)
    acc.deposit(250)
    acc.deposit(50)
    assert acc.get_balance() == 400


def test_deposit_with_paise():
    """Deposits with paise (decimal amounts) are added correctly.
    Input: balance 0, deposit 10.50 then 20.25
    Expected: balance is 30.75
    """
    acc = Account("A1", "Asha", 0)
    acc.deposit(10.50)
    acc.deposit(20.25)
    assert acc.get_balance() == 30.75


def test_withdraw_decreases_balance():
    """Withdrawing money decreases the balance by that amount.
    Input: balance 100, withdraw 50
    Expected: balance is 50
    """
    acc = Account("A1", "Asha", 100)
    acc.withdraw(50)
    assert acc.get_balance() == 50


def test_withdraw_entire_balance():
    """Withdrawing exactly the whole balance leaves zero.
    Input: balance 100, withdraw 100
    Expected: balance is 0
    """
    acc = Account("A1", "Asha", 100)
    acc.withdraw(100)
    assert acc.get_balance() == 0


def test_withdraw_more_than_balance_raises():
    """Withdrawing more than the balance is rejected.
    Input: balance 100, withdraw 150
    Expected: ValueError, balance stays 100
    """
    acc = Account("A1", "Asha", 100)
    with pytest.raises(ValueError):
        acc.withdraw(150)
    assert acc.get_balance() == 100


def test_transfer_moves_money():
    """A transfer moves money from one account to another.
    Input: A=100, B=50, transfer 30 from A to B
    Expected: A is 70, B is 80
    """
    a = Account("A1", "Asha", 100)
    b = Account("B1", "Ravi", 50)
    a.transfer(b, 30)
    assert a.get_balance() == 70
    assert b.get_balance() == 80


def test_transfer_more_than_balance_raises():
    """A transfer larger than the sender's balance is rejected.
    Input: A=100, B=0, transfer 500 from A to B
    Expected: ValueError, A stays 100, B stays 0
    """
    a = Account("A1", "Asha", 100)
    b = Account("B1", "Ravi", 0)
    with pytest.raises(ValueError):
        a.transfer(b, 500)
    assert a.get_balance() == 100
    assert b.get_balance() == 0


def test_apply_interest():
    """Interest is added at the given percentage.
    Input: balance 1000, rate 5%
    Expected: balance is 1050
    """
    acc = Account("A1", "Asha", 1000)
    acc.apply_interest(5)
    assert acc.get_balance() == 1050


def test_zero_interest_leaves_balance_unchanged():
    """A 0% interest rate does not change the balance.
    Input: balance 1000, rate 0%
    Expected: balance is 1000
    """
    acc = Account("A1", "Asha", 1000)
    acc.apply_interest(0)
    assert acc.get_balance() == 1000


def test_bank_total_money():
    """The bank's total is the sum of all account balances.
    Input: accounts with 100, 200, 300
    Expected: total_money is 600
    """
    bank = Bank()
    bank.open_account("A1", "Asha", 100)
    bank.open_account("B1", "Ravi", 200)
    bank.open_account("C1", "Meera", 300)
    assert bank.total_money() == 600


def test_bank_total_unchanged_after_transfer():
    """A transfer between two accounts keeps the bank's total the same.
    Input: A=100, B=200, transfer 40 from A to B
    Expected: total_money stays 300
    """
    bank = Bank()
    a = bank.open_account("A1", "Asha", 100)
    b = bank.open_account("B1", "Ravi", 200)
    a.transfer(b, 40)
    assert bank.total_money() == 300


def test_duplicate_account_id_raises():
    """Opening two accounts with the same id is rejected.
    Input: open "A1" twice
    Expected: ValueError on the second open
    """
    bank = Bank()
    bank.open_account("A1", "Asha", 100)
    with pytest.raises(ValueError):
        bank.open_account("A1", "Someone else", 0)
