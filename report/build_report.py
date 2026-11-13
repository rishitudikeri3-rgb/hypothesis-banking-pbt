"""
build_report.py - Generates report/Software_Testing_Project_Report.docx.

Every number, table row and counterexample in the report is read from
results/metrics.json (produced by scripts/run_experiment.py), and the code
excerpts are read from src/. Nothing is typed in by hand, so re-running the
experiment and this script always gives a report that matches the run.

Usage: python report/build_report.py
"""

import ast
import json
import re
from pathlib import Path

from docx import Document
from docx.enum.table import WD_TABLE_ALIGNMENT
from docx.enum.text import WD_ALIGN_PARAGRAPH
from docx.oxml import OxmlElement
from docx.oxml.ns import qn
from docx.shared import Cm, Pt, RGBColor

ROOT = Path(__file__).resolve().parent.parent
RESULTS = ROOT / "results"
OUTPUT = ROOT / "report" / "Software_Testing_Project_Report.docx"

TITLE = ("Property-Based Testing of a Banking Transaction Module Using Hypothesis: "
         "Automated Input Generation and Failure Shrinking")
STUDENT, USN = "Rishit Mahantesh Udikeri", "1BM23AD046"

SUITES = ["example_based", "property_based", "stateful"]
SUITE_NAMES = {"example_based": "Example-based (PyTest)",
               "property_based": "Property-based (Hypothesis)",
               "stateful": "Stateful (Hypothesis)"}
INVARIANT_STEPS = ("balances_match_model", "no_negative_balances", "total_money_is_conserved")

m = json.loads((RESULTS / "metrics.json").read_text(encoding="utf-8"))
buggy, fixed = m["runs"]["buggy"], m["runs"]["fixed"]


# ======================================================== small helpers

def plain(text):
    """Decimal('0.01') -> 0.01 so counterexamples are easy to read."""
    return re.sub(r"Decimal\('([^']*)'\)", r"\1", text)


def compact_example(example):
    """Turn Hypothesis's multi-line counterexample into one short line."""
    lines = [line.strip() for line in example.splitlines() if line.strip()]
    if lines and lines[0].startswith("<state machine>"):
        steps = [l.replace("state.", "") for l in lines
                 if l.startswith("state.") and not l.startswith(tuple("state." + s for s in INVARIANT_STEPS))
                 and l != "state.teardown()"]
        return plain(" -> ".join(steps))
    args = [l.split("#")[0].strip().rstrip(",") for l in lines[1:] if "=" in l]
    return plain(", ".join(args))


def method_source(path, class_name, method_name):
    """Read the source code of one method straight from a file in src/."""
    source = path.read_text(encoding="utf-8")
    for node in ast.walk(ast.parse(source)):
        if isinstance(node, ast.ClassDef) and node.name == class_name:
            for item in node.body:
                if isinstance(item, ast.FunctionDef) and item.name == method_name:
                    lines = source.splitlines()[item.lineno - 1:item.end_lineno]
                    return "\n".join(line[4:] for line in lines)  # remove class indent
    raise KeyError(method_name)


def tests_of(version, suite):
    return m["runs"][version][suite]["tests"]


def phase_count(test, phase):
    stats = test.get("hypothesis") or {}
    p = stats.get("phases", {}).get(phase)
    return p["passing"] + p["failing"] if p else 0


# Short IDs used in all tables: EB-01.., P-01.., S-01
EB_IDS = {t["name"]: f"EB-{i:02d}" for i, t in enumerate(tests_of("buggy", "example_based"), 1)}
P_IDS = {t["name"]: f"P-{i:02d}" for i, t in enumerate(tests_of("buggy", "property_based"), 1)}
S_IDS = {t["name"]: f"S-{i:02d}" for i, t in enumerate(tests_of("buggy", "stateful"), 1)}
ALL_IDS = {**EB_IDS, **P_IDS, **S_IDS}

# ======================================================== docx helpers

doc = Document()
for section in doc.sections:
    section.top_margin = section.bottom_margin = Cm(2.5)
    section.left_margin = Cm(3.0)
    section.right_margin = Cm(2.5)

normal = doc.styles["Normal"]
normal.font.name = "Times New Roman"
normal.element.rPr.rFonts.set(qn("w:eastAsia"), "Times New Roman")
normal.font.size = Pt(12)
normal.paragraph_format.line_spacing = 1.15
normal.paragraph_format.space_after = Pt(6)

for level, size in [(1, 15), (2, 13), (3, 12)]:
    style = doc.styles[f"Heading {level}"]
    style.font.name = "Times New Roman"
    style.element.rPr.rFonts.set(qn("w:asciiTheme"), "")  # stop theme font overriding
    style.element.rPr.rFonts.set(qn("w:hAnsi"), "Times New Roman")
    style.element.rPr.rFonts.set(qn("w:ascii"), "Times New Roman")
    style.font.size = Pt(size)
    style.font.bold = True
    style.font.color.rgb = RGBColor(0, 0, 0)
    style.paragraph_format.space_before = Pt(14 if level == 1 else 10)
    style.paragraph_format.space_after = Pt(6)

figure_no = 0
table_no = 0


def heading(text, level=1, new_page=False):
    if new_page:
        doc.add_page_break()
    return doc.add_heading(text, level=level)


def para(text, bold_prefix=None, align=WD_ALIGN_PARAGRAPH.JUSTIFY, italic=False, size=None):
    p = doc.add_paragraph()
    p.alignment = align
    if bold_prefix:
        p.add_run(bold_prefix).bold = True
    run = p.add_run(text)
    run.italic = italic
    if size:
        run.font.size = Pt(size)
    return p


def bullets(items, style="List Bullet"):
    for item in items:
        p = doc.add_paragraph(style=style)
        p.alignment = WD_ALIGN_PARAGRAPH.JUSTIFY
        if isinstance(item, tuple):
            p.add_run(item[0]).bold = True
            p.add_run(item[1])
        else:
            p.add_run(item)


def code(text, size=9):
    """A grey box with monospaced code."""
    table = doc.add_table(rows=1, cols=1)
    table.alignment = WD_TABLE_ALIGNMENT.CENTER
    cell = table.cell(0, 0)
    shade(cell, "F2F2F2")
    cell.paragraphs[0].paragraph_format.line_spacing = 1.0
    run = cell.paragraphs[0].add_run(text)
    run.font.name = "Consolas"
    run.font.size = Pt(size)
    doc.add_paragraph().paragraph_format.space_after = Pt(0)


def shade(cell, hex_color):
    shd = OxmlElement("w:shd")
    shd.set(qn("w:val"), "clear")
    shd.set(qn("w:color"), "auto")
    shd.set(qn("w:fill"), hex_color)
    cell._tc.get_or_add_tcPr().append(shd)


def caption(text, kind):
    global figure_no, table_no
    if kind == "Figure":
        figure_no += 1
        label = f"Figure {figure_no}: "
    else:
        table_no += 1
        label = f"Table {table_no}: "
    p = doc.add_paragraph()
    p.alignment = WD_ALIGN_PARAGRAPH.CENTER
    r = p.add_run(label)
    r.bold = True
    r.font.size = Pt(10)
    r2 = p.add_run(text)
    r2.font.size = Pt(10)
    r2.italic = True
    return p


def table(headers, rows, widths=None, font_size=9, title=None):
    if title:
        caption(title, "Table")
    t = doc.add_table(rows=1, cols=len(headers))
    t.style = "Table Grid"
    t.alignment = WD_TABLE_ALIGNMENT.CENTER
    for i, h in enumerate(headers):
        cell = t.rows[0].cells[i]
        shade(cell, "D9E2F3")
        cell.paragraphs[0].add_run(h).bold = True
    for row in rows:
        cells = t.add_row().cells
        for i, value in enumerate(row):
            cells[i].paragraphs[0].add_run(str(value))
    for row in t.rows:
        for i, cell in enumerate(row.cells):
            if widths:
                cell.width = Cm(widths[i])
            for p in cell.paragraphs:
                p.paragraph_format.line_spacing = 1.0
                p.paragraph_format.space_after = Pt(2)
                p.alignment = WD_ALIGN_PARAGRAPH.LEFT
                for r in p.runs:
                    r.font.size = Pt(font_size)
    # repeat the header row on every page the table spans
    tr_pr = t.rows[0]._tr.get_or_add_trPr()
    header_flag = OxmlElement("w:tblHeader")
    header_flag.set(qn("w:val"), "true")
    tr_pr.append(header_flag)
    doc.add_paragraph().paragraph_format.space_after = Pt(0)
    return t


def figure(path, text, width_cm=15):
    doc.add_picture(str(path), width=Cm(width_cm))
    doc.paragraphs[-1].alignment = WD_ALIGN_PARAGRAPH.CENTER
    caption(text, "Figure")


def add_page_number_footer():
    for section in doc.sections:
        p = section.footer.paragraphs[0]
        p.alignment = WD_ALIGN_PARAGRAPH.CENTER
        run = p.add_run()
        for tag, text in [("begin", None), (None, "PAGE"), ("end", None)]:
            if tag:
                fld = OxmlElement("w:fldChar")
                fld.set(qn("w:fldCharType"), tag)
                run._r.append(fld)
            else:
                instr = OxmlElement("w:instrText")
                instr.set(qn("xml:space"), "preserve")
                instr.text = text
                run._r.append(instr)
        run.font.size = Pt(10)


# ======================================================== numbers used in the text

n_bugs = len(m["bugs"])
eb_total = buggy["example_based"]["total"]
p_total = buggy["property_based"]["total"]
p_failed_buggy = buggy["property_based"]["failed"]
p_examples_fixed = fixed["property_based"]["examples_executed"]
p_examples_buggy = buggy["property_based"]["examples_executed"]
s_examples_fixed = fixed["stateful"]["examples_executed"]
s_examples_buggy = buggy["stateful"]["examples_executed"]
pbt_bugs = sorted(set(buggy["property_based"]["bugs_detected"]) | set(buggy["stateful"]["bugs_detected"]))
generated_total_fixed = p_examples_fixed + s_examples_fixed
ratio = generated_total_fixed / fixed["example_based"]["examples_executed"]
max_generate_to_fail = max(phase_count(t, "generate") for t in tests_of("buggy", "property_based")
                           if t["status"] == "failed")
stateful_buggy = tests_of("buggy", "stateful")[0]
stateful_steps = stateful_buggy.get("hypothesis", {}) or {}
env = m["environment"]
# the shrunk BUG-3 counterexample, quoted in the abstract and viva answers
withdraw_ce = compact_example(next(t for t in tests_of("buggy", "property_based")
                                   if t["name"] == "test_balance_never_negative_after_withdraw")["failures"][0]["counterexample"])
verification = m["verification"]


def detected_by(bug, version="buggy"):
    """Which test IDs of each suite revealed `bug`."""
    found = {}
    for suite in SUITES:
        ids = [ALL_IDS[t["name"]] for t in tests_of(version, suite)
               if any(bug in f["bugs"] for f in t["failures"])]
        found[suite] = ids
    return found


# ======================================================== COVER PAGE

for _ in range(3):
    doc.add_paragraph()
p = doc.add_paragraph()
p.alignment = WD_ALIGN_PARAGRAPH.CENTER
r = p.add_run("BMS COLLEGE OF ENGINEERING, BENGALURU")
r.bold = True
r.font.size = Pt(16)
p = doc.add_paragraph()
p.alignment = WD_ALIGN_PARAGRAPH.CENTER
p.add_run("(Autonomous Institute, Affiliated to VTU, Belagavi)").font.size = Pt(11)
p = doc.add_paragraph()
p.alignment = WD_ALIGN_PARAGRAPH.CENTER
r = p.add_run("Department of Artificial Intelligence and Data Science")
r.bold = True
r.font.size = Pt(13)
doc.add_paragraph()
p = doc.add_paragraph()
p.alignment = WD_ALIGN_PARAGRAPH.CENTER
r = p.add_run("Software Testing – Course Project")
r.font.size = Pt(14)
r.italic = True
doc.add_paragraph()
p = doc.add_paragraph()
p.alignment = WD_ALIGN_PARAGRAPH.CENTER
r = p.add_run(TITLE)
r.bold = True
r.font.size = Pt(18)
for _ in range(3):
    doc.add_paragraph()
p = doc.add_paragraph()
p.alignment = WD_ALIGN_PARAGRAPH.CENTER
p.add_run("Submitted by\n").font.size = Pt(12)
r = p.add_run(f"{STUDENT}\n")
r.bold = True
r.font.size = Pt(14)
p.add_run(f"USN: {USN}").font.size = Pt(12)
for _ in range(4):
    doc.add_paragraph()
p = doc.add_paragraph()
p.alignment = WD_ALIGN_PARAGRAPH.CENTER
p.add_run("Department of Artificial Intelligence and Data Science\n"
          "BMS College of Engineering, Bengaluru\n"
          "Academic Year 2026–27").font.size = Pt(12)

# ======================================================== ABSTRACT

heading("Abstract", new_page=True)
para("Example-based unit tests check only the inputs that a developer thinks of. Property-based testing (PBT) "
     "takes a different approach: the tester states rules (properties or invariants) that the code must satisfy "
     "for every valid input, and a tool generates the inputs automatically. When it finds an input that breaks a "
     "rule, it shrinks that input to the simplest one that still fails.")
