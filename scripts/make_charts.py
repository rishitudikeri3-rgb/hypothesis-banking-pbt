"""
make_charts.py - Draws the result charts from results/metrics.json.

Creates in results/:
  chart1_bugs_detected.png     bugs found by each suite (buggy version)
  chart2_test_cases.png        hand-written vs Hypothesis-generated test cases
  chart3_pass_fail.png         passed / failed per suite, buggy vs fixed
  chart4_execution_time.png    execution time per suite
  workflow.png                 the project's testing workflow (diagram)

Usage: python scripts/make_charts.py
"""

import json
from pathlib import Path

import matplotlib

matplotlib.use("Agg")  # draw straight to files, no window needed
import matplotlib.pyplot as plt
from matplotlib.patches import FancyArrowPatch, FancyBboxPatch

ROOT = Path(__file__).resolve().parent.parent
RESULTS = ROOT / "results"

SUITES = ["example_based", "property_based", "stateful"]
SUITE_LABELS = ["Example-based\n(PyTest)", "Property-based\n(Hypothesis)", "Stateful\n(Hypothesis)"]

# Colours (validated colour-blind-safe categorical palette)
BLUE, ORANGE, AQUA, RED = "#2a78d6", "#eb6834", "#1baf7a", "#e34948"
TEXT, MUTED, GRID = "#0b0b0b", "#52514e", "#e4e3df"

plt.rcParams.update({
    "font.family": "DejaVu Sans",
    "font.size": 10,
    "axes.edgecolor": MUTED,
    "axes.labelcolor": TEXT,
    "axes.titleweight": "bold",
    "axes.titlesize": 12,
    "xtick.color": MUTED,
    "ytick.color": MUTED,
    "axes.spines.top": False,
    "axes.spines.right": False,
    "axes.grid": True,
    "axes.grid.axis": "y",
    "grid.color": GRID,
    "axes.axisbelow": True,
})


def label_bars(ax, bars, fmt="{:g}"):
    """Write each bar's value just above it."""
    for bar in bars:
        height = bar.get_height()
        ax.annotate(fmt.format(height), (bar.get_x() + bar.get_width() / 2, height),
                    xytext=(0, 3), textcoords="offset points", ha="center", va="bottom",
                    color=TEXT, fontsize=9)


def save(fig, name):
    fig.tight_layout()
    fig.savefig(RESULTS / name, dpi=200)
    plt.close(fig)
    print(f"saved results/{name}")


def chart_bugs_detected(m):
    total_bugs = len(m["bugs"])
    counts = [len(m["runs"]["buggy"][s]["bugs_detected"]) for s in SUITES]
    fig, ax = plt.subplots(figsize=(6.4, 4))
    bars = ax.bar(SUITE_LABELS, counts, width=0.5, color=BLUE)
    label_bars(ax, bars)
    ax.axhline(total_bugs, color=MUTED, linestyle="--", linewidth=1)
    ax.text(2.3, total_bugs, f"{total_bugs} seeded bugs", va="bottom", ha="right", color=MUTED, fontsize=9)
    ax.set_ylim(0, total_bugs + 1)
    ax.set_ylabel("Distinct seeded bugs detected")
    ax.set_title("Bugs detected on the buggy version")
    save(fig, "chart1_bugs_detected.png")


def grouped_bars(ax, values_buggy, values_fixed, fmt="{:g}"):
    x = range(len(SUITES))
    w = 0.36
    b1 = ax.bar([i - w / 2 - 0.01 for i in x], values_buggy, w, color=BLUE, label="Buggy version")
    b2 = ax.bar([i + w / 2 + 0.01 for i in x], values_fixed, w, color=ORANGE, label="Fixed version")
    label_bars(ax, b1, fmt)
    label_bars(ax, b2, fmt)
    ax.set_xticks(list(x))
    ax.set_xticklabels(SUITE_LABELS)
    ax.legend(frameon=False)


def chart_test_cases(m):
    buggy = [m["runs"]["buggy"][s]["examples_executed"] for s in SUITES]
    fixed = [m["runs"]["fixed"][s]["examples_executed"] for s in SUITES]
    fig, ax = plt.subplots(figsize=(7, 4.2))
    grouped_bars(ax, buggy, fixed)
    ax.set_yscale("log")
    ax.set_ylim(1, max(buggy + fixed) * 4)
    ax.set_ylabel("Test cases executed (log scale)")
    ax.set_title("Hand-written vs Hypothesis-generated test cases")
    save(fig, "chart2_test_cases.png")


