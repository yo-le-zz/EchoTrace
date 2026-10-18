"""Interface commune des modules OSINT."""

from __future__ import annotations

from abc import ABC, abstractmethod
from collections.abc import Callable
from dataclasses import dataclass, field

import aiohttp

# `random_delay`, `random_headers` et `fetch` sont ré-exportés pour les modules.
from echotrace.network import fetch, random_delay, random_headers

__all__ = [
    "BaseModule",
    "OsintResult",
    "ProgressCallback",
    "fetch",
    "random_delay",
    "random_headers",
]

ProgressCallback = Callable[[str, float], None]


@dataclass
class OsintResult:
    """Un résultat OSINT standardisé."""

    module: str
    platform: str
    url: str
    title: str = ""
    username: str = ""
    confidence: float = 0.0
    data: dict = field(default_factory=dict)

    def to_dict(self) -> dict:
        return {
            "module": self.module,
            "platform": self.platform,
            "url": self.url,
            "title": self.title,
            "username": self.username,
            "confidence": self.confidence,
            "data": self.data,
        }


class BaseModule(ABC):
    """Classe de base de tous les modules OSINT.

    Un module déclare dans `requires` les champs de la cible qui le déclenchent
    et implémente `run`. Voir docs/modules.md pour en ajouter un.
    """

    name: str = "base"
    description: str = ""
    requires: list[str] = []  # le module s'exécute si au moins un de ces champs est rempli

    def can_run(self, target_data: dict) -> bool:
        """Indique si le module a de quoi travailler avec les données fournies."""
        return any(target_data.get(req) for req in self.requires)

    @abstractmethod
    async def run(
        self,
        target_data: dict,
        session: aiohttp.ClientSession,
        progress_cb: ProgressCallback | None = None,
    ) -> list[OsintResult]:
        """Lance le module. `progress_cb(message, pourcentage)` est facultatif."""
