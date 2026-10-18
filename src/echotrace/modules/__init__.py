"""Modules OSINT. Pour en ajouter un, voir docs/modules.md."""

from __future__ import annotations

import importlib.util
import logging

from echotrace import paths
from echotrace.modules.base import BaseModule, OsintResult
from echotrace.modules.email_module import EmailModule
from echotrace.modules.google_module import GoogleModule
from echotrace.modules.image_module import ImageModule
from echotrace.modules.phone_module import PhoneModule
from echotrace.modules.username_module import UsernameModule

log = logging.getLogger(__name__)

# Ordre d'exécution et d'affichage des modules intégrés.
ALL_MODULES: list[type[BaseModule]] = [
    UsernameModule,
    GoogleModule,
    ImageModule,
    EmailModule,
    PhoneModule,
]


def load_plugins() -> list[type[BaseModule]]:
    """Modules écrits par l'utilisateur dans `<dossier de configuration>/plugins/*.py`.

    Chaque fichier est exécuté tel quel : n'y placez que du code en lequel vous avez
    confiance. Un plugin défectueux est ignoré et journalisé, il n'empêche pas le démarrage.
    """
    folder = paths.config_dir() / "plugins"
    if not folder.is_dir():
        return []
    found: list[type[BaseModule]] = []
    for path in sorted(folder.glob("*.py")):
        if path.name.startswith("_"):
            continue
        try:
            spec = importlib.util.spec_from_file_location(f"echotrace_plugin_{path.stem}", path)
            module = importlib.util.module_from_spec(spec)
            spec.loader.exec_module(module)
        except Exception:
            log.exception("Plugin ignoré : %s", path.name)
            continue
        found += [
            obj for obj in vars(module).values()
            if isinstance(obj, type) and issubclass(obj, BaseModule)
            and obj is not BaseModule and obj.__module__ == module.__name__
        ]
    return found


def build_modules() -> list[BaseModule]:
    """Instances des modules intégrés suivies de celles des plugins."""
    instances: list[BaseModule] = []
    for cls in [*ALL_MODULES, *load_plugins()]:
        try:
            instances.append(cls())
        except Exception:
            log.exception("Module %s impossible à instancier", cls.__name__)
    return instances


__all__ = [
    "ALL_MODULES",
    "BaseModule",
    "EmailModule",
    "GoogleModule",
    "ImageModule",
    "OsintResult",
    "PhoneModule",
    "UsernameModule",
    "build_modules",
    "load_plugins",
]
