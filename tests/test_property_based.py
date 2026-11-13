"""
test_property_based.py - Property-based tests written with Hypothesis.

Instead of picking inputs ourselves, each test states a RULE (a "property")
that must hold for EVERY valid input. The @given decorator tells Hypothesis
which kinds of input to generate (a "strategy"), and Hypothesis then runs the
test on hundreds of generated inputs, deliberately including edge cases such
as 0, 0.01 and values right next to a boundary. If any input breaks the rule,
Hypothesis "shrinks" it to the simplest input that still fails and reports it.

Why Decimal strategies? Money has exactly 2 decimal places, so we generate
amounts with st.decimals(places=2). Both versions of the bank accept these:
the buggy version converts them to float internally (that is BUG-1), the
fixed version keeps them as Decimal. The same test therefore runs cleanly on
both versions, and we compare results as exact Decimals with as_decimal().

Each docstring has three parts (read by scripts/run_experiment.py):
    first line -> the property in plain English
    Strategy:  -> the inputs Hypothesis generates
    Targets:   -> the seeded bug(s) the property is designed to expose
"""

from decimal import Decimal, ROUND_HALF_UP

import pytest
from hypothesis import example, given, settings, strategies as st

from bank import Account, Bank

CENT = Decimal("0.01")


def as_decimal(value):
    """Turn a balance (float or Decimal) into an exact Decimal for comparing.
    str() keeps every digit, so 0.30000000000000004 stays visible."""
    return Decimal(str(value))


# ---------------------------------------------------------------- strategies
# A strategy describes a set of possible inputs. Hypothesis picks from it.
money = st.decimals(min_value=Decimal("0.00"), max_value=Decimal("10000.00"), places=2)
positive_money = st.decimals(min_value=Decimal("0.01"), max_value=Decimal("10000.00"), places=2)
non_positive_money = st.decimals(min_value=Decimal("-10000.00"), max_value=Decimal("0.00"), places=2)
negative_money = st.decimals(min_value=Decimal("-10000.00"), max_value=Decimal("-0.01"), places=2)
any_rate = st.decimals(min_value=Decimal("-50.00"), max_value=Decimal("50.00"), places=2)
non_negative_rate = st.decimals(min_value=Decimal("0.00"), max_value=Decimal("50.00"), places=2)


# ------------------------------------------------------------ the properties

@settings(max_examples=200)
@given(start=money, amount=positive_money)
def test_deposit_then_withdraw_is_round_trip(start, amount):
    """Depositing an amount and then withdrawing the same amount leaves the balance exactly where it started.
    Strategy: start = decimals 0.00..10000.00 (2 dp); amount = decimals 0.01..10000.00 (2 dp)
    Targets: BUG-1
    """
    acc = Account("A1", "Test", start)
    acc.deposit(amount)
    acc.withdraw(amount)
    assert as_decimal(acc.get_balance()) == start


@settings(max_examples=200)
@given(deposits=st.lists(positive_money, min_size=1, max_size=20))
def test_balance_always_has_at_most_two_decimal_places(deposits):
    """After any sequence of deposits the balance has at most 2 decimal places (whole paise).
    Strategy: list of 1-20 deposits, each decimals 0.01..10000.00 (2 dp)
    Targets: BUG-1
    """
    acc = Account("A1", "Test", 0)
    for amount in deposits:
        acc.deposit(amount)
    balance = as_decimal(acc.get_balance())
    assert balance == balance.quantize(CENT)


@settings(max_examples=200)
@given(start=money, amount=non_positive_money)
def test_deposit_of_zero_or_negative_is_rejected(start, amount):
    """Depositing zero or a negative amount always raises ValueError and leaves the balance unchanged.
    Strategy: start = decimals 0.00..10000.00; amount = decimals -10000.00..0.00 (2 dp)
    Targets: BUG-6
    """
    acc = Account("A1", "Test", start)
    with pytest.raises(ValueError):
        acc.deposit(amount)
    assert as_decimal(acc.get_balance()) == start


@settings(max_examples=200)
@given(start=money, amount=negative_money)
def test_withdraw_of_negative_amount_is_rejected(start, amount):
    """Withdrawing a negative amount always raises ValueError and leaves the balance unchanged.
    Strategy: start = decimals 0.00..10000.00; amount = decimals -10000.00..-0.01 (2 dp)
    Targets: BUG-2
    """
    acc = Account("A1", "Test", start)
    with pytest.raises(ValueError):
        acc.withdraw(amount)
    assert as_decimal(acc.get_balance()) == start