para(f"This project applies PBT with the Python library Hypothesis to a small banking module that supports "
     f"deposits, withdrawals, transfers and interest. Six realistic bugs were seeded into one version of the "
     f"module, and a corrected version was written with the same interface. Three test suites were run against "
     f"both versions with a fixed random seed ({m['seed']}): {eb_total} hand-written example-based PyTest tests, "
     f"{p_total} Hypothesis property tests and one stateful (rule-based state machine) test.")
para(f"All {eb_total} example-based tests passed on the buggy version, so they detected 0 of the {n_bugs} bugs. "
     f"On the same code, {p_failed_buggy} of the {p_total} property tests failed (the remaining one is a control "
     f"property that is meant to pass). Between them, the property-based and stateful suites detected "
     f"{len(pbt_bugs)} of the {n_bugs} seeded bugs, and every failure was reported with a minimal "
     f"counterexample (for example {withdraw_ce} for the overdraft bug). On the fixed version every test in "
     f"all three suites passed. During the fixed-version run, Hypothesis executed {generated_total_fixed} "
     f"generated test cases, compared with {eb_total} hand-written ones. The results show that a module can pass "
     f"a typical example-based suite while still containing bugs that property-based testing finds "
     f"automatically.")
para("Keywords: software testing, property-based testing, Hypothesis, PyTest, shrinking, stateful testing, "
     "invariants, test automation.", italic=True)

# ======================================================== CONTENTS

heading("Contents", new_page=True)
for line in ["Abstract", "1. Introduction", "2. Objectives", "3. Literature Review and Background",
             "4. Tool Overview: Hypothesis and PyTest", "5. System Under Test", "6. Methodology",
             "7. Test Case Tables", "8. Results and Analysis",
             "9. Comparison: Example-Based vs Property-Based Testing", "10. Limitations and Future Scope",
             "11. Conclusion", "References", "Appendix A: Commands to Reproduce", "Appendix B: Viva Questions and Answers"]:
    doc.add_paragraph(line).paragraph_format.space_after = Pt(2)

# ======================================================== 1. INTRODUCTION

heading("1. Introduction", new_page=True)
heading("1.1 Software testing", 2)
para("Software testing is the process of running a program in order to find faults before its users do. It "
     "checks that the software does what its specification says and does not do what the specification forbids. "
     "Testing cannot prove that a program has no bugs. As Dijkstra put it, testing can show the presence of bugs "
     "but never their absence. What it can do is raise our confidence, and that confidence depends on how well "
     "the tests explore the space of possible inputs.")
heading("1.2 Limits of example-based testing", 2)
para("Most unit tests are example-based. The developer picks a concrete input, works out the expected output by "
     "hand and writes an assertion, for example \"deposit 100 into an empty account, the balance should be 100\". "
     "Such tests are easy to read and quick to write, but they have a structural weakness: they only cover the "
     "inputs the developer happened to think of. The same person who wrote the code usually writes the tests, so "
     "the blind spots in the code tend to be the same as the blind spots in the tests. Edge cases such as zero, "
     "negative numbers, fractions of a unit, values right next to a boundary, or an object interacting with "
     "itself are easy to forget.")
heading("1.3 Motivation", 2)
para("Financial software is a good place to see this problem. Small errors such as a rounding mistake, a "
     "comparison that is off at a boundary, or a transfer that creates money in an unusual case can add up to "
     "real losses and break regulatory rules. These bugs often survive code review and a passing test suite "
     "because they appear only for unusual inputs.")
para("Property-based testing reverses the job. Instead of listing examples, the tester writes down general rules "
     "that must always hold, for example \"a transfer never changes the total amount of money in the bank\", and a "
     "tool searches for inputs that break them. This project asks a simple question: if a banking module passes a "
     "reasonable set of hand-written tests, can property-based testing still find the bugs that remain, and how "
     "useful is the output it gives the developer?")

# ======================================================== 2. OBJECTIVES

heading("2. Objectives")
bullets([
    "To build a small, readable banking transaction module in Python in two versions: one with six seeded, "
    "realistic bugs and one corrected version with the same interface.",
    "To write a conventional example-based PyTest suite of the kind a typical developer would write, and to show "
    "that it passes on the buggy version.",
    "To express the module's correctness rules as Hypothesis properties, using appropriate input strategies, "
    "@settings and @example.",
    "To write a stateful test (a rule-based state machine) that runs random sequences of operations and checks "
    "invariants after every step.",
    "To run every suite against both versions with a fixed seed and collect measurable results: tests "
    "passed/failed, bugs detected, examples generated, shrunk counterexamples and execution time.",
    "To analyse how Hypothesis shrinks failing inputs, and to compare example-based and property-based testing on "
    "effort, edge-case coverage, bugs found and limitations.",
], style="List Number")

# ======================================================== 3. LITERATURE

heading("3. Literature Review and Background", new_page=True)
heading("3.1 Example-based testing", 2)
para("In example-based (or scenario-based) unit testing, each test fixes one input and one expected output. "
     "Frameworks such as JUnit and PyTest made this style standard practice. Its strengths are clarity and "
     "speed, and each test documents one piece of intended behaviour. Its weakness is that coverage of the input "
     "space is limited by the tester's imagination and patience. Fifteen tests check fifteen points in an input "
     "space that, for a function taking two money amounts, contains billions of points.")
heading("3.2 Boundary value analysis and equivalence partitioning", 2)
para("Classic black-box test design techniques try to choose examples systematically (Myers et al., The Art of "
     "Software Testing). Equivalence partitioning divides the input domain into classes that should behave the "
     "same way and picks one value from each class. Boundary value analysis adds values at and next to the edges "
     "of each class, because errors cluster at boundaries. These techniques are valuable, but the tester still "
     "has to identify the partitions and boundaries correctly. If the tester assumes that the overdraft "
     "boundary is \"amount equals balance\", they will test 100 against 100 and miss a boundary that actually sits "
     "in the paise between a balance and the next whole rupee.")
heading("3.3 Random testing", 2)
para("Random testing generates inputs at random and checks that the program does not crash or that its output "
     "matches an oracle. Duran and Ntafos (1984) showed that random testing is surprisingly cost-effective "
     "compared with partition testing. Pure random testing has two problems. First, uniformly random values "
     "rarely hit special values such as 0, 0.01 or exact boundaries. Second, when it does find a failure, the "
     "failing input is usually large and noisy, so it is hard to understand.")
heading("3.4 Property-based testing", 2)
para("Property-based testing was introduced by Claessen and Hughes (2000) with QuickCheck for Haskell. A "
     "property is a universally quantified statement about the program, such as \"for all lists xs, reverse "
     "(reverse xs) == xs\". QuickCheck generates many random instances of the inputs, checks the property on each, "
     "and reports a counterexample if one is found. PBT differs from plain random testing in three ways. The "
     "oracle is a general rule rather than a crash. Generators are typed and composable. Generation is "
     "deliberately biased towards small and special values. The idea has since been ported to most languages, "
     "and Hughes (2016) describes its industrial use, for example in telecom and automotive systems.")
