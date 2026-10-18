"""Emplacements des fichiers de l'application, identiques sur Windows, Linux et macOS.

Rien n'est écrit à côté du code ou de l'exécutable : un binaire PyInstaller peut
se trouver dans un dossier en lecture seule (Program Files, AppImage, /usr/bin...).
La variable d'environnement ECHOTRACE_HOME regroupe tout dans un seul dossier
(mode portable, tests, CI).
"""

from __future__ import annotations

import os
from pathlib import Path

from platformdirs import (
    user_cache_path,
    user_config_path,
    user_data_path,
    user_documents_path,
    user_log_path,
)

APP_NAME = "EchoTrace"
ENV_HOME = "ECHOTRACE_HOME"


def _override() -> Path | None:
    value = os.environ.get(ENV_HOME, "").strip()
    return Path(value).expanduser() if value else None


def _ensure(path: Path) -> Path:
    path.mkdir(parents=True, exist_ok=True)
    return path


def config_dir() -> Path:
    """Dossier de la configuration utilisateur (clés API incluses)."""
    base = _override()
    return _ensure(base / "config" if base else user_config_path(APP_NAME, appauthor=False))


def data_dir() -> Path:
    """Dossier de la base SQLite (cibles, recherches, résultats)."""
    base = _override()
    return _ensure(base / "data" if base else user_data_path(APP_NAME, appauthor=False))


def cache_dir() -> Path:
    """Dossier des données jetables, recréables à tout moment."""
    base = _override()
    return _ensure(base / "cache" if base else user_cache_path(APP_NAME, appauthor=False))


def log_dir() -> Path:
    base = _override()
    return _ensure(base / "logs" if base else user_log_path(APP_NAME, appauthor=False))


def default_export_dir() -> Path:
    """Dossier d'export par défaut (Documents/EchoTrace)."""
    base = _override()
    return _ensure(base / "exports" if base else user_documents_path() / APP_NAME)


def config_file() -> Path:
    return config_dir() / "echotrace_config.json"


def database_file() -> Path:
    return data_dir() / "echotrace.db"
