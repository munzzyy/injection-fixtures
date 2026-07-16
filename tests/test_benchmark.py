"""Structure tests for benchmark/run_framewall.py's report builder.

These don't invoke a real framewall CLI - the actual benchmark run against a
live install belongs in a dated, manually-refreshed snapshot (see
docs/benchmarks/framewall.md), not in a suite that has to pass without
framewall installed. This package's only runtime dependency is Pillow (see
CONTRIBUTING.md); framewall isn't one of them, and injection-fixtures' own CI
never installs it. What's tested here is that `build_report` turns a given
set of scan results into the right rows and totals, so a change to the table
format can't silently drop a technique or drift the math.
"""

from __future__ import annotations

import importlib.util
from pathlib import Path

from injection_fixtures.benign import BENIGN_CATALOG
from injection_fixtures.catalog import CATALOG

SCRIPT_PATH = Path(__file__).parent.parent / "benchmark" / "run_framewall.py"


def _load_run_framewall():
    spec = importlib.util.spec_from_file_location("run_framewall", SCRIPT_PATH)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def _fake_scan(verdict: str, rule_ids=()) -> dict:
    return {
        "verdict": verdict,
        "ocr_used": True,
        "ocr_skipped_reason": "",
        "findings": [{"rule_id": rid} for rid in rule_ids],
    }


def _fake_results():
    """One technique result per catalog entry (caught only if ocr_expected,
    mirroring a plausible OCR-dependent detector) and one clean benign
    result per control - deliberately synthetic, this is a structure check
    on the report builder, not a real measurement."""
    technique_results = [
        {
            "kind": "technique", "id": t.id, "name": t.name, "ocr_expected": t.ocr_expected,
            "scan": _fake_scan("dangerous", ["FW-001"]) if t.ocr_expected else _fake_scan("clean"),
        }
        for t in CATALOG.values()
    ]
    benign_results = [
        {"kind": "benign", "id": s.id, "name": s.name, "ocr_expected": None, "scan": _fake_scan("clean")}
        for s in BENIGN_CATALOG.values()
    ]
    return technique_results, benign_results


def _report(technique_results, benign_results, **overrides):
    module = _load_run_framewall()
    kwargs = {"fw_version": "0.1.0", "ocr_note": "used on every image", "run_date": "2026-07-16"}
    kwargs.update(overrides)
    return module.build_report(technique_results, benign_results, **kwargs)


def test_report_has_a_row_for_every_technique():
    technique_results, benign_results = _fake_results()
    report = _report(technique_results, benign_results)
    for technique_id in CATALOG:
        assert f"`{technique_id}`" in report


def test_report_has_a_row_for_every_benign_control():
    technique_results, benign_results = _fake_results()
    report = _report(technique_results, benign_results)
    for sample_id in BENIGN_CATALOG:
        assert f"`{sample_id}`" in report


def test_report_computes_catch_rate_from_verdicts():
    technique_results, benign_results = _fake_results()
    caught = sum(1 for t in CATALOG.values() if t.ocr_expected)
    report = _report(technique_results, benign_results)
    assert f"{caught}/{len(CATALOG)} injection techniques caught" in report


def test_report_lists_missed_techniques_by_id():
    technique_results, benign_results = _fake_results()
    report = _report(technique_results, benign_results)
    for technique in CATALOG.values():
        if not technique.ocr_expected:
            assert f"`{technique.id}`" in report.split("missed:")[1].split("\n")[0]


def test_report_counts_benign_false_positives():
    technique_results, benign_results = _fake_results()
    benign_results[0]["scan"] = _fake_scan("suspicious", ["FW-004"])
    report = _report(technique_results, benign_results)
    assert f"1/{len(BENIGN_CATALOG)} benign controls false-positived" in report


def test_report_names_the_framewall_version_and_run_date():
    technique_results, benign_results = _fake_results()
    report = _report(technique_results, benign_results, fw_version="9.9.9", run_date="2099-01-01")
    assert "9.9.9" in report
    assert "2099-01-01" in report


def test_report_carries_the_ocr_note_verbatim():
    technique_results, benign_results = _fake_results()
    report = _report(technique_results, benign_results, ocr_note="skipped on every image (no tesseract)")
    assert "skipped on every image (no tesseract)" in report


def test_report_includes_the_reproduce_command():
    technique_results, benign_results = _fake_results()
    report = _report(technique_results, benign_results)
    assert "python benchmark/run_framewall.py" in report