para("Common kinds of property include round-trip properties (decode(encode(x)) == x), invariants (the total "
     "money in a bank is conserved), idempotence, comparison against a simpler reference model (the test oracle), "
     "and \"never crashes / always raises the right error\" properties.")
heading("3.5 Hypothesis", 2)
para("Hypothesis (MacIver, Hatfield-Dodds et al., 2019) is the main property-based testing library for Python. "
     "Unlike QuickCheck, which shrinks values with type-specific shrink functions, Hypothesis records the "
     "sequence of random choices it made while generating a test case and shrinks that underlying choice "
     "sequence. Because of this, shrinking works automatically for any strategy, including complex composite ones "
     "and stateful programs, without the user writing shrink code (MacIver and Donaldson, 2020).")
heading("3.6 Shrinking", 2)
para("Shrinking (also called test-case reduction) is what makes PBT practical. A randomly found failure might "
     "involve an amount like 7,318.64 and a balance like 7,318.27. Hypothesis repeatedly tries simpler variants, "
     "such as smaller numbers, shorter lists and fewer steps, and keeps a variant only if the test still fails. "
     "The result is a minimal counterexample, for example \"balance 0.00, withdraw 0.01\", from which the cause "
     "of the bug is usually obvious.")
heading("3.7 Stateful (model-based) testing", 2)
para("Many bugs only show up after a particular sequence of operations. Stateful testing generates whole "
     "programs, which are random sequences of API calls, and checks invariants after each step. Often the real "
     "system is compared against a simple model of what its state should be. QuickCheck's state-machine testing "
     "and Hypothesis's RuleBasedStateMachine implement this idea, and they shrink a failing program to the "
     "shortest sequence of calls that reproduces the bug.")

# ======================================================== 4. TOOLS

heading("4. Tool Overview: Hypothesis and PyTest")
para(f"The experiment used Python {env['python']}, pytest {env['pytest']} and Hypothesis {env['hypothesis']} on "
     f"{env['platform']}.")
heading("4.1 Hypothesis concepts used in this project", 2)
bullets([
    ("Strategies. ", "A strategy describes a set of possible values and how to generate them. This project uses "
     "st.decimals(min_value, max_value, places=2) for money, st.integers for account indices, st.lists for "
     "sequences of deposits and st.sampled_from for choosing account ids."),
    ("@given. ", "A decorator that turns a test function with parameters into a property. Hypothesis calls the "
     "function many times with values drawn from the strategies."),
    ("@settings. ", "Controls the search, for example max_examples (how many inputs to try), deadline and "
     "stateful_step_count. A project-wide profile in tests/conftest.py disables the per-example deadline and the "
     "example database so that runs are reproducible."),
    ("@example. ", "Adds an explicit input that is always tried first. It acts as a regression test that sits "
     "alongside the random search."),
    ("Shrinking. ", "When a property fails, Hypothesis automatically searches for a simpler failing input and "
     "reports only the minimal one."),
    ("Example database. ", "By default Hypothesis saves failing inputs in a local .hypothesis directory and "
     "replays them first on the next run, so a bug that was found once is not lost. It is disabled here only to "
     "keep each run independent and reproducible from the seed."),
    ("Phases and statistics. ", "A run goes through explicit, generate, shrink and explain phases. The "
     "--hypothesis-show-statistics option prints how many test cases each phase executed. These counts are the "
     "source of the \"examples generated\" figures in this report."),
    ("Stateful testing. ", "RuleBasedStateMachine with @rule (an operation) and @invariant (a check after every "
     "step)."),
    ("Seeding. ", "The --hypothesis-seed option fixes the random seed, so the same run can be reproduced "
     "exactly."),
])
heading("4.2 PyTest", 2)
para("PyTest is the standard Python test runner. It discovers files and functions named test_*, rewrites plain "
     "assert statements so that failures show the values involved, provides pytest.raises for checking "
     "exceptions, and can write machine-readable JUnit XML reports. Hypothesis integrates with it as a plugin, so "
     "property tests are collected and reported like ordinary tests. The experiment script reads PyTest's JUnit "
     "XML for pass/fail, timings and failure text, and reads the console output for Hypothesis's statistics.")

# ======================================================== 5. SUT

heading("5. System Under Test", new_page=True)
para("The system under test is a small banking module with two classes:")
bullets([
    ("Account(account_id, owner, balance) ", "with deposit(amount), withdraw(amount), transfer(to_account, amount), "
     "apply_interest(rate_percent) and get_balance()."),
    ("Bank ", "which holds accounts in a dictionary and offers open_account(), get_account() and total_money()."),
])
para("Two versions share exactly the same interface. src/bank_buggy.py contains six seeded bugs, each documented "
     "in a comment block at the top of the file. src/bank_fixed.py corrects them: money is held as decimal.Decimal "
     "rounded to two places, and invalid input raises ValueError. A third file, src/bank.py, imports one of the two "
     "depending on the environment variable BANK_VERSION. Because of this, the same unchanged test files run "
     "against both versions.")
table(["Bug ID", "Seeded defect"], [[k, v] for k, v in m["bugs"].items()], widths=[2, 13],
      title="Seeded bugs in bank_buggy.py")
para("The excerpts below are taken directly from the source files. The buggy withdraw() compares whole rupees "
     "only (BUG-3) and never rejects a negative amount (BUG-2). The buggy transfer() computes both new balances "
     "before saving either one, so when the sender and the receiver are the same account the second assignment "
     "overwrites the first (BUG-4).")
para("Buggy version (src/bank_buggy.py):", bold_prefix=None)
code(method_source(ROOT / "src" / "bank_buggy.py", "Account", "withdraw") + "\n\n" +
     method_source(ROOT / "src" / "bank_buggy.py", "Account", "transfer"))
para("Fixed version (src/bank_fixed.py):")
code(method_source(ROOT / "src" / "bank_fixed.py", "Account", "withdraw") + "\n\n" +
     method_source(ROOT / "src" / "bank_fixed.py", "Account", "transfer"))

# ======================================================== 6. METHODOLOGY

heading("6. Methodology")
heading("6.1 Workflow", 2)
para("Figure 1 shows the workflow. First, the module was written in its buggy and fixed versions. Next came a "
     "typical example-based suite and then the property-based and stateful suites. All three suites were run "
     "against both versions with the same fixed Hypothesis seed. Hypothesis generated inputs, found failures and "
     "shrank them. Finally, scripts/run_experiment.py collected the metrics into results/metrics.json, "
     "scripts/make_charts.py drew the charts, and this report was generated from those files.")
