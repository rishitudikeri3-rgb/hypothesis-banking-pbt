"""
build_demo_page.py - Fills the demo web page (docs/index.html) with real data.

The page's layout lives in docs/index.html. This script only replaces the
JSON inside its <script id="data"> block with data taken from
results/metrics.json and from the source files, so the page always shows the
latest real run. Run it after scripts/run_experiment.py.

Usage: python scripts/build_demo_page.py
"""

import json
import re
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
PAGE = ROOT / "docs" / "index.html"
SUITES = {"example_based": "Example-based", "property_based": "Property-based", "stateful": "Stateful"}
INVARIANTS = ("balances_match_model", "no_negative_balances", "total_money_is_conserved")

# For each bug: a piece of text that identifies the buggy line and the fixed line.
# The script copies the WHOLE matching line from the source file onto the page.
FIX_LINES = [
    ("BUG-1", "self.balance = float(balance)", "return to_decimal(value).quantize(CENT"),
    ("BUG-2", "# BUG-2:", 'raise ValueError("Withdrawal amount must be positive")'),
    ("BUG-3", "if int(amount) > int(self.balance):", "if amount > self.balance:"),
    ("BUG-4", "new_to_balance = to_account.balance + amount", "if to_account is self:"),
    ("BUG-5", "interest = int(self.balance * rate) / 100", "interest = (self.balance * rate / 100).quantize("),
    ("BUG-6", "# BUG-6:", 'raise ValueError("Deposit amount must be positive")'),
]


def plain(text):
    """Decimal('0.01') -> 0.01"""
    return re.sub(r"Decimal\('([^']*)'\)", r"\1", text)


def source_line(filename, snippet):
    """Return the full (stripped) line of src/<filename> that contains snippet."""
    for line in (ROOT / "src" / filename).read_text(encoding="utf-8").splitlines():
        if snippet in line:
            if line.strip().startswith("#"):      # the "line" is a comment that marks a missing check
                return line.strip()
            return line.split("  #")[0].strip()   # drop trailing comments
    raise ValueError(f"{snippet!r} not found in {filename}")


def call_args(counterexample):
    """'test_x(\\n start=0.00,  # comment\\n amount=0.01,\\n)' -> 'start=0.00, amount=0.01'"""
    lines = [l.strip() for l in counterexample.splitlines()[1:]]
    return plain(", ".join(l.split("#")[0].strip().rstrip(",") for l in lines if "=" in l))


def program_steps(counterexample):
    """The rule calls of a shrunk state-machine program, without invariant checks."""
    steps = []
    for line in counterexample.splitlines():
        line = line.strip()
        if line.startswith("state.") and line != "state.teardown()" \
                and not line.startswith(tuple(f"state.{i}" for i in INVARIANTS)):
            steps.append(plain(line.replace("state.", "")).replace("acc_id=", "").replace("amount=", ""))
    return steps


def main():
    m = json.loads((ROOT / "results" / "metrics.json").read_text(encoding="utf-8"))
    buggy, fixed = m["runs"]["buggy"], m["runs"]["fixed"]

    example = [{"name": tb["name"], "buggy": tb["status"], "fixed": tf["status"]}
               for tb, tf in zip(buggy["example_based"]["tests"], fixed["example_based"]["tests"])]

    properties = []
    for i, (tb, tf) in enumerate(zip(buggy["property_based"]["tests"], fixed["property_based"]["tests"]), 1):
        properties.append({
            "id": f"P-{i:02d}",
            "name": tb["name"],
            "description": tb.get("description", ""),
            "strategy": tb.get("strategy", ""),
            "buggy": tb["status"],
            "fixed": tf["status"],
            "examples_fixed": tf["examples_executed"],
            "failures": [{"bugs": f["bugs"], "message": plain(f["message"]),
                          "counterexample": call_args(f["counterexample"])} for f in tb["failures"]],
        })

    # Step 3 zooms in on the overdraft bug (BUG-3)
    hl = next(t for t in buggy["property_based"]["tests"] if t["name"] == "test_balance_never_negative_after_withdraw")
    hl_fail = hl["failures"][0]
    highlight = {
        "description": hl["description"],
        "human_example": "start=100.00, amount=100.00",
        "counterexample": call_args(hl_fail["counterexample"]),
        "message": plain(hl_fail["message"]),
        "generated": hl["hypothesis"]["phases"]["generate"]["passing"] + hl["hypothesis"]["phases"]["generate"]["failing"],
        "buggy_line": source_line("bank_buggy.py", "if int(amount) > int(self.balance):"),
        "fixed_line": source_line("bank_fixed.py", "if amount > self.balance:"),
    }

    st = buggy["stateful"]["tests"][0]
    stateful = {
        "programs": fixed["stateful"]["examples_executed"],
        "max_steps": 20,
        "failures": [{"bugs": f["bugs"],
                      "message": plain(f["message"]).replace("AssertionError: INVARIANT ", ""),
                      "steps": program_steps(f["counterexample"])} for f in st["failures"]],
    }

    suites = [{"key": k, "label": label, "file": buggy[k]["test_file"],
               "fixed_passed": fixed[k]["passed"], "bugs_buggy": len(buggy[k]["bugs_detected"]),
               "cases_fixed": fixed[k]["examples_executed"]} for k, label in SUITES.items()]

    fixes = [{"bug": bug,
              "buggy": source_line("bank_buggy.py", b),
              "fixed": source_line("bank_fixed.py", f)} for bug, b, f in FIX_LINES]

    pbt_bugs = set(buggy["property_based"]["bugs_detected"]) | set(buggy["stateful"]["bugs_detected"])
    data = {
        "seed": m["seed"],
        "generated_at": m["generated_at"],
        "env": m["environment"],
        "bugs": m["bugs"],
        "summary": {
            "n_bugs": len(m["bugs"]),
            "eb_total": buggy["example_based"]["total"],
            "eb_passed_buggy": buggy["example_based"]["passed"],
            "pbt_bugs": len(pbt_bugs),
            "fixed_passed": sum(s["passed"] for s in fixed.values()),
            "fixed_total": sum(s["total"] for s in fixed.values()),
        },
        "example": example,
        "properties": properties,
        "highlight": highlight,
        "stateful": stateful,
        "suites": suites,
        "fixes": fixes,
    }

    blob = json.dumps(data, indent=1).replace("</", "<\\/")   # keep </script> out of the JSON
    page = PAGE.read_text(encoding="utf-8")
    page, count = re.subn(r'(<script id="data" type="application/json">).*?(</script>)',
                          lambda mt: mt.group(1) + blob + mt.group(2), page, flags=re.DOTALL)
    assert count == 1, "data block not found in docs/index.html"
    PAGE.write_text(page, encoding="utf-8")
    print(f"updated {PAGE.relative_to(ROOT)}")


if __name__ == "__main__":
    main()
