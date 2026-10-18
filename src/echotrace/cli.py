"""Interface en ligne de commande : `echotrace-cli`. Même moteur que l'interface graphique.

Codes de sortie : 0 succès ; 1 erreur ; 2 saisie invalide ; 3 analyse réussie avec de nouveaux
résultats depuis la précédente analyse de la même cible (pratique pour une tâche planifiée).
"""

from __future__ import annotations

import argparse
import asyncio
import json
import sys
from pathlib import Path

from echotrace import __version__
from echotrace.app import purge_expired, setup_logging
from echotrace.config.settings import get_settings
from echotrace.core.compare import diff_results, format_diff
from echotrace.core.engine import EchoTraceEngine, build_summary
from echotrace.core.identity import PURPOSES
from echotrace.database import db
from echotrace.reports import ReportGenerator

EXPORT_KINDS = ("html", "json", "csv", "pdf", "graph")
EXIT_OK, EXIT_ERROR, EXIT_INVALID, EXIT_NEW_RESULTS = 0, 1, 2, 3


def resolve_purpose(value: str) -> str | None:
    """Accepte le numéro (1-5) ou le texte exact d'une finalité ; None si inconnue."""
    if value.isdigit() and 1 <= int(value) <= len(PURPOSES):
        return PURPOSES[int(value) - 1]
    return value if value in PURPOSES else None


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="echotrace-cli", description="EchoTrace en ligne de commande.")
    parser.add_argument("--version", action="version", version=f"EchoTrace {__version__}")
    sub = parser.add_subparsers(dest="command", required=True)

    run = sub.add_parser("run", help="lancer une analyse")
    run.add_argument("--pseudo", action="append", default=[], help="répétable ; « nom. » active le mode joker")
    run.add_argument("--email")
    run.add_argument("--phone", dest="telephone")
    run.add_argument("--first", dest="prenom")
    run.add_argument("--last", dest="nom")
    run.add_argument("--city", dest="ville")
    run.add_argument("--company", dest="entreprise")
    run.add_argument("--photo", action="append", default=[], help="fichier ou URL, répétable")
    run.add_argument("--purpose", required=True, help="finalité : numéro 1-5 (voir `purposes`) ou texte exact")
    _add_output_options(run)

    rescan = sub.add_parser("rescan", help="relancer une analyse passée et la comparer")
    rescan.add_argument("id", type=int)
    _add_output_options(rescan)

    sub.add_parser("purposes", help="liste des finalités acceptées")
    sub.add_parser("list", help="historique des analyses")
    show = sub.add_parser("show", help="afficher les résultats d'une analyse")
    show.add_argument("id", type=int)
    show.add_argument("--min-confidence", type=float, default=0.0)
    diff = sub.add_parser("diff", help="comparer deux analyses")
    diff.add_argument("old", type=int)
    diff.add_argument("new", type=int)
    purge = sub.add_parser("purge", help="supprimer les analyses anciennes")
    purge.add_argument("--days", type=int, help="défaut : durée de conservation des réglages")
    export = sub.add_parser("export-data", help="exporter toutes les données stockées (droit d'accès)")
    export.add_argument("file", type=Path)
    erase = sub.add_parser("erase", help="effacer toutes les données (droit à l'effacement)")
    erase.add_argument("--yes", action="store_true", help="confirmer sans question")
    return parser


def _add_output_options(parser: argparse.ArgumentParser) -> None:
    parser.add_argument("--export", default="", help=f"formats séparés par des virgules : {', '.join(EXPORT_KINDS)}")
    parser.add_argument("--out", type=Path, help="dossier des exports (défaut : réglages)")
    parser.add_argument("--min-confidence", type=float, default=0.0)
    parser.add_argument("--quiet", action="store_true", help="n'affiche ni progression ni tableau")


def print_table(rows: list[dict]) -> None:
    for r in rows:
        status = f" [{r['status']}]" if r.get("status") else ""
        print(f"{r['confidence']:.2f}  {r['platform']:<18} {r['url'] or r['title']}{status}")