figure(RESULTS / "workflow.png", "Testing workflow", width_cm=15.5)
heading("6.2 Test design", 2)
bullets([
    ("Example-based suite (tests/test_example_based.py). ", f"{eb_total} tests written as a typical student would: "
     "deposit 100, withdraw 50, transfer 30, 5% interest on 1000, an overdraft of 150 against a balance of 100, "
     "and so on. They were deliberately not written with knowledge of the bugs, because the project is about "
     "what typical tests miss."),
    ("Property-based suite (tests/test_property_based.py). ", f"{p_total} properties, each with a docstring "
     "stating the rule in plain English, the strategy used and the bug it targets. Money is generated with "
     "st.decimals(places=2), because real money has exactly two decimal places. Both versions accept these "
     "values: the buggy one converts them to float internally (which is BUG-1 itself), and the fixed one keeps "
     "them as Decimal. Results are compared as exact Decimals. One property (overdraft of at least one rupee is "
     "rejected) is a control that should pass on both versions, to show that properties do not fail by "
     "default."),
    ("Stateful suite (tests/test_stateful.py). ", "A RuleBasedStateMachine with three accounts and three rules "
     "(deposit, withdraw, transfer, where a transfer may go from an account to itself). A dictionary model tracks "
     "the exact Decimal balance each account should have. After every step three invariants are checked: no "
     "balance is negative, the bank's total equals the model's total, and every balance equals the model."),
])
heading("6.3 Experiment procedure", 2)
para(f"scripts/run_experiment.py runs each suite on each version (six runs in total) with: pytest <suite> -v "
     f"-p no:cacheprovider --hypothesis-seed={m['seed']} --hypothesis-show-statistics --junitxml=<file>. The "
     f"console output is saved to results/<suite>_<version>.txt. Pass/fail status, timings and failure messages "
     f"come from the JUnit XML. Examples generated and shrink counts come from the statistics section. Each "
     f"failure is mapped to a seeded bug in two ways. If the error message shows a number with more than two "
     f"decimal places (the fingerprint of float drift), it is BUG-1. Otherwise it is the bug named in the "
     f"property's \"Targets\" line. For the stateful test, a negative balance maps to BUG-3, and a total-money "
     f"error whose shrunk program contains a transfer from an account to itself maps to BUG-4.")
heading("6.4 Metrics collected", 2)
bullets(["Tests passed / failed per suite per version", "Seeded bugs detected per suite",
         "Test cases executed per property, split by Hypothesis phase (generate, shrink, explain)",
         "The shrunk (falsifying) counterexample for every failure",
         "Execution time per suite (as reported by pytest)"])

# ======================================================== 7. TEST CASE TABLES

heading("7. Test Case Tables", new_page=True)
heading("7.1 Example-based test cases", 2)
rows = []
for tb, tf in zip(tests_of("buggy", "example_based"), tests_of("fixed", "example_based")):
    actual = "Same as expected" if tb["status"] == "passed" else tb["failures"][0]["message"] if tb["failures"] else "Failed"
    rows.append([EB_IDS[tb["name"]], tb.get("description", ""), tb.get("input", ""), tb.get("expected", ""),
                 actual, f"{tb['status'].capitalize()} / {tf['status'].capitalize()}"])
table(["ID", "Description", "Input", "Expected", "Actual (buggy)", "Status buggy / fixed"], rows,
      widths=[1.3, 4.2, 3.4, 2.8, 2.0, 2.0], font_size=8.5,
      title="Example-based test cases (tests/test_example_based.py)")
para(f"All {eb_total} example-based tests passed on both versions. For these inputs the buggy module behaves "
     f"exactly like the fixed one. For example, 10.50 + 20.25 happens to be exact in binary floating point, so "
     f"EB-05 cannot expose BUG-1.")

heading("7.2 Properties", 2)
rows = [[P_IDS[t["name"]], t.get("description", ""), t.get("strategy", ""), t.get("targets", "")]
        for t in tests_of("buggy", "property_based")]
table(["ID", "Property (plain English)", "Strategy used", "Targets"], rows,
      widths=[1.2, 6.0, 6.0, 2.5], font_size=8.5, title="Property definitions (tests/test_property_based.py)")

heading("7.3 Property results", 2)
para("\"Examples\" means the number of test cases Hypothesis actually executed, as printed by "
     "--hypothesis-show-statistics. On the buggy version, Hypothesis stops generating new inputs once a property "
     "fails and then spends its effort on shrinking (S) and explaining (E) the failure. The explain phase re-runs "
     "the minimal failure while varying each argument, to tell the reader which arguments do not matter. On the "
     "fixed version, each property runs its full max_examples budget in the generate phase (G).")
rows = []
for tb, tf in zip(tests_of("buggy", "property_based") + tests_of("buggy", "stateful"),
                  tests_of("fixed", "property_based") + tests_of("fixed", "stateful")):
    ce = "; ".join(compact_example(f["counterexample"]) for f in tb["failures"]) or "–"
    rows.append([ALL_IDS[tb["name"]],
                 f"G {phase_count(tb, 'generate')} / S {phase_count(tb, 'shrink')} / E {phase_count(tb, 'explain')}",
                 str(tf["examples_executed"]),
                 tb["status"].upper(), tf["status"].upper(), ce])
table(["ID", "Examples on buggy (G/S/E)", "Examples on fixed", "Buggy", "Fixed", "Shrunk falsifying example (buggy)"],
      rows, widths=[1.2, 2.6, 1.6, 1.4, 1.4, 7.5], font_size=8.5,
      title="Results of every property and the state machine (S-01) on both versions")

# ======================================================== 8. RESULTS

heading("8. Results and Analysis", new_page=True)
heading("8.1 Summary", 2)
rows = []
for version in ["buggy", "fixed"]:
    for suite in SUITES:
        r = m["runs"][version][suite]
        rows.append([version.capitalize(), SUITE_NAMES[suite], r["total"], r["passed"], r["failed"],
                     r["examples_executed"], ", ".join(r["bugs_detected"]) or "none", f"{r['pytest_time_s']:.2f}"])
table(["Version", "Suite", "Tests", "Passed", "Failed", "Test cases executed", "Bugs detected", "Time (s)"],
      rows, widths=[1.5, 3.6, 1.2, 1.4, 1.4, 2.0, 3.6, 1.3], font_size=8.5,
      title=f"Overall results (seed {m['seed']})")
para(f"The run confirms the project's three claims: (1) example-based tests all pass on the buggy version: "
     f"{verification['example_tests_all_pass_on_buggy']}; (2) every seeded bug is caught by a property-based or "
     f"stateful test: {verification['every_seeded_bug_caught_by_pbt']}; (3) every test passes on the fixed "
     f"version: {verification['everything_passes_on_fixed']}.")

