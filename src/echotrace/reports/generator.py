"""Génération des rapports (HTML, JSON, CSV, PDF, graphe) à partir des résultats."""

from __future__ import annotations

import csv
import json
import re
from datetime import datetime
from pathlib import Path

from jinja2 import Environment

from echotrace import __version__, paths
from echotrace.core.engine import build_summary
from echotrace.reports.graph import build_graph_svg
from echotrace.reports.html_template import HTML_TEMPLATE
from echotrace.reports.pdf import write_pdf

CSV_COLUMNS = ["platform", "confidence", "url", "title", "username", "module", "status", "note"]
STATUS_LABELS = {"confirmed": "Confirmé", "to_check": "À vérifier", "false_positive": "Faux positif"}

# autoescape=True : titres et URLs viennent de pages web non fiables.
_ENV = Environment(autoescape=True)


def _safe_name(name: str) -> str:
    """Réduit un nom de fichier à son dernier composant, sans caractère interdit."""
    return re.sub(r'[<>:"/\\|?*\x00-\x1f]', "_", Path(name).name) or "report"


class ReportGenerator:
    """Écrit les rapports dans `output_dir` (Documents/EchoTrace par défaut)."""

    def __init__(self, output_dir: str | Path | None = None) -> None:
        self.output_dir = Path(output_dir) if output_dir else paths.default_export_dir()
        self.output_dir.mkdir(parents=True, exist_ok=True)

    def _target_path(self, filename: str | None, prefix: str, extension: str) -> Path:
        if not filename:
            filename = f"{prefix}_{datetime.now():%Y%m%d_%H%M%S}.{extension}"
        return self.output_dir / _safe_name(filename)

    @staticmethod
    def _summary(results: list[dict], summary: dict | None) -> dict:
        # Un résumé incomplet (ancien format) est recalculé plutôt que de casser le rendu.
        if summary and {"total", "high_confidence", "avg_confidence", "platforms"} <= summary.keys():
            return summary
        return build_summary(results)

    def generate_html_report(self, target_data: dict, results: list[dict],
                             analysis_summary: dict | None = None,
                             filename: str | None = None, purpose: str = "") -> str:
        path = self._target_path(filename, "echotrace_report", "html")
        html = _ENV.from_string(HTML_TEMPLATE).render(
            generation_time=datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
            target_data=target_data,
            purpose=purpose,
            status_labels=STATUS_LABELS,
            results=results,
            summary=self._summary(results, analysis_summary),
            graph_svg=build_graph_svg(results),
        )
        path.write_text(html, encoding="utf-8")
        return str(path)

    def generate_json_report(self, target_data: dict, results: list[dict],
                             analysis_summary: dict | None = None,
                             filename: str | None = None, purpose: str = "") -> str:
        path = self._target_path(filename, "echotrace_report", "json")
        report = {
            "metadata": {
                "generated_at": datetime.now().isoformat(timespec="seconds"),
                "tool": "EchoTrace",
                "version": __version__,
                "description": "OSINT analysis report - public data only",
            },
            "target": target_data,
            "purpose": purpose,
            "summary": self._summary(results, analysis_summary),
            "results": results,
        }
        path.write_text(json.dumps(report, indent=2, ensure_ascii=False, default=str),
                        encoding="utf-8")
        return str(path)

    def generate_csv_report(self, results: list[dict], filename: str | None = None) -> str:
        path = self._target_path(filename, "echotrace_results", "csv")
        # utf-8-sig : Excel sous Windows reconnaît ainsi l'encodage.
        with open(path, "w", encoding="utf-8-sig", newline="") as handle:
            writer = csv.DictWriter(handle, fieldnames=CSV_COLUMNS, extrasaction="ignore")
            writer.writeheader()
            for result in results:
                # Préfixe l'apostrophe aux cellules qu'un tableur lirait comme une formule.
                writer.writerow({
                    key: f"'{value}" if isinstance(value, str) and value[:1] in "=+-@\t\r" and value
                    else value
                    for key, value in result.items() if key in CSV_COLUMNS
                })
        return str(path)

    def generate_pdf_report(self, target_data: dict, results: list[dict],
                            analysis_summary: dict | None = None,
                            filename: str | None = None, purpose: str = "") -> str:
        path = self._target_path(filename, "echotrace_report", "pdf")
        write_pdf(path, target_data, results, self._summary(results, analysis_summary), purpose)
        return str(path)

    def generate_network_graph(self, results: list[dict], filename: str | None = None) -> str:
        """Graphe pseudo ↔ plateforme en page HTML autonome ; chaîne vide s'il n'y a rien à relier."""
        svg = build_graph_svg(results)
        if not svg:
            return ""
        path = self._target_path(filename, "echotrace_network", "html")
        path.write_text(
            '<!DOCTYPE html><html lang="fr"><head><meta charset="UTF-8">'
            "<title>EchoTrace - Graphe</title></head>"
            f'<body style="margin:0;font-family:sans-serif">{svg}</body></html>',
            encoding="utf-8",
        )
        return str(path)
