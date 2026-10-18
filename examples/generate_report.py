"""Génère tous les formats de rapport à partir de données fictives (hors ligne).

    uv run python examples/generate_report.py
"""

import tempfile
from pathlib import Path

from echotrace.core.engine import build_summary
from echotrace.reports import ReportGenerator

target = {"pseudo": "example_user", "email": "user@example.org"}
results = [
    {"module": "username", "platform": "GitHub", "url": "https://github.com/example_user",
     "title": "@example_user sur GitHub", "username": "example_user", "confidence": 0.84},
    {"module": "username", "platform": "GitLab", "url": "https://gitlab.com/example_user",
     "title": "@example_user sur GitLab", "username": "example_user", "confidence": 0.84},
    {"module": "google", "platform": "Bing", "url": "https://example.org/profile",
     "title": "Profil public", "username": "", "confidence": 0.36},
]

output = Path(tempfile.mkdtemp(prefix="echotrace_example_"))
generator = ReportGenerator(output)
summary = build_summary(results)

for path in (
    generator.generate_html_report(target, results, summary),
    generator.generate_json_report(target, results, summary),
    generator.generate_csv_report(results),
    generator.generate_pdf_report(target, results, summary),
    generator.generate_network_graph(results),
):
    print(path)
