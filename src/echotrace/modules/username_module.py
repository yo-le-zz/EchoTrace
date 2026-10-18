"""Module pseudo : présence d'un pseudo (et de ses variantes) sur des plateformes publiques.

Deux modes de saisie :
  - pseudo normal  (`yolezz`)  : le pseudo et ses variantes (yo_le_zz, yo-le-zz, yole.zz...) ;
  - mode joker     (`yolezz.`) : les pseudos de la forme `yolezz.<mot>` repérés par les moteurs
                                 de recherche, plus une liste de suffixes courants.

Avec « deux passes » (réglage par défaut), chaque variante est d'abord testée sur les sites
rapides et fiables ; seules celles qui existent quelque part sont testées sur tous les sites.
"""

from __future__ import annotations

import asyncio
import logging
from urllib.parse import quote, urlparse

import aiohttp

from echotrace.config.settings import get_settings
from echotrace.core.identity import split_pseudos
from echotrace.core.scorer import compute_result_confidence
from echotrace.database import db
from echotrace.modules.base import BaseModule, OsintResult, ProgressCallback, fetch, random_delay
from echotrace.modules.search import search
from echotrace.modules.sites import RELIABILITY_FACTOR, Site, load_sites
from echotrace.modules.variants import (
    Pattern,
    extract_handles,
    generate_variants,
    parse_pattern,
    wildcard_candidates,
)

log = logging.getLogger(__name__)

# Moteurs interrogés pour repérer des pseudos « base.mot » : Google bloque trop vite.
DISCOVERY_ENGINES = ("Bing", "DuckDuckGo")


def is_found(site: Site, requested_url: str, status: int, final_url: str, text: str) -> bool:
    """Interprète une réponse HTTP selon le type de vérification du site."""
    if status != 200:
        return False
    if site.check == "body_not_contains":
        return site.marker not in text
    if site.check == "body_contains":
        return site.marker in text
    # status_200 : beaucoup de sites redirigent un profil absent vers leur accueil
    requested_path = urlparse(requested_url).path
    return not (urlparse(final_url).path in ("", "/") and requested_path not in ("", "/"))


async def discover_handles(session: aiohttp.ClientSession, pattern: Pattern) -> set[str]:
    """Pseudos `base<sep>mot` visibles dans les résultats publics des moteurs de recherche."""
    stem = pattern.base + pattern.separator
    queries = [f'"{stem}*"', f'"{stem}"', f"{stem} profile"]
    found: set[str] = set()
    for engine in DISCOVERY_ENGINES:
        for query in queries:
            for hit in await search(session, engine, query):
                found |= extract_handles(f"{hit.title} {hit.snippet} {hit.url}", pattern)
            await random_delay()
    return found


class UsernameModule(BaseModule):
    name = "username"
    description = "Recherche de pseudo (variantes, syllabes, mode joker) sur des plateformes publiques"
    requires = ["pseudo"]

    async def run(
        self,
        target_data: dict,
        session: aiohttp.ClientSession,
        progress_cb: ProgressCallback | None = None,
    ) -> list[OsintResult]:
        settings = get_settings()

        def report(message: str, percent: float) -> None:
            if progress_cb:
                progress_cb(message, percent)

        # candidat -> pseudo saisi dont il dérive ; `exact` : les pseudos testés tels que saisis
        origins: dict[str, str] = {}
        exact: set[str] = set()
        discovered_all: set[str] = set()
        for raw in split_pseudos(target_data.get("pseudo", "")):
            pattern = parse_pattern(raw)
            if pattern.wildcard:
                report(f"Recherche de pseudos « {pattern.base}{pattern.separator}… »", 2)
                discovered = await discover_handles(session, pattern)
                discovered_all |= discovered
                names = wildcard_candidates(pattern, discovered, settings.max_username_variations + 30)
                exact.add(pattern.base)
            else:
                names = generate_variants(raw, settings.max_username_variations)
                exact.add(raw)
            for name in names:
                origins.setdefault(name, pattern.base)
        if not origins:
            return []

        sites = load_sites()
        probes = [s for s in sites if s.probe]
        results: list[OsintResult] = []
        two_pass = settings.two_pass and len(origins) > 1 and 0 < len(probes) < len(sites)

        if two_pass:
            first = [(name, site) for name in origins for site in probes]
            hits = await self._check_many(session, first, origins, exact, discovered_all, report, 5, 50)
            results += hits
            alive = {r.username for r in hits} | (exact & origins.keys())
            probe_names = {s.name for s in probes}
            second = [(name, site) for name in origins if name in alive
                      for site in sites if site.name not in probe_names]
            results += await self._check_many(session, second, origins, exact, discovered_all, report, 55, 45)
        else:
            pairs = [(name, site) for name in origins for site in sites]
            results = await self._check_many(session, pairs, origins, exact, discovered_all, report, 5, 95)
        return results

    async def _check_many(self, session, pairs, origins, exact, discovered, report, start, span):
        """Teste des couples (pseudo, site) en parallèle ; `span` % de la barre lui sont attribués."""
        semaphore = asyncio.Semaphore(get_settings().max_concurrent)
        total = len(pairs)
        found: list[OsintResult] = []
        done = 0

        async def check(name: str, site: Site) -> OsintResult | None:
            async with semaphore:
                return await self._check_site(session, origins[name], name, site, exact, discovered)

        tasks = [asyncio.create_task(check(name, site)) for name, site in pairs]
        try:
            for finished in asyncio.as_completed(tasks):
                result = await finished
                done += 1
                if result:
                    found.append(result)
                if done % 10 == 0 or done == total:
                    report(f"Vérification des pseudos : {done}/{total}", start + done / max(total, 1) * span)
        finally:
            # Sur annulation ou erreur, on ne laisse aucune requête orpheline
            for task in tasks:
                if not task.done():
                    task.cancel()
        return found

    async def _check_site(self, session, original: str, username: str, site: Site,
                          exact: set[str], discovered: set[str]) -> OsintResult | None:
        settings = get_settings()
        url = site.url.format(quote(username, safe=""))
        cache_key = f"username:{site.name}:{username}"

        status = 200
        found: bool | None = None
        if settings.cache_enabled:
            cached = db.cache_get(cache_key)
            if cached is not None:
                found, status = cached["found"], cached["status"]

        if found is None:
            response = await fetch(session, url, read_body=site.check != "status_200", timeout=8)
            if response is None:
                return None  # erreur réseau : ni trouvé ni absent, on ne met rien en cache
            status = response.status
            found = is_found(site, url, status, response.url, response.text)
            if settings.cache_enabled:
                db.cache_set(cache_key, {"found": found, "status": status},
                             settings.cache_ttl_hours * 3600)

        if not found:
            return None

        # Une variante ne vaut pas le pseudo exact ; un site peu fiable vaut moins qu'un site fiable.
        checks = {"http_200": True, "profile_exists": True}
        if username in exact:
            checks["username_exact"] = True
        else:
            checks.update(username_exact=False, username_similar=True)
        confidence = compute_result_confidence("username", checks) * RELIABILITY_FACTOR[site.reliability]
        return OsintResult(
            module=self.name,
            platform=site.name,
            url=url,
            title=f"@{username} sur {site.name}",
            username=username,
            confidence=round(confidence, 3),
            data={
                "http_status": status,
                "tested_username": username,
                "original_username": original,
                "reliability": site.reliability,
                "verifiable": site.reliability != "low",
                "discovered_online": username in discovered,
            },
        )
