"""
run_experiment.py - Runs every test suite against both versions of the bank
and collects the results into results/metrics.json.

For each (version, suite) pair it:
  1. runs pytest with a FIXED Hypothesis seed (so results are reproducible)
     and --hypothesis-show-statistics,
  2. saves the raw console output to results/<suite>_<version>.txt and a
     JUnit XML file to results/<suite>_<version>.xml,
  3. reads pass/fail, timings and failure details from the XML,
  4. reads "examples generated" and shrink counts from the statistics text,
  5. maps every failure to the seeded bug(s) it reveals.

Usage (from the project folder):
    python scripts/run_experiment.py            # seed 12345
    python scripts/run_experiment.py --seed 7   # any other seed
"""

import argparse
import ast
import json
import os
import platform
import re
import subprocess
import sys
import time
import xml.etree.ElementTree as ET
from datetime import datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
RESULTS = ROOT / "results"

VERSIONS = ["buggy", "fixed"]
SUITES = {
    "example_based": "tests/test_example_based.py",
    "property_based": "tests/test_property_based.py",
    "stateful": "tests/test_stateful.py",
}


# ------------------------------------------------------------ static info

def read_bug_list():
    """Read BUG-n titles from the comment block at the top of bank_buggy.py."""
    text = (ROOT / "src" / "bank_buggy.py").read_text(encoding="utf-8")
    bugs = {}
    current = None
    for line in text.splitlines():
        match = re.match(r"^ (BUG-\d)\s+(.+)$", line)
        if match:
            current = match.group(1)
            bugs[current] = match.group(2).strip()
        elif current and line.strip() and "What goes wrong" not in line:
            bugs[current] += " " + line.strip()   # title continues on next line
        else:
            current = None
    return bugs


def read_docstrings(test_file):
    """Return {test name: {description, field: value, ...}} from docstrings."""
    tree = ast.parse((ROOT / test_file).read_text(encoding="utf-8"))
    info = {}
    for node in ast.walk(tree):
        if isinstance(node, ast.FunctionDef) and node.name.startswith("test_"):
            doc = ast.get_docstring(node) or ""
            lines = [line.strip() for line in doc.splitlines() if line.strip()]
            entry = {"description": lines[0] if lines else ""}
            for line in lines[1:]:
                if ":" in line:
                    key, value = line.split(":", 1)
                    entry[key.strip().lower()] = value.strip()
            info[node.name] = entry
    return info


# --------------------------------------------------------- output parsing

def parse_statistics(output):
    """Parse the --hypothesis-show-statistics section of pytest's output.
    Returns {test id: {"phases": {...}, "valid_examples": n, ...}}."""
    stats = {}
    if "Hypothesis Statistics" not in output:
        return stats
    section = output.split("Hypothesis Statistics", 1)[1]
    section = section.split("short test summary info", 1)[0]
    blocks = re.split(r"^(tests/\S+?):\s*$", section, flags=re.MULTILINE)
    # blocks = [junk, header1, body1, header2, body2, ...]
    for header, body in zip(blocks[1::2], blocks[2::2]):
        test_id = header.split("::", 1)[1]
        phases = {}
        for phase, phase_body in re.findall(r"- during (\w+) phase.*?\n(.*?)(?=\n\s*- during|\n\s*- Stopped|\Z)",
                                            body, flags=re.DOTALL):
            counts = re.search(r"(\d+) passing, (\d+) failing, and (\d+) invalid", phase_body)
            if counts:
                phases[phase] = {
                    "passing": int(counts.group(1)),
                    "failing": int(counts.group(2)),
                    "invalid": int(counts.group(3)),
                }
        shrinks = re.search(r"Tried (\d+) shrinks of which (\d+) were successful", body)
        stopped = re.search(r"Stopped because (.+)", body)
        stats[test_id] = {
            "phases": phases,
            # every input that actually ran the test body, in every phase
            "valid_examples": sum(p["passing"] + p["failing"] for p in phases.values()),
            "generate_phase_examples": sum(phases.get("generate", {"passing": 0, "failing": 0}).get(k, 0)
                                           for k in ("passing", "failing")),
            "shrinks_tried": int(shrinks.group(1)) if shrinks else 0,
            "shrinks_successful": int(shrinks.group(2)) if shrinks else 0,
            "stopped_because": stopped.group(1).strip() if stopped else None,
        }
    return stats