def export_reports(result: dict, kinds: list[str], out: Path | None, min_confidence: float) -> list[str]:
    rows = [r for r in result["results"] if r["confidence"] >= min_confidence and r.get("status") != "false_positive"]
    generator = ReportGenerator(out or get_settings().export_path)
    summary, target, purpose = build_summary(rows), result["target"], result["purpose"]
    makers = {
        "html": lambda: generator.generate_html_report(target, rows, summary, purpose=purpose),
        "json": lambda: generator.generate_json_report(target, rows, summary, purpose=purpose),
        "csv": lambda: generator.generate_csv_report(rows),
        "pdf": lambda: generator.generate_pdf_report(target, rows, summary, purpose=purpose),
        "graph": lambda: generator.generate_network_graph(rows),
    }
    return [path for kind in kinds if (path := makers[kind]())]


def analyze(target: dict, purpose: str, args: argparse.Namespace) -> int:
    kinds = [k.strip() for k in args.export.split(",") if k.strip()]
    unknown = [k for k in kinds if k not in EXPORT_KINDS]
    if unknown:
        print(f"Format(s) d'export inconnu(s) : {', '.join(unknown)}", file=sys.stderr)
        return EXIT_INVALID

    def progress(message: str, percent: float) -> None:
        if not args.quiet:
            print(f"{percent:5.1f}%  {message}", file=sys.stderr)

    result = asyncio.run(EchoTraceEngine().run_analysis(target, progress, purpose=purpose))
    if not result["success"]:
        print(result["error"], file=sys.stderr)
        return EXIT_INVALID if result["target_id"] is None else EXIT_ERROR

    shown = [r for r in result["results"] if r["confidence"] >= args.min_confidence]
    if not args.quiet:
        print_table(shown)
    print(f"{len(shown)} résultat(s) (analyse n°{result['target_id']}, {result['duration']:.1f}s)")
    for module, error in result["errors"].items():
        print(f"module {module} en erreur : {error}", file=sys.stderr)
    for path in export_reports(result, kinds, args.out, args.min_confidence):
        print(f"export : {path}")

    diff = result["diff"]
    if diff is not None:
        print(format_diff(diff))
        if diff.appeared:
            return EXIT_NEW_RESULTS
    return EXIT_OK


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    setup_logging()
    purge_expired()
    command = args.command

    if command == "purposes":
        for number, purpose in enumerate(PURPOSES, 1):
            print(f"{number}. {purpose}")
    elif command == "run":
        purpose = resolve_purpose(args.purpose)
        if purpose is None:
            print("Finalité inconnue : voir `echotrace-cli purposes`.", file=sys.stderr)
            return EXIT_INVALID
        target = {key: getattr(args, key) for key in ("email", "telephone", "prenom", "nom", "ville", "entreprise")
                  if getattr(args, key)}
        if args.pseudo:
            target["pseudo"] = "\n".join(args.pseudo)
        if args.photo:
            target["photo"] = "\n".join(args.photo)
        return analyze(target, purpose, args)
    elif command == "rescan":
        stored = db.get_target(args.id)
        if stored is None:
            print(f"Analyse {args.id} introuvable.", file=sys.stderr)
            return EXIT_INVALID
        return analyze(stored["data"], stored["purpose"] or PURPOSES[0], args)
    elif command == "list":
        for t in db.list_targets():
            print(f"{t['id']:>4}  {t['label']:<24} {t['results_count']:>4} résultat(s)  {t['purpose']}")
    elif command == "show":
        rows = [r for r in db.get_results(args.id) if r["confidence"] >= args.min_confidence]
        print_table(rows)
    elif command == "diff":
        print(format_diff(diff_results(db.get_results(args.old), db.get_results(args.new))))
    elif command == "purge":
        days = args.days if args.days is not None else get_settings().retention_days
        print(f"{db.purge_older_than(days)} analyse(s) supprimée(s).")
    elif command == "export-data":
        args.file.write_text(json.dumps(db.export_everything(), indent=2, ensure_ascii=False, default=str),
                             encoding="utf-8")
        print(f"Données exportées : {args.file}")
    elif command == "erase":
        if not args.yes and input("Tout effacer définitivement ? [oui/non] ").strip().lower() != "oui":
            return EXIT_ERROR
        db.erase_everything()
        print("Toutes les données ont été effacées.")
    return EXIT_OK


if __name__ == "__main__":
    sys.exit(main())