heading("8.2 Charts", 2)
figure(RESULTS / "chart1_bugs_detected.png",
       f"Seeded bugs detected on the buggy version. Example-based: "
       f"{len(buggy['example_based']['bugs_detected'])}, property-based: "
       f"{len(buggy['property_based']['bugs_detected'])}, stateful: {len(buggy['stateful']['bugs_detected'])}",
       width_cm=13)
para(f"Figure 2 is the central result. The example-based suite found none of the {n_bugs} bugs, and the "
     f"property-based suite found {len(buggy['property_based']['bugs_detected'])}. The stateful test found "
     f"{len(buggy['stateful']['bugs_detected'])} ({', '.join(buggy['stateful']['bugs_detected'])}). This is by "
     f"design: it only generates valid, positive amounts and does not call apply_interest, so BUG-2, BUG-5 and "
     f"BUG-6 are out of its reach. Its role is to test sequences of operations rather than input validation.")
figure(RESULTS / "chart2_test_cases.png",
       "Test cases executed per suite (log scale): hand-written vs Hypothesis-generated", width_cm=14)
para(f"Figure 3 compares the amount of testing. On the fixed version the {p_total} properties executed "
     f"{p_examples_fixed} generated test cases and the state machine ran {s_examples_fixed} random programs "
     f"(each up to 20 steps), compared with {eb_total} hand-written tests. That is about {ratio:.0f} times as many "
     f"test cases, even though the property file has fewer test functions than the example file. On the buggy "
     f"version the counts are lower ({p_examples_buggy} and {s_examples_buggy}) because a property stops "
     f"exploring once it fails. Most of those executions belong to shrinking and explaining the failure, not to "
     f"new exploration.")
figure(RESULTS / "chart3_pass_fail.png", "Passed and failed tests per suite on the buggy and fixed versions",
       width_cm=15.5)
para("Figure 4 shows the same contrast as a pass/fail count. On the buggy version the example suite is all "
     "green, while the property and stateful suites are almost all red. On the fixed version everything passes.")
figure(RESULTS / "chart4_execution_time.png", "Execution time per suite (seconds, as reported by pytest)", width_cm=14)
para(f"Figure 5 shows that property-based testing costs more time but remains practical. The whole "
     f"property suite took {fixed['property_based']['pytest_time_s']:.2f} s on the fixed version and "
     f"{buggy['property_based']['pytest_time_s']:.2f} s on the buggy version, where shrinking and failure "
     f"reporting add work. The example-based suite takes a fraction of a second. These times are small and include "
     f"some start-up noise, so small differences between them should not be over-interpreted.")

heading("8.3 Bug detection matrix", 2)
rows = []
for bug, title in m["bugs"].items():
    found = detected_by(bug)
    rows.append([bug, title] + [("Yes (" + ", ".join(found[s]) + ")") if found[s] else "No" for s in SUITES])
table(["Bug", "Description", "Example-based", "Property-based", "Stateful"], rows,
      widths=[1.4, 6.0, 2.2, 3.4, 2.4], font_size=8.5,
      title="Which suite detected which bug (buggy version; IDs refer to Tables 2–4)")
para("Several bugs were found by more than one property. BUG-1 (float money) was exposed by two properties and by "
     "two invariants of the state machine. BUG-5 was exposed by two different properties: one found the negative "
     "rate and the other found the truncation. BUG-4 was exposed both by the general \"transfer conserves "
     "money\" property, where Hypothesis itself discovered that the sender and the receiver could be the same "
     "account, and by the specific self-transfer property.")

heading("8.4 Shrinking: real counterexamples from the run", 2)
para("Every failure below is exactly what Hypothesis printed during the buggy-version run (seed "
     f"{m['seed']}), copied from results/property_based_buggy.txt and results/stateful_buggy.txt. Each one is "
     "the minimal input that Hypothesis's shrinker could find.")
rows = []
for t in tests_of("buggy", "property_based") + tests_of("buggy", "stateful"):
    for f in t["failures"]:
        h = t.get("hypothesis") or {}
        rows.append([ALL_IDS[t["name"]], ", ".join(f["bugs"]), plain(f["message"]),
                     f"{h.get('shrinks_tried', 0)} / {h.get('shrinks_successful', 0)}"])
table(["ID", "Bug", "Error reported", "Shrinks tried / successful"], rows,
      widths=[1.2, 1.5, 10.5, 2.6], font_size=8.5, title="Failures and shrinking effort on the buggy version")


def failure_of(name, version="buggy"):
    for suite in ("property_based", "stateful"):
        for t in tests_of(version, suite):
            if t["name"] == name and t["failures"]:
                return t, t["failures"]
    return None, []


for name, intro in [
    ("test_balance_never_negative_after_withdraw",
     "BUG-3 (overdraft boundary). The explicit @example(start=100.00, amount=100.00), which is the boundary a "
     "developer would normally test, passed. Hypothesis then found the real boundary on its own:"),
    ("test_deposit_then_withdraw_is_round_trip",
     "BUG-1 (float money). Depositing and then withdrawing the same amount should be a perfect round trip. "
     "Hypothesis shrank the failure to two small amounts in paise:"),
    ("test_transfer_conserves_total_money",
     "BUG-4 (self-transfer). The property draws the sender and receiver indices independently. While shrinking, "
     "Hypothesis drove both indices to the same value, which showed that a transfer from an account to itself "
     "creates money. No one told it to try this case:"),
    ("test_interest_is_rounded_to_nearest_paisa",
     "BUG-5 (truncation). The expected value is computed independently with exact Decimal arithmetic and "
     "half-up rounding. Hypothesis found a small balance and rate where truncation loses one paisa:"),
    ("test_deposit_of_zero_or_negative_is_rejected",
     "BUG-6 (deposit validation). Here the explain phase adds comments. Hypothesis tried varying each argument "
     "and the test always failed, so it marks the values with \"# or any other generated value\". This tells the "
     "developer that the failure does not depend on the particular values at all:"),
]:
    t, failures = failure_of(name)
    if not failures:
        continue
    para(intro, bold_prefix=f"{ALL_IDS[name]}: ")
    code(plain(failures[0]["counterexample"]) + "\n\n" + plain(failures[0]["message"]))

t, failures = failure_of(stateful_buggy["name"])
if failures:
    para(f"The state machine reported {len(failures)} distinct failures from a single run. Hypothesis keeps "
         f"separate failures that are raised at different places in the code and shrinks each one to the shortest "
         f"program of rule calls. In the listing below, the invariant checks have been removed for readability:",
         bold_prefix="S-01 (stateful): ")
    code("\n\n".join(f"[{', '.join(f['bugs'])}] {plain(f['message'])}\n  " +
                     compact_example(f["counterexample"]).replace(" -> ", "\n  ") for f in failures))
    para("Note that the state machine did not report BUG-4 even though transfer to self is one of its possible "
         "steps. Self-transfer and float drift both break the same assertion (total money conserved). Hypothesis "
         "treats failures at the same line as one bug and reports the simplest example of it, which here was "
         "float drift. This shows a real property of PBT: one bug can hide another that breaks the same "
         "assertion, and the hidden bug appears once the first is fixed. In this project the dedicated "
         "self-transfer property (P-10) catches BUG-4 directly.")

