import json
import sys

import pytest

from scripts.check_coverage import main


def write_inputs(tmp_path, *, line_coverage, branches_covered, branches_total):
    report = tmp_path / "coverage.json"
    thresholds = tmp_path / "thresholds.json"
    report.write_text(
        json.dumps(
            {
                "totals": {
                    "percent_statements_covered": line_coverage,
                    "covered_branches": branches_covered,
                    "num_branches": branches_total,
                }
            }
        ),
        encoding="utf-8",
    )
    thresholds.write_text(
        json.dumps({"minimum": {"line_percent": 80, "branch_percent": 70}}),
        encoding="utf-8",
    )
    return report, thresholds


def run_checker(report, thresholds, monkeypatch):
    monkeypatch.setattr(
        sys,
        "argv",
        ["check_coverage.py", str(report), "--thresholds", str(thresholds)],
    )
    return main()


def test_coverage_checker_accepts_both_metrics_at_or_above_minimum(tmp_path, monkeypatch):
    report, thresholds = write_inputs(
        tmp_path, line_coverage=80, branches_covered=72, branches_total=100
    )

    assert run_checker(report, thresholds, monkeypatch) == 0


@pytest.mark.parametrize(
    ("line_coverage", "branches_covered"),
    ((79.99, 90), (90, 69)),
)
def test_coverage_checker_rejects_a_below_minimum_metric(
    tmp_path, monkeypatch, line_coverage, branches_covered
):
    report, thresholds = write_inputs(
        tmp_path,
        line_coverage=line_coverage,
        branches_covered=branches_covered,
        branches_total=100,
    )

    assert run_checker(report, thresholds, monkeypatch) == 1


def test_coverage_checker_rejects_reports_without_branch_data(tmp_path, monkeypatch):
    report, thresholds = write_inputs(
        tmp_path, line_coverage=90, branches_covered=0, branches_total=0
    )

    assert run_checker(report, thresholds, monkeypatch) == 2
