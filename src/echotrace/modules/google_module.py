"""Module de recherche web : requêtes avancées (dorks) sur plusieurs moteurs."""

from __future__ import annotations

import logging

import aiohttp

from echotrace.core.identity import split_pseudos
from echotrace.core.scorer import compute_result_confidence
from echotrace.modules.base import BaseModule, OsintResult, ProgressCallback, random_delay
from echotrace.modules.search import SEARCH_ENGINES, is_cross_link, search
from echotrace.modules.variants import parse_pattern

log = logging.getLogger(__name__)

# Les moteurs bloquent vite les rafales : on plafonne le nombre de requêtes par moteur.
MAX_QUERIES_PER_ENGINE = 20

_SOCIAL_SITES = (
    "linkedin.com", "github.com", "instagram.com", "twitter.com", "reddit.com",
    "tiktok.com", "youtube.com", "medium.com",
)


def generate_queries(target_data: dict) -> list[str]:
    """Requêtes pour tous les pseudos de la cible (3 au maximum), sans doublons."""
    pseudos = [parse_pattern(p).base for p in split_pseudos(target_data.get("pseudo", ""))][:3]
    queries: list[str] = []
    for pseudo in pseudos or [""]:
        queries += _queries_for({**target_data, "pseudo": pseudo})
    return list(dict.fromkeys(queries))


def _queries_for(target_data: dict) -> list[str]:
    """Construit les requêtes à partir des champs renseignés, sans doublons, par priorité."""
    pseudo = target_data.get("pseudo", "").strip()
    nom = target_data.get("nom", "").strip()
    prenom = target_data.get("prenom", "").strip()
    email = target_data.get("email", "").strip()
    entreprise = target_data.get("entreprise", "").strip()
    full_name = f"{prenom} {nom}" if nom and prenom else ""

    queries: list[str] = []

    if pseudo:
        queries.append(f'"{pseudo}"')
        queries += [f'"{pseudo}" site:{site}' for site in _SOCIAL_SITES]
        queries += [f'"{pseudo}" "{word}"' for word in ("profile", "about", "contact")]

    if full_name:
        queries.append(f'"{full_name}"')
        queries += [f'"{full_name}" site:{site}' for site in ("linkedin.com", "github.com", "facebook.com")]
        queries += [f'"{full_name}" "{word}"'
                    for word in ("curriculum vitae", "portfolio", "developer", "engineer")]

    if email:
        queries.append(f'"{email}"')
        queries += [f'"{email}" site:{site}' for site in ("linkedin.com", "github.com")]
        queries += [f'"{email}" "{word}"' for word in ("leaked", "breach", "pastebin")]

    if entreprise:
        if pseudo:
            queries += [f'"{pseudo}" "{entreprise}"', f'"{pseudo}" site:linkedin.com "{entreprise}"']
        if full_name:
            queries += [f'"{full_name}" "{entreprise}"',
                        f'"{full_name}" site:linkedin.com "{entreprise}"']

    if pseudo:
        queries += [f'"{pseudo}" filetype:{ext}' for ext in ("pdf", "doc", "txt")]

    return list(dict.fromkeys(queries))


class GoogleModule(BaseModule):
    name = "google"
    description = "Recherche Google avancée avec dorks"
    requires = ["pseudo", "nom", "prenom", "email", "entreprise"]

    async def run(
        self,
        target_data: dict,
        session: aiohttp.ClientSession,
        progress_cb: ProgressCallback | None = None,
    ) -> list[OsintResult]:
        queries = generate_queries(target_data)[:MAX_QUERIES_PER_ENGINE]
        if not queries:
            return []

        total = len(queries) * len(SEARCH_ENGINES)
        done = 0
        results: dict[str, OsintResult] = {}  # dédoublonnage par URL

        for engine in SEARCH_ENGINES:
            for query in queries:
                if progress_cb:
                    progress_cb(f"Recherche {engine}: {query[:50]}", done / total * 100)
                for hit in await search(session, engine, query):
                    if hit.url in results:
                        continue
                    confidence = compute_result_confidence(
                        "google", {"http_200": True, "cross_link": is_cross_link(hit.url)}
                    )
                    results[hit.url] = OsintResult(
                        module=self.name,
                        platform=engine,
                        url=hit.url,
                        title=hit.title,
                        confidence=confidence,
                        data={"search_engine": engine, "query": query, "snippet": hit.snippet},
                    )
                done += 1
                await random_delay()
        return list(results.values())
