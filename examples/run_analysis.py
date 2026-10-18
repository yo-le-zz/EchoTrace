"""Lance une analyse sans interface graphique et exporte le rapport HTML.

    uv run python examples/run_analysis.py <pseudo> <email>

Les requêtes partent réellement vers les sites publics : ne l'utilisez que sur vous-même
ou avec l'accord de la personne concernée.
"""

import asyncio
import sys

from echotrace.config import get_settings
from echotrace.core.engine import EchoTraceEngine
from echotrace.reports import ReportGenerator


async def main(username: str, email: str) -> None:
    engine = EchoTraceEngine()
    target = {"pseudo": username, "email": email}
    result = await engine.run_analysis(target, lambda message, percent: print(f"{percent:5.1f}%  {message}"))

    if not result["success"]:
        sys.exit(result["error"])
    print(f"{result['results_count']} résultat(s) en {result['duration']:.1f}s")
    for module, error in result["errors"].items():
        print(f"module {module} en erreur : {error}")

    report = ReportGenerator(get_settings().export_path)
    print(report.generate_html_report(target, result["results"], result["summary"]))


if __name__ == "__main__":
    if len(sys.argv) != 3:
        sys.exit("usage : run_analysis.py <pseudo> <email>")
    asyncio.run(main(sys.argv[1], sys.argv[2]))