def clean_failure_text(text):
    """Remove pytest's 'E   ' prefixes and exception-group '|' bars."""
    lines = []
    for line in text.splitlines():
        line = re.sub(r"^\s*(\|\s?)+", "", line)
        line = re.sub(r"^E {1,7}", "", line)
        lines.append(line)
    return "\n".join(lines)


def parse_failures(failure_text):
    """Split a failure into its distinct errors. For each one return the
    error message and Hypothesis's shrunk counterexample."""
    text = clean_failure_text(failure_text)
    sections = re.split(r"\+-+ \d+ -+", text)   # exception-group separators
    failures = []
    for section in sections:
        lines = section.splitlines()
        start = next((i for i, l in enumerate(lines)
                      if l.strip().startswith(("Failing test case:", "Falsifying example:"))), None)
        if start is None:
            continue
        example = []
        for line in lines[start:]:
            example.append(line.rstrip())
            one_line_call = len(example) == 1 and line.rstrip().endswith(")")
            if one_line_call or line.strip() in (")", "state.teardown()"):
                break
        message_lines = [l.strip() for l in lines[:start]
                         if re.match(r"^\s*(\w+Error|Failed|ExceptionGroup)\b.*:", l)]
        failures.append({
            "message": message_lines[-1] if message_lines else "",
            "counterexample": "\n".join(example).replace("Failing test case: ", "", 1)
                                               .replace("Falsifying example: ", "", 1),
        })
    return failures


def has_float_drift(message):
    """True if the message shows a number with more than 2 decimal places,
    e.g. 0.30000000000000004 - the fingerprint of BUG-1."""
    return any(len(frac) > 2 for frac in re.findall(r"\d+\.(\d+)", message))


def bugs_for_failure(suite, test_info, failure):
    """Decide which seeded bug a failure reveals."""
    message, example = failure["message"], failure["counterexample"]
    if has_float_drift(message):
        return ["BUG-1"]
    if suite == "stateful":
        if "no-negative-balance" in message:
            return ["BUG-3"]
        self_transfer = re.search(r"transfer\(sender='(\w+)', receiver='\1'", example)
        return ["BUG-4"] if self_transfer else []
    return re.findall(r"BUG-\d", test_info.get("targets", ""))


# ---------------------------------------------------------------- running

