"""Export PDF des résultats (reportlab, pur Python, identique sur tous les systèmes)."""

from __future__ import annotations

from datetime import datetime
from pathlib import Path
from xml.sax.saxutils import escape

from reportlab.lib import colors
from reportlab.lib.pagesizes import A4, landscape
from reportlab.lib.styles import getSampleStyleSheet
from reportlab.lib.units import mm
from reportlab.platypus import Paragraph, SimpleDocTemplate, Spacer, Table, TableStyle


def write_pdf(path: Path, target_data: dict, results: list[dict], summary: dict, purpose: str = "") -> Path:
    """Écrit un rapport PDF paysage. Les polices standard ne couvrent que le latin."""
    styles = getSampleStyleSheet()
    cell = styles["BodyText"].clone("cell", fontSize=8, leading=10)

    def text(value: object) -> Paragraph:
        # Paragraph interprète un balisage XML : le contenu web doit être échappé.
        return Paragraph(escape(str(value or "-")), cell)

    story = [
        Paragraph("EchoTrace - Rapport d'analyse OSINT", styles["Title"]),
        Paragraph(f"Généré le {datetime.now():%Y-%m-%d %H:%M:%S} - données publiques uniquement",
                  styles["Normal"]),
        Spacer(1, 6 * mm),
        Paragraph("Cible", styles["Heading2"]),
    ]
    if purpose:
        story.append(Paragraph(f"Finalité de la recherche : {escape(purpose)}", styles["Normal"]))
    fields = [(k, v) for k, v in target_data.items() if v]
    if fields:
        table = Table([[text(k.title()), text(v)] for k, v in fields], colWidths=[40 * mm, 200 * mm])
        table.setStyle(TableStyle([("GRID", (0, 0), (-1, -1), 0.25, colors.lightgrey),
                                   ("VALIGN", (0, 0), (-1, -1), "TOP")]))
        story.append(table)

    story += [
        Spacer(1, 6 * mm),
        Paragraph(
            f"Résumé : {summary['total']} résultat(s), {summary['high_confidence']} à haute confiance, "
            f"{len(summary['platforms'])} plateforme(s), confiance moyenne "
            f"{summary['avg_confidence'] * 100:.1f}%.",
            styles["Normal"],
        ),
        Spacer(1, 4 * mm),
        Paragraph("Résultats", styles["Heading2"]),
    ]

    labels = {"confirmed": "Confirmé", "to_check": "À vérifier", "false_positive": "Faux positif"}
    header = [text(h) for h in ("Plateforme", "Confiance", "URL", "Titre", "Pseudo", "Statut", "Note")]
    rows = [header] + [
        [text(r["platform"]), text(f"{r['confidence'] * 100:.0f}%"), text(r["url"]),
         text(r["title"]), text(r["username"]), text(labels.get(r.get("status", ""), "")),
         text(r.get("note", ""))]
        for r in results
    ]
    table = Table(rows, repeatRows=1,
                  colWidths=[26 * mm, 17 * mm, 80 * mm, 60 * mm, 25 * mm, 20 * mm, 40 * mm])
    table.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#d0e2ff")),
        ("GRID", (0, 0), (-1, -1), 0.25, colors.lightgrey),
        ("VALIGN", (0, 0), (-1, -1), "TOP"),
    ]))
    story.append(table)

    SimpleDocTemplate(str(path), pagesize=landscape(A4), title="EchoTrace", author="EchoTrace",
                      leftMargin=10 * mm, rightMargin=10 * mm).build(story)
    return path