def chart_pass_fail(m):
    fig, axes = plt.subplots(1, 2, figsize=(9, 4), sharey=True)
    w = 0.36
    for ax, version in zip(axes, ["buggy", "fixed"]):
        passed = [m["runs"][version][s]["passed"] for s in SUITES]
        failed = [m["runs"][version][s]["failed"] for s in SUITES]
        x = range(len(SUITES))
        b1 = ax.bar([i - w / 2 - 0.01 for i in x], passed, w, color=AQUA, label="Passed")
        b2 = ax.bar([i + w / 2 + 0.01 for i in x], failed, w, color=RED, label="Failed")
        label_bars(ax, b1)
        label_bars(ax, b2)
        ax.set_xticks(list(x))
        ax.set_xticklabels(SUITE_LABELS, fontsize=9)
        ax.set_title(f"{version.capitalize()} version")
    axes[0].set_ylabel("Number of tests")
    axes[0].legend(frameon=False)
    axes[0].set_ylim(0, max(m["runs"]["buggy"][s]["total"] for s in SUITES) + 3)
    fig.suptitle("Pass / fail per suite", fontweight="bold")
    save(fig, "chart3_pass_fail.png")


def chart_execution_time(m):
    buggy = [m["runs"]["buggy"][s]["pytest_time_s"] for s in SUITES]
    fixed = [m["runs"]["fixed"][s]["pytest_time_s"] for s in SUITES]
    fig, ax = plt.subplots(figsize=(7, 4.2))
    grouped_bars(ax, buggy, fixed, fmt="{:.2f}s")
    ax.set_ylim(0, max(buggy + fixed) * 1.25)
    ax.set_ylabel("Execution time reported by pytest (s)")
    ax.set_title("Execution time per suite")
    save(fig, "chart4_execution_time.png")


def workflow_diagram():
    steps = [
        "Write the banking\nmodule (buggy +\nfixed versions)",
        "Write example-based\nPyTest tests",
        "Write properties\n(@given + strategies)\nand a state machine",
        "Run all suites on\nboth versions\n(fixed seed)",
        "Hypothesis generates\ninputs, finds a failure\nand shrinks it",
        "Collect metrics,\ncharts and report",
    ]
    fig, ax = plt.subplots(figsize=(10, 3.4))
    ax.set_xlim(0, 3)
    ax.set_ylim(0, 2)
    ax.axis("off")
    positions = [(0.5, 1.45), (1.5, 1.45), (2.5, 1.45), (2.5, 0.5), (1.5, 0.5), (0.5, 0.5)]
    box_w, box_h = 0.8, 0.72
    for (x, y), text in zip(positions, steps):
        ax.add_patch(FancyBboxPatch((x - box_w / 2, y - box_h / 2), box_w, box_h,
                                    boxstyle="round,pad=0.02,rounding_size=0.05",
                                    facecolor="#eaf2fc", edgecolor=BLUE, linewidth=1.5))
        ax.text(x, y, text, ha="center", va="center", fontsize=9, color=TEXT)
    for i in range(len(positions) - 1):
        (x1, y1), (x2, y2) = positions[i], positions[i + 1]
        if y1 == y2:
            sign = 1 if x2 > x1 else -1
            start, end = (x1 + sign * box_w / 2, y1), (x2 - sign * box_w / 2, y2)
        else:
            start, end = (x1, y1 - box_h / 2), (x2, y2 + box_h / 2)
        ax.add_patch(FancyArrowPatch(start, end, arrowstyle="-|>", mutation_scale=14,
                                     color=MUTED, linewidth=1.3))
    ax.set_title("Testing workflow used in this project")
    save(fig, "workflow.png")


def main():
    metrics = json.loads((RESULTS / "metrics.json").read_text(encoding="utf-8"))
    chart_bugs_detected(metrics)
    chart_test_cases(metrics)
    chart_pass_fail(metrics)
    chart_execution_time(metrics)
    workflow_diagram()


if __name__ == "__main__":
    main()
