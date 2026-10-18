"""Démarrage de l'application : journalisation puis fenêtre principale."""

from __future__ import annotations

import contextlib
import logging
import sys
from logging.handlers import RotatingFileHandler

from echotrace import __version__, paths


def setup_logging() -> None:
    """Journal tournant dans le dossier de logs de l'utilisateur, plus la console."""
    handlers: list[logging.Handler] = [logging.StreamHandler()]
    # Dossier de logs non inscriptible : la console suffit.
    with contextlib.suppress(OSError):
        handlers.append(
            RotatingFileHandler(paths.log_dir() / "echotrace.log", maxBytes=1_000_000,
                                backupCount=3, encoding="utf-8")
        )
    logging.basicConfig(level=logging.INFO, handlers=handlers,
                        format="%(asctime)s %(levelname)s %(name)s: %(message)s")


def purge_expired() -> int:
    """Supprime les analyses plus anciennes que la durée de conservation choisie (0 = jamais)."""
    from echotrace.config.settings import get_settings
    from echotrace.database import db

    try:
        deleted = db.purge_older_than(get_settings().retention_days)
    except Exception:  # une base illisible ne doit pas empêcher de démarrer
        logging.getLogger(__name__).exception("Purge des analyses anciennes impossible")
        return 0
    if deleted:
        logging.getLogger(__name__).info("%d analyse(s) expirée(s) supprimée(s)", deleted)
    return deleted


def main() -> None:
    setup_logging()
    purge_expired()
    try:
        from PyQt6.QtWidgets import QApplication

        from echotrace.ui.main_window import MainWindow
        from echotrace.ui.theme import apply_theme
    except ImportError as exc:
        print(f"[EchoTrace] Dépendance manquante : {exc}\n"
              "Installez le projet avec : uv sync", file=sys.stderr)
        raise SystemExit(1) from exc

    app = QApplication(sys.argv)
    app.setApplicationName("EchoTrace")
    app.setApplicationVersion(__version__)
    app.setOrganizationName("EchoTrace")
    apply_theme(app)

    window = MainWindow()
    window.show()
    sys.exit(app.exec())


if __name__ == "__main__":
    main()
