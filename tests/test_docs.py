"""The README is the product page. These pin the parts of it that are output
from the code, so a new technique or a changed column width can't leave it
describing a different package.
"""

from __future__ import annotations

import contextlib
import io
import re
from pathlib import Path

import pytest

import injection_fixtures
from injection_fixtures import cli
from injection_fixtures.benign import BENIGN_CATALOG
from injection_fixtures.catalog import CATALOG

ROOT = Path(__file__).resolve().parent.parent
README = ROOT / "README.md"
TECHNIQUES_DOC = ROOT / "docs" / "techniques.md"

NUMBER_WORDS = (
    "one|two|three|four|five|six|seven|eight|nine|ten|eleven|twelve|thirteen|"
    "fourteen|fifteen|sixteen|seventeen|eighteen|nineteen|twenty"
)


def _readme() -> str:
    return README.read_text(encoding="utf-8")


def _fenced_block(text: str, first_line: str) -> list:
    match = re.search(r"```\n" + re.escape(first_line) + r"\n(.*?)\n```", text, re.S)
    assert match is not None, f"no fenced block starting with {first_line!r}"
    return match.group(1).split("\n")


def _section(text: str, heading: str) -> str:
    match = re.search(r"^## " + re.escape(heading) + r"\n(.*?)(?=^## |\Z)", text, re.S | re.M)
    assert match is not None, f"no section {heading!r}"
    return match.group(1)


def test_readme_list_block_is_the_real_list_output():
    out = io.StringIO()
    with contextlib.redirect_stdout(out):
        assert cli.main(["list"]) == 0
    assert _fenced_block(_readme(), "$ injection-fixtures list") == out.getvalue().rstrip("\n").split("\n")


def test_readme_render_all_sample_counts_every_image():
    wrote = re.findall(r"wrote (\d+) images", _readme())
    assert wrote
    assert {int(n) for n in wrote} == {len(CATALOG) + len(BENIGN_CATALOG)}


def test_readme_pytest_sample_matches_what_the_snippet_collects():
    # The snippet runs one test per technique, one per control, and one more.
    sample = "\n".join(_fenced_block(_readme(), "$ pytest -v"))
    expected = len(CATALOG) + len(BENIGN_CATALOG) + 1
    assert re.findall(r"collected (\d+) items", sample) == [str(expected)]
    assert re.findall(r"(\d+) passed", sample) == [str(expected)]
    for some_id in list(CATALOG) + list(BENIGN_CATALOG):
        assert f"[{some_id}]" in sample
    assert re.findall(r"plugins: injection-fixtures-(\S+)", sample) == [injection_fixtures.__version__]


@pytest.mark.parametrize("heading", ["What it does", "What this is not"])
def test_readme_counts_are_digits_that_match_the_catalogs(heading):
    section = _section(_readme(), heading)
    techniques = re.findall(r"\b(\d+)\s+(?:[\w-]+\s+){0,2}techniques\b", section)
    controls = re.findall(r"\b(\d+)\s+(?:[\w-]+\s+){0,2}control(?:s| images)\b", section)
    assert techniques and controls
    assert set(techniques) == {str(len(CATALOG))}
    assert set(controls) == {str(len(BENIGN_CATALOG))}
    spelled = re.findall(r"\b(?:" + NUMBER_WORDS + r")\s+(?:techniques|controls)\b", section, re.I)
    assert spelled == []


def _doc_table_rows():
    if not TECHNIQUES_DOC.is_file():
        pytest.skip("docs/ is not in this tree")
    rows = {}
    for line in TECHNIQUES_DOC.read_text(encoding="utf-8").splitlines():
        match = re.match(r"^\| `([a-z0-9-]+)` \|(.*)\|$", line)
        if match:
            rows[match.group(1)] = [cell.strip() for cell in match.group(2).split("|")]
    return rows


def test_techniques_doc_min_size_column_matches_the_catalog():
    rows = _doc_table_rows()
    for technique_id, technique in CATALOG.items():
        assert technique_id in rows, f"{technique_id} has no row in docs/techniques.md"
        w, h = technique.min_size
        assert rows[technique_id][2] == f"{w}x{h}", technique_id


def test_techniques_doc_benign_table_lists_every_control():
    rows = _doc_table_rows()
    assert set(rows) == set(CATALOG) | set(BENIGN_CATALOG)