def run_suite(version, suite, test_file, seed):
    """Run one suite on one version and return its metrics."""
    out_txt = RESULTS / f"{suite}_{version}.txt"
    out_xml = RESULTS / f"{suite}_{version}.xml"
    env = dict(os.environ, BANK_VERSION=version)
    cmd = [sys.executable, "-m", "pytest", test_file, "-v",
           "-p", "no:cacheprovider",
           f"--hypothesis-seed={seed}",
           "--hypothesis-show-statistics",
           f"--junitxml={out_xml}"]
    started = time.perf_counter()
    proc = subprocess.run(cmd, cwd=ROOT, env=env, capture_output=True, text=True, encoding="utf-8")
    wall_time = time.perf_counter() - started
    output = proc.stdout + proc.stderr
    out_txt.write_text(f"$ BANK_VERSION={version} {' '.join(cmd[2:])}\n\n{output}", encoding="utf-8")

    docs = read_docstrings(test_file)
    stats = parse_statistics(output)
    xml_root = ET.parse(out_xml).getroot()
    suite_node = xml_root if xml_root.tag == "testsuite" else xml_root.find("testsuite")

    tests = []
    for case in suite_node.iter("testcase"):
        name = case.get("name")
        class_parts = case.get("classname", "").split(".")
        test_id = f"{class_parts[2]}::{name}" if len(class_parts) > 2 else name
        info = dict(docs.get(name, {}))
        if suite == "stateful":
            info = {"description": "Random sequences of deposit / withdraw / transfer on 3 accounts; "
                                   "invariants: no negative balance, total money conserved, balances match model.",
                    "strategy": "rules over sampled_from(3 account ids) and decimals 0.01..1000.00 (2 dp); "
                                "200 programs x up to 20 steps",
                    "targets": "any"}
        failure_node = case.find("failure")
        if failure_node is None:
            failure_node = case.find("error")
        status = "passed" if failure_node is None else "failed"
        failures = []
        if failure_node is not None:
            raw = (failure_node.get("message") or "") + "\n" + (failure_node.text or "")
            for failure in parse_failures(raw):
                failure["bugs"] = bugs_for_failure(suite, info, failure)
                failures.append(failure)
        test_stats = stats.get(test_id)
        tests.append({
            "name": test_id,
            "status": status,
            "time_s": float(case.get("time", 0)),
            **{k: v for k, v in info.items()},
            "hypothesis": test_stats,
            # example-based tests run exactly one hand-picked input
            "examples_executed": test_stats["valid_examples"] if test_stats else 1,
            "failures": failures,
        })

    bugs_detected = sorted({bug for t in tests for f in t["failures"] for bug in f["bugs"]})
    return {
        "test_file": test_file,
        "command": " ".join(cmd[2:]),
        "exit_code": proc.returncode,
        "total": len(tests),
        "passed": sum(t["status"] == "passed" for t in tests),
        "failed": sum(t["status"] == "failed" for t in tests),
        "pytest_time_s": round(float(suite_node.get("time", 0)), 3),
        "wall_time_s": round(wall_time, 3),
        "examples_executed": sum(t["examples_executed"] for t in tests),
        "bugs_detected": bugs_detected,
        "tests": tests,
    }


def main():
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--seed", type=int, default=12345, help="Hypothesis seed (default 12345)")
    args = parser.parse_args()
    RESULTS.mkdir(exist_ok=True)

    import hypothesis
    import pytest

    metrics = {
        "generated_at": datetime.now().isoformat(timespec="seconds"),
        "seed": args.seed,
        "environment": {
            "python": platform.python_version(),
            "platform": platform.platform(),
            "pytest": pytest.__version__,
            "hypothesis": hypothesis.__version__,
        },
        "bugs": read_bug_list(),
        "runs": {},
    }
    for version in VERSIONS:
        metrics["runs"][version] = {}
        for suite, test_file in SUITES.items():
            print(f"Running {suite:15s} on {version:5s} ...", end=" ", flush=True)
            result = run_suite(version, suite, test_file, args.seed)
            metrics["runs"][version][suite] = result
            print(f"{result['passed']} passed, {result['failed']} failed, "
                  f"{result['pytest_time_s']:.2f}s, bugs: {', '.join(result['bugs_detected']) or '-'}")

    # ------------------------------------------------ the project's 3 claims
    buggy, fixed = metrics["runs"]["buggy"], metrics["runs"]["fixed"]
    all_bugs = set(metrics["bugs"])
    pbt_bugs = set(buggy["property_based"]["bugs_detected"]) | set(buggy["stateful"]["bugs_detected"])
    metrics["verification"] = {
        "example_tests_all_pass_on_buggy": buggy["example_based"]["failed"] == 0,
        "every_seeded_bug_caught_by_pbt": pbt_bugs == all_bugs,
        "bugs_missed_by_pbt": sorted(all_bugs - pbt_bugs),
        "everything_passes_on_fixed": all(s["failed"] == 0 for s in fixed.values()),
    }
    (RESULTS / "metrics.json").write_text(json.dumps(metrics, indent=2), encoding="utf-8")

    print("\nVerification:")
    for key, value in metrics["verification"].items():
        print(f"  {key}: {value}")
    print(f"\nSaved {RESULTS / 'metrics.json'}")


if __name__ == "__main__":
    main()
