"""
test_stateful.py - Stateful (model-based) testing with Hypothesis.

WHY STATEFUL TESTING IS POWERFUL
A normal property test checks ONE operation. Real bugs often need a SEQUENCE
of operations to show up: deposit, then transfer, then withdraw, ... A
RuleBasedStateMachine lets us describe the operations ("rules") and the
things that must always be true ("invariants"). Hypothesis then writes
hundreds of random programs made of these rules, checks every invariant
after every single step, and, if something breaks, shrinks the program to
the SHORTEST sequence of steps that still breaks it.

We also keep a simple "model": a dictionary holding the balance we EXPECT
each account to have, worked out with exact Decimal maths. After each step
the real bank must agree with the model.
"""

from decimal import Decimal

from hypothesis import settings, strategies as st
from hypothesis.stateful import RuleBasedStateMachine, invariant, rule

from bank import Bank

ACCOUNT_IDS = ["ACC0", "ACC1", "ACC2"]


def as_decimal(value):
    """Turn a balance (float or Decimal) into an exact Decimal for comparing."""
    return Decimal(str(value))


class BankMachine(RuleBasedStateMachine):
    """Random sequences of deposits, withdrawals and transfers on 3 accounts."""

    # Strategies used by the rules below.
    account_ids = st.sampled_from(ACCOUNT_IDS)
    amounts = st.decimals(min_value=Decimal("0.01"), max_value=Decimal("1000.00"), places=2)

    def __init__(self):
        super().__init__()
        self.bank = Bank()
        self.model = {}  # account id -> expected balance (exact Decimal)
        for acc_id in ACCOUNT_IDS:
            self.bank.open_account(acc_id, f"Owner of {acc_id}", 0)
            self.model[acc_id] = Decimal("0")

    # ------------------------------------------------------------- rules
    # A rule is one operation Hypothesis may choose as the next step.

    @rule(acc_id=account_ids, amount=amounts)
    def deposit(self, acc_id, amount):
        self.bank.get_account(acc_id).deposit(amount)
        self.model[acc_id] += amount

    @rule(acc_id=account_ids, amount=amounts)
    def withdraw(self, acc_id, amount):
        try:
            self.bank.get_account(acc_id).withdraw(amount)
        except ValueError:
            return  # the bank refused, so the model does not change
        self.model[acc_id] -= amount

    @rule(sender=account_ids, receiver=account_ids, amount=amounts)
    def transfer(self, sender, receiver, amount):
        # sender and receiver may be the same account on purpose.
        try:
            self.bank.get_account(sender).transfer(self.bank.get_account(receiver), amount)
        except ValueError:
            return
        self.model[sender] -= amount
        self.model[receiver] += amount

    # -------------------------------------------------------- invariants
    # An invariant is checked after EVERY step of EVERY generated program.

    @invariant()
    def no_negative_balances(self):
        for acc_id in ACCOUNT_IDS:
            balance = as_decimal(self.bank.get_account(acc_id).get_balance())
            assert balance >= 0, f"INVARIANT no-negative-balance violated: {acc_id} = {balance}"

    @invariant()
    def total_money_is_conserved(self):
        # Money only enters via deposit and leaves via withdraw, so the bank's
        # total must equal the total of the model.
        actual = as_decimal(self.bank.total_money())
        expected = sum(self.model.values(), Decimal("0"))
        assert actual == expected, f"INVARIANT total-money-conserved violated: bank has {actual}, expected {expected}"

    @invariant()
    def balances_match_model(self):
        for acc_id in ACCOUNT_IDS:
            actual = as_decimal(self.bank.get_account(acc_id).get_balance())
            assert actual == self.model[acc_id], (
                f"INVARIANT balance-matches-model violated: {acc_id} has {actual}, expected {self.model[acc_id]}"
            )


# 200 random programs, each up to 20 steps long.
BankMachine.TestCase.settings = settings(max_examples=200, stateful_step_count=20)

# pytest collects this class and runs the state machine as one test.
TestBankStateMachine = BankMachine.TestCase
