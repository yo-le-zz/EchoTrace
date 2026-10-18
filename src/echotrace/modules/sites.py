"""Catalogue des sites testés par le module pseudo (fichier JSON + ajouts de l'utilisateur)."""

from __future__ import annotations

import json
import logging
from dataclasses import dataclass
from pathlib import Path

from echotrace import paths

log = logging.getLogger(__name__)

BUNDLED = Path(__file__).parent / "data" / "sites.json"
CHECKS = ("status_200", "body_contains", "body_not_contains")
RELIABILITIES = ("high", "medium", "low")
# Une page de connexion ou une application JS répond 200 pour n'importe quel pseudo.
RELIABILITY_FACTOR = {"high": 1.0, "medium": 0.9, "low": 0.55}


@dataclass(frozen=True)
class Site:
    name: str
    url: str
    check: str = "status_200"
    marker: str = ""
    reliability: str = "medium"
    probe: bool = False
    known_user: str = ""


def _parse(entry: dict, origin: str) -> Site | None:
    """Valide une entrée ; retourne None (et journalise) si elle est inutilisable."""
    try:
        site = Site(
            name=str(entry["name"]),
            url=str(entry["url"]),
            check=str(entry.get("check", "status_200")),
            marker=str(entry.get("marker", "")),
            reliability=str(entry.get("reliability", "medium")),
            probe=bool(entry.get("probe", False)),
            known_user=str(entry.get("known_user", "")),
        )
    except (KeyError, TypeError) as exc:
        log.warning("Site ignoré (%s) : entrée incomplète %s", origin, exc)
        return None
    problems = []
    if site.url.count("{}") != 1 or not site.url.startswith(("http://", "https://")):
        problems.append("l'URL doit être en http(s) et contenir {} une seule fois")
    if site.check not in CHECKS:
        problems.append(f"check inconnu ({site.check})")
    if site.check != "status_200" and not site.marker:
        problems.append("un marqueur est requis")
    if site.reliability not in RELIABILITIES:
        problems.append(f"reliability inconnue ({site.reliability})")
    if problems:
        log.warning("Site ignoré (%s) %s : %s", origin, site.name, "; ".join(problems))
        return None
    return site


def _read(path: Path) -> list[dict]:
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
        sites = data["sites"] if isinstance(data, dict) else data
        return [entry for entry in sites if isinstance(entry, dict)]
    except FileNotFoundError:
        return []
    except (OSError, ValueError, KeyError, TypeError) as exc:
        log.warning("Fichier de sites illisible (%s) : %s", path, exc)
        return []


def load_sites() -> list[Site]:
    """Sites fournis + sites de l'utilisateur ; un site utilisateur du même nom remplace le fourni."""
    merged: dict[str, Site] = {}
    for path in (BUNDLED, paths.config_dir() / "sites.json"):
        for entry in _read(path):
            site = _parse(entry, path.name)
            if site:
                merged[site.name.lower()] = site
    return list(merged.values())
