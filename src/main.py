#!/usr/bin/env python3
"""
EchoTrace — OSINT Correlation Engine
Données publiques uniquement / Public data only
"""

import os
import sys
from pathlib import Path


def get_app_dir() -> Path:
    """Retourne le répertoire de l'application."""
    if getattr(sys, "frozen", False):
        return Path(sys.executable).resolve().parent

    return Path(__file__).resolve().parent.parent


def get_resource_dir() -> Path:
    """Retourne le répertoire des ressources embarquées."""
    if "__compiled__" in globals():
        return Path(__file__).resolve().parent

    return get_app_dir()


APP_DIR = get_app_dir()
RESOURCE_DIR = get_resource_dir()

# Permet de retrouver les modules du projet.
sys.path.insert(0, str(APP_DIR))
sys.path.insert(0, str(APP_DIR / "src"))


def check_deps() -> None:
    """Vérifie les dépendances nécessaires à l'application."""
    dependencies = {
        "PyQt6": "PyQt6",
        "aiohttp": "aiohttp",
        "bs4": "beautifulsoup4",
        "requests": "requests",
        "networkx": "networkx",
    }

    missing = []

    for module, package in dependencies.items():
        try:
            __import__(module)
        except ImportError:
            missing.append(package)

    if missing:
        print(
            "[EchoTrace] Dépendances manquantes : "
            + ", ".join(missing),
            file=sys.stderr,
        )

        if getattr(sys, "frozen", False) or "__compiled__" in globals():
            print(
                "Le binaire semble incomplet. "
                "Recompilez l'application avec ses dépendances.",
                file=sys.stderr,
            )
        else:
            print(
                "Installez-les avec : "
                "uv pip install -r requirements.txt",
                file=sys.stderr,
            )

        raise SystemExit(1)


def main() -> None:
    # Configuration HiDPI.
    os.environ.setdefault("QT_AUTO_SCREEN_SCALE_FACTOR", "1")

    check_deps()

    from PyQt6.QtWidgets import QApplication
    from PyQt6.QtGui import QFont

    from ui.main_window import MainWindow

    app = QApplication(sys.argv)
    app.setApplicationName("EchoTrace")
    app.setApplicationVersion("1.0.0")
    app.setOrganizationName("EchoTrace")

    app.setFont(QFont("Segoe UI", 10))

    window = MainWindow()
    window.show()

    sys.exit(app.exec())


if __name__ == "__main__":
    main()