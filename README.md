# Property-Based Testing of a Banking Transaction Module Using Hypothesis

**Automated Input Generation and Failure Shrinking**
Software Testing – Course Project · Rishit Mahantesh Udikeri (1BM23AD046) · Dept. of AI & DS, BMS College of Engineering, Bengaluru · 2026–27

## The idea in one paragraph

Example-based unit tests only check the inputs the developer thought of. Property-based testing (PBT) lets you
state rules the code must **always** satisfy (for example, "a transfer never changes the bank's total money").
Hypothesis then generates hundreds of inputs, including edge cases, to try to break those rules. When it finds a
failure, it **shrinks** the input to the simplest one that still fails. This project shows a banking module that
passes all 15 hand-written PyTest tests while hiding 6 bugs, and Hypothesis finds every one of them automatically.

## Project layout

```
property-based-testing-project/
├── README.md
├── requirements.txt
├── pytest.ini                 # tells pytest to look in src/ for `import bank`
├── src/
│   ├── bank_buggy.py          # 6 seeded bugs, documented at the top of the file
│   ├── bank_fixed.py          # same API, all bugs fixed (Decimal money, ValueError on bad input)
│   └── bank.py                # picks buggy/fixed from env var BANK_VERSION (default: buggy)
├── tests/
│   ├── conftest.py            # Hypothesis profile: no deadline, no example database (reproducible)
│   ├── test_example_based.py  # 15 traditional PyTest tests (all pass on the buggy version!)
│   ├── test_property_based.py # 10 Hypothesis @given properties
│   └── test_stateful.py       # 1 RuleBasedStateMachine (random sequences of operations)
├── scripts/
│   ├── run_experiment.py      # runs 3 suites x 2 versions -> results/*.txt, *.xml, metrics.json
│   └── make_charts.py         # results/metrics.json -> results/*.png
├── results/                   # raw outputs, metrics.json, charts
└── report/
    ├── build_report.py        # results/ + src/ -> the .docx report
    └── Software_Testing_Project_Report.docx
```

## Setup (Windows PowerShell)

```powershell
cd property-based-testing-project
python -m venv .venv
.venv\Scripts\Activate.ps1
pip install -r requirements.txt
```

On Linux/macOS use `source .venv/bin/activate`, and put `BANK_VERSION=buggy` / `BANK_VERSION=fixed` in front of
each command instead of setting `$env:BANK_VERSION`.

## Running the suites

The **same test files** run against either version. You choose the version with the `BANK_VERSION` environment variable.

```powershell
# --- buggy version (the default) ---
$env:BANK_VERSION = "buggy"
pytest tests/test_example_based.py -v                                            # 15 passed
pytest tests/test_property_based.py --hypothesis-seed=12345 --tb=short            # 9 failed, 1 passed
pytest tests/test_stateful.py --hypothesis-seed=12345 --tb=short                  # 1 failed (3 distinct errors)

# --- fixed version ---
$env:BANK_VERSION = "fixed"
pytest -v                                                                         # 26 passed

# extra: show how many inputs Hypothesis generated for each property
pytest tests/test_property_based.py --hypothesis-seed=12345 --hypothesis-show-statistics
```

`--hypothesis-seed=12345` makes the "random" inputs identical on every run, so you will see the same
counterexamples as in the report.

## Regenerating results, charts and the report

```powershell
python scripts/run_experiment.py      # ~10 s; writes results/*.txt, results/*.xml, results/metrics.json
python scripts/make_charts.py         # writes results/chart1..4 and workflow.png
python report/build_report.py         # writes report/Software_Testing_Project_Report.docx
```

Every number, table and counterexample in the report is read from `results/metrics.json`, so the report always
matches the latest run. `run_experiment.py` also prints a verification block:

```
example_tests_all_pass_on_buggy: True
every_seeded_bug_caught_by_pbt: True
everything_passes_on_fixed: True
```

## How to demo this live in class (about 5 minutes)

Open a terminal in the project folder with the venv activated, then run these in order.

**1. "The code passes its unit tests."**
```powershell
$env:BANK_VERSION = "buggy"
pytest tests/test_example_based.py -v
```
→ 15 green tests. "By normal standards, this module is done."

**2. "Now let Hypothesis try to break the rules."**
```powershell
pytest tests/test_property_based.py --hypothesis-seed=12345 --tb=short -q
```
→ 9 of 10 properties fail. Scroll to any `Failing test case:` block and point out how small the shrunk inputs are.

**3. Zoom in on one bug (overdraft boundary, BUG-3).**
```powershell
pytest tests/test_property_based.py::test_balance_never_negative_after_withdraw --hypothesis-seed=12345 --tb=short
```
→ `start=Decimal('0.00'), amount=Decimal('0.01')` → balance becomes `-0.01`. Then open `src/bank_buggy.py` and show
`if int(amount) > int(self.balance):`, which compares whole rupees only. Also point out the `@example(100, 100)`
in the test: that's the boundary a human would test, and it passes.

**4. Stateful testing: a shrunk sequence of operations.**
```powershell
pytest tests/test_stateful.py --hypothesis-seed=12345 --tb=short
```
→ Look for `state.deposit(...)` / `state.withdraw(...)` lines. Hypothesis reduced a random 20-step program to 1–2 steps.

**5. Switch to the fixed version: everything passes.**
```powershell
$env:BANK_VERSION = "fixed"
pytest -v
```
→ 26 passed. Close with the charts in `results/` (chart1 is the key one: 0 vs 6 bugs).

## The six seeded bugs

| Bug | What's wrong in `bank_buggy.py` | Caught by |
|---|---|---|
| BUG-1 | Money stored as `float` (0.1 + 0.2 ≠ 0.3) | round-trip, 2-decimal-places, stateful invariants |
| BUG-2 | `withdraw()` accepts negative amounts (adds money) | negative-withdraw property |
| BUG-3 | Overdraft check uses `int()`, so you can overdraw by < ₹1 | never-negative property, stateful |
| BUG-4 | `transfer()` to the same account creates money | transfer-conserves-total, self-transfer |
| BUG-5 | `apply_interest()` accepts negative rates and truncates | interest-never-decreases, interest-rounding |
| BUG-6 | `deposit()` accepts zero / negative amounts | non-positive-deposit property |
