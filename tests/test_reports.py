import csv
import json
from pathlib import Path

import pytest

from echotrace.reports import ReportGenerator
from echotrace.reports.graph import build_graph_svg

RESULTS = [
    {"module": "username", "platform": "GitHub", "url": "https://github.com/alice",
     "title": "@alice sur GitHub", "username": "alice", "confidence": 0.9},
    {"module": "google", "platform": "Bing", "url": "javascript:alert(1)",
     "title": "<script>alert('xss')</script>", "username": "", "confidence": 0.3},
    {"module": "google", "platform": "Bing", "url": "https://example.org",
     "title": "=HYPERLINK(\"http://evil\")", "username": "", "confidence": 0.5},
]
TARGET = {"pseudo": "alice", "email": "<b>a@b.fr</b>"}


@pytest.fixture
def generator(tmp_path):
    return ReportGenerator(tmp_path / "out")


def test_html_report_escapes_untrusted_content(generator):
    html = Path(generator.generate_html_report(TARGET, RESULTS)).read_text(encoding="utf-8")
    assert "<script>alert" not in html
    assert "&lt;script&gt;" in html
    assert "<b>a@b.fr</b>" not in html
    assert 'href="javascript:' not in html
    assert 'href="https://github.com/alice"' in html
    assert "<svg" in html  # le graphe est intégré


def test_json_report_structure(generator):
    path = generator.generate_json_report(TARGET, RESULTS)
    report = json.loads(Path(path).read_text(encoding="utf-8"))
    assert report["metadata"]["tool"] == "EchoTrace"
    assert report["summary"]["total"] == 3
    assert len(report["results"]) == 3


def test_csv_report_neutralizes_formulas(generator):
    path = generator.generate_csv_report(RESULTS)
    with open(path, encoding="utf-8-sig", newline="") as handle:
        rows = list(csv.DictReader(handle))
    assert len(rows) == 3
    assert rows[2]["title"].startswith("'=")


def test_pdf_report_is_written(generator):
    path = generator.generate_pdf_report(TARGET, RESULTS)
    assert Path(path).read_bytes()[:5] == b"%PDF-"


def test_filename_cannot_escape_output_dir(generator, tmp_path):
    path = generator.generate_json_report(TARGET, RESULTS, filename="../../evil.json")
    assert (tmp_path / "out" / "evil.json").exists()
    assert str(tmp_path / "out") in path


def test_graph(generator):
    assert build_graph_svg([]) == ""
    svg = build_graph_svg(RESULTS)
    assert "alice" in svg and "GitHub" in svg
    assert generator.generate_network_graph([]) == ""
    assert generator.generate_network_graph(RESULTS).endswith(".html")