# @example adds an input that is ALWAYS tried first. This is the boundary a
# developer would normally test (withdraw exactly the balance). It passes on
# the buggy code; Hypothesis still finds the boundary that the developer missed.
@settings(max_examples=300)
@example(start=Decimal("100.00"), amount=Decimal("100.00"))
@given(start=money, amount=positive_money)
def test_balance_never_negative_after_withdraw(start, amount):
    """After any withdrawal attempt (accepted or rejected) the balance is never negative.
    Strategy: start = decimals 0.00..10000.00; amount = decimals 0.01..10000.00; @example(100, 100)
    Targets: BUG-3
    """
    acc = Account("A1", "Test", start)
    try:
        acc.withdraw(amount)
    except ValueError:
        pass  # a rejected withdrawal is fine
    assert as_decimal(acc.get_balance()) >= 0


@settings(max_examples=200)
@given(start=money, extra=st.decimals(min_value=Decimal("1.00"), max_value=Decimal("1000.00"), places=2))
def test_overdraft_of_one_rupee_or_more_is_rejected(start, extra):
    """Withdrawing at least one rupee more than the balance is always rejected (control property).
    Strategy: start = decimals 0.00..10000.00; extra = decimals 1.00..1000.00; amount = start + extra
    Targets: none (control property: expected to pass on both versions)
    """
    acc = Account("A1", "Test", start)
    with pytest.raises(ValueError):
        acc.withdraw(start + extra)
    assert as_decimal(acc.get_balance()) == start


@settings(max_examples=200)
@given(start=money, rate=any_rate)
def test_interest_never_decreases_balance(start, rate):
    """Applying interest at any rate either raises ValueError or never decreases the balance.
    Strategy: start = decimals 0.00..10000.00; rate = decimals -50.00..50.00 (2 dp)
    Targets: BUG-5
    """
    acc = Account("A1", "Test", start)
    try:
        acc.apply_interest(rate)
    except ValueError:
        pass  # rejecting a negative rate is the correct behaviour
    assert as_decimal(acc.get_balance()) >= start


@settings(max_examples=200)
@given(start=money, rate=non_negative_rate)
def test_interest_is_rounded_to_nearest_paisa(start, rate):
    """Interest added equals balance x rate / 100, rounded half-up to the nearest paisa.
    Strategy: start = decimals 0.00..10000.00; rate = decimals 0.00..50.00 (2 dp)
    Targets: BUG-5
    """
    # The expected answer is computed independently with exact Decimal maths.
    expected = start + (start * rate / 100).quantize(CENT, rounding=ROUND_HALF_UP)
    acc = Account("A1", "Test", start)
    acc.apply_interest(rate)
    assert as_decimal(acc.get_balance()) == expected


@settings(max_examples=200)
@given(
    balances=st.lists(money, min_size=3, max_size=3),
    sender=st.integers(min_value=0, max_value=2),
    receiver=st.integers(min_value=0, max_value=2),
    amount=positive_money,
)
def test_transfer_conserves_total_money(balances, sender, receiver, amount):
    """Any transfer between any two accounts in the bank never changes the bank's total money.
    Strategy: 3 balances (decimals 0.00..10000.00); sender/receiver = integers 0..2 (may be equal); amount = decimals 0.01..10000.00
    Targets: BUG-4
    """
    bank = Bank()
    accounts = [bank.open_account(f"ACC{i}", f"Owner{i}", b) for i, b in enumerate(balances)]
    total_before = as_decimal(bank.total_money())
    try:
        accounts[sender].transfer(accounts[receiver], amount)
    except ValueError:
        pass  # a rejected transfer must also leave the total unchanged
    assert as_decimal(bank.total_money()) == total_before


@settings(max_examples=200)
@given(start=money, amount=positive_money)
def test_transfer_to_self_leaves_balance_unchanged(start, amount):
    """Transferring money from an account to itself never changes its balance.
    Strategy: start = decimals 0.00..10000.00; amount = decimals 0.01..10000.00 (2 dp)
    Targets: BUG-4
    """
    acc = Account("A1", "Test", start)
    try:
        acc.transfer(acc, amount)
    except ValueError:
        pass  # refusing a self-transfer is acceptable
    assert as_decimal(acc.get_balance()) == start