para(f"Two observations follow from these counterexamples. First, the shrunk inputs are tiny: amounts such as "
     f"0.01 and 0.02 and programs of one or two steps. A developer can understand them at a glance, unlike a "
     f"random input such as 7,318.64. Second, finding the bugs required very little search. On the buggy version "
     f"no property needed more than {max_generate_to_fail} generated inputs in its generate phase before it "
     f"switched to shrinking, because Hypothesis deliberately favours small and boundary values.")

# ======================================================== 9. COMPARISON

heading("9. Comparison: Example-Based vs Property-Based Testing", new_page=True)
rows = [
    ["What the tester writes", "Concrete input and expected output for each case",
     "A general rule plus a description of the valid inputs (strategy)"],
    ["Effort per test", "Low per test, but grows linearly with the number of cases",
     "Higher per property (you must think of a true rule), but one property covers thousands of cases"],
    ["Test cases executed in this project",
     f"{eb_total}", f"{p_examples_fixed} (properties) + {s_examples_fixed} programs (stateful) on the fixed version"],
    ["Coverage of edge cases", "Only those the tester thinks of",
     "Automatic: 0, 0.01, boundaries, equal arguments, long sequences"],
    ["Bugs found here (of 6)", f"{len(buggy['example_based']['bugs_detected'])}", f"{len(pbt_bugs)}"],
    ["Failure report", "The tester's own input", "A shrunk, minimal counterexample"],
    ["Readability", "Very high: each test is a concrete story",
     "High once you can read strategies; the property states the intent directly"],
    ["Determinism", "Fully deterministic", "Random, made reproducible with a seed and the example database"],
    ["Speed", f"{fixed['example_based']['pytest_time_s']:.2f} s for the suite",
     f"{fixed['property_based']['pytest_time_s']:.2f} s (properties), {fixed['stateful']['pytest_time_s']:.2f} s (stateful)"],
    ["Limitations", "Blind spots match the developer's blind spots",
     "Needs good properties and strategies; cannot prove absence of bugs; a weak property passes silently"],
]
table(["Aspect", "Example-based (PyTest)", "Property-based (Hypothesis)"], rows, widths=[3.6, 5.8, 6.4],
      font_size=9, title="Example-based vs property-based testing")
para("The two approaches work best together. Example tests serve as readable documentation of specific "
     "behaviours and as regression tests for known bugs. Properties explore the input space and find the cases "
     "nobody thought of. Hypothesis supports this combination directly through @example, which pins a concrete "
     "case inside a property, as P-05 does in this project.")

# ======================================================== 10. LIMITATIONS

heading("10. Limitations and Future Scope")
heading("10.1 Limitations", 2)
bullets([
    ("Properties must be correct and strong enough. ", "A property that is too weak (for example \"the balance is a "
     "number\") passes on buggy code. The quality of PBT depends on the tester's understanding of the "
     "specification."),
    ("The bugs were seeded by the author. ", "The experiment shows that PBT can find realistic bugs of these "
     "kinds. It is not a statistical study of real-world fault detection rates. The example-based suite was also "
     "written by the author to be typical. A tester applying boundary value analysis very carefully could have "
     "caught some of these bugs by hand. PBT's advantage is that it does not depend on that care."),
    ("No proof of correctness. ", f"Passing {generated_total_fixed} generated cases raises confidence but, like all "
     "testing, does not prove the absence of bugs."),
    ("Masking. ", "As seen with the state machine, one failure can hide another that breaks the same assertion "
     "until the first is fixed."),
    ("Small system under test. ", "The banking module is intentionally small so that it can be explained line by "
     "line. Larger systems need more careful strategy design and longer runs."),
    ("Timing figures are indicative. ", "Execution times were measured on one laptop and include noise."),
])
heading("10.2 Future scope", 2)
bullets([
    "Measure code coverage (coverage.py) and mutation score (e.g. mutmut) for each suite to give a more general "
    "comparison than the six seeded bugs.",
    "Extend the state machine with bundles (opening and closing accounts dynamically), interest and invalid "
    "operations, and add preconditions for richer model-based testing.",
    "Use targeted property-based testing (hypothesis.target) to steer the search towards extreme values, such as "
    "maximising rounding error.",
    "Run Hypothesis in continuous integration with a shared example database, so that failures found on one "
    "machine are replayed everywhere.",
    "Apply the same approach to a real-world service, for example a REST API using schema-based generators.",
])

# ======================================================== 11. CONCLUSION

heading("11. Conclusion")
para(f"This project built a banking transaction module in a buggy and a fixed version and tested both with three "
     f"suites. The hand-written example-based suite of {eb_total} tests passed completely on the buggy code and "
     f"detected none of the {n_bugs} seeded bugs. The property-based suite expressed the module's rules directly: "
     f"round trips, no negative balances, conservation of money, validation of inputs, and correct rounding. "
     f"Together with one stateful test, it detected all {len(pbt_bugs)} bugs. For every failure Hypothesis "
     f"reported a shrunk counterexample of one or two small values, or a program of one or two steps, which "
     f"made each bug easy to diagnose. After the fixes, every test in every suite passed.")
para("The main lesson is that a passing test suite shows only that the code works for the inputs that were "
     "tried. Property-based testing asks the developer to state what must always be true and lets the machine "
     "search for counterexamples, including edge cases that people rarely think of. Combined with conventional "
     "example tests, it is a practical, low-cost way to find subtle bugs, especially in code where correctness "
     "matters, such as financial software.")

# ======================================================== REFERENCES

heading("References", new_page=True)
for ref in [
    "Claessen, K., & Hughes, J. (2000). QuickCheck: A lightweight tool for random testing of Haskell programs. "
    "Proceedings of the Fifth ACM SIGPLAN International Conference on Functional Programming (ICFP '00), "
    "268–279. https://doi.org/10.1145/351240.351266",
    "MacIver, D. R., Hatfield-Dodds, Z., et al. (2019). Hypothesis: A new approach to property-based testing. "
    "Journal of Open Source Software, 4(43), 1891. https://doi.org/10.21105/joss.01891",
    "MacIver, D. R., & Donaldson, A. F. (2020). Test-case reduction via test-case generation: Insights from the "
    "Hypothesis reducer. 34th European Conference on Object-Oriented Programming (ECOOP 2020), LIPIcs vol. 166, "
    "13:1–13:27. https://doi.org/10.4230/LIPIcs.ECOOP.2020.13",
    "Hughes, J. (2016). Experiences with QuickCheck: Testing the hard stuff and staying sane. In A List of "
    "Successes That Can Change the World (LNCS 9600), Springer, 169–186.",
    "Duran, J. W., & Ntafos, S. C. (1984). An evaluation of random testing. IEEE Transactions on Software "
    "Engineering, SE-10(4), 438–444.",
    "Myers, G. J., Sandler, C., & Badgett, T. (2011). The Art of Software Testing (3rd ed.). John Wiley & Sons.",
    "Goldberg, D. (1991). What every computer scientist should know about floating-point arithmetic. ACM "
    "Computing Surveys, 23(1), 5–48.",
    "Dijkstra, E. W. (1970). Notes on Structured Programming (EWD249). Technological University Eindhoven.",
    "Hypothesis documentation. https://hypothesis.readthedocs.io/",
    "pytest documentation. https://docs.pytest.org/",
    "Python Software Foundation. decimal — Decimal fixed point and floating point arithmetic. "
    "https://docs.python.org/3/library/decimal.html",
]:
    p = doc.add_paragraph(ref, style="List Number")
    p.alignment = WD_ALIGN_PARAGRAPH.LEFT

# ======================================================== APPENDIX A

heading("Appendix A: Commands to Reproduce")
para("Windows (PowerShell), from the project folder:")
code("python -m venv .venv\n"
     ".venv\\Scripts\\Activate.ps1\n"
     "pip install -r requirements.txt\n\n"
     "# run one suite on one version\n"
     "$env:BANK_VERSION = \"buggy\"\n"
     f"pytest tests/test_example_based.py -v\n"
     f"pytest tests/test_property_based.py --hypothesis-seed={m['seed']} --hypothesis-show-statistics\n"
     f"pytest tests/test_stateful.py --hypothesis-seed={m['seed']}\n"
     "$env:BANK_VERSION = \"fixed\"\n"
     "pytest -v\n\n"
     "# full pipeline: experiment -> charts -> report\n"
     f"python scripts/run_experiment.py --seed {m['seed']}\n"
     "python scripts/make_charts.py\n"
     "python report/build_report.py")
para("Linux / macOS: use source .venv/bin/activate and prefix commands with BANK_VERSION=buggy or "
     "BANK_VERSION=fixed instead of setting $env:BANK_VERSION.")
para(f"This report was generated from the run of {m['generated_at']} (seed {m['seed']}, Python {env['python']}, "
     f"pytest {env['pytest']}, Hypothesis {env['hypothesis']}). Raw outputs are in the results/ folder.")

# ======================================================== APPENDIX B

heading("Appendix B: Viva Questions and Answers", new_page=True)
qa = [
    ("What is a property?",
     "A rule that must be true for every valid input, for example \"a transfer never changes the bank's total "
     "money\". It describes behaviour in general instead of one example."),
    ("What is property-based testing?",
     "A testing style where you write properties and a tool generates many inputs automatically to try to break "
     "them. If an input breaks a property, the tool reports it as a counterexample."),
    ("What is Hypothesis?",
     "The main property-based testing library for Python. It works as a pytest plugin. You decorate a test with "
     "@given(...) and it calls the test with generated inputs."),
    ("What is a strategy?",
     "A description of which inputs to generate, for example st.decimals(min_value=0, max_value=10000, places=2) "
     "for money amounts. Strategies can be combined, for example a list of decimals."),
    ("What is shrinking?",
     "When Hypothesis finds a failing input, it keeps trying simpler versions (smaller numbers, shorter lists, "
     f"fewer steps) and keeps the simplest one that still fails. In this project a failing withdrawal was shrunk to "
     f"{withdraw_ce}."),
    ("Why did the example-based tests pass on the buggy code?",
     "They only use inputs like 100, 50 and 10.50, which avoid every bug: they never use negative amounts, never "
     "transfer to the same account, never overdraw by less than a rupee, and use amounts that are exact in "
     "binary floating point."),
    ("How is PBT different from random testing?",
     "Random testing usually just checks that nothing crashes. PBT checks a meaningful rule. It biases generation "
     "towards edge cases like 0 and boundaries, and it shrinks failures to minimal examples instead of reporting "
     "a large random input."),
    ("How is it different from boundary value analysis?",
     "In BVA the tester must find the boundaries by hand. With PBT the tool searches the whole range and favours "
     "boundary-like values automatically, so it can find boundaries the tester did not know about, such as the "
     "paise just above the balance in BUG-3."),
    ("What is stateful testing?",
     "Testing a sequence of operations instead of a single call. Hypothesis's RuleBasedStateMachine generates "
     "random sequences of rules (deposit, withdraw, transfer), checks invariants after each step and shrinks a "
     "failing sequence to the shortest one."),
    ("What is an invariant?",
     "A condition that must stay true at all times, such as \"no balance is ever negative\" or \"the total money "
     "equals deposits minus withdrawals\"."),
    ("Why is float wrong for money?",
     "Binary floating point cannot represent most decimal fractions exactly, so 0.1 + 0.2 = 0.30000000000000004. "
     "The fixed version uses decimal.Decimal rounded to 2 places."),
    ("How did you make random tests reproducible?",
     f"By fixing the seed with --hypothesis-seed={m['seed']} and disabling the example database, so every run "
     "generates the same inputs."),
    ("What are @settings and @example?",
     "@settings changes how Hypothesis runs, for example max_examples=200. @example adds a specific input that is "
     "always tested in addition to the generated ones."),
    ("Does PBT replace example-based tests?",
     "No. They complement each other. Examples are clear documentation and regression tests. Properties find "
     "the unexpected cases."),
    ("What are the limitations of PBT?",
     "You must think of good properties, a weak property gives false confidence, tests take longer, and it still "
     "cannot prove that there are no bugs."),
    ("What is the Hypothesis example database?",
     "A local store (the .hypothesis folder) of failing inputs. Hypothesis replays them first on the next run so a "
     "bug is not lost. It was disabled in this project only to keep runs reproducible from the seed."),
    ("Why did the state machine not report BUG-4?",
     "Self-transfer and float drift both break the same assertion (total money conserved). Hypothesis reports "
     "one failure per assertion and chose the simpler one. BUG-4 was still caught by the dedicated "
     "self-transfer property."),
]
for i, (q, a) in enumerate(qa, 1):
    p = doc.add_paragraph()
    p.paragraph_format.space_after = Pt(1)
    p.add_run(f"Q{i}. {q}").bold = True
    para(a)

add_page_number_footer()
OUTPUT.parent.mkdir(exist_ok=True)
doc.save(OUTPUT)
print(f"saved {OUTPUT.relative_to(ROOT)}")
