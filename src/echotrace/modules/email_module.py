"""Module email : fuites connues (HIBP), fournisseur et mentions publiques."""

from __future__ import annotations

import json
import logging
import re
from urllib.parse import quote

import aiohttp

from echotrace.config.settings import get_settings
from echotrace.core.scorer import compute_result_confidence
from echotrace.modules.base import (
    BaseModule,
    OsintResult,
    ProgressCallback,
    fetch,
    random_delay,
)
from echotrace.modules.search import is_cross_link, search

log = logging.getLogger(__name__)

_EMAIL_RE = re.compile(r"^[^@\s]+@[^@\s]+\.[^@\s]+$")
HIBP_URL = "https://haveibeenpwned.com/api/v3/breachedaccount/{}?truncateResponse=false"
KNOWN_PROVIDERS = {
    "gmail.com", "yahoo.com", "outlook.com", "hotmail.com",
    "protonmail.com", "proton.me", "icloud.com", "mail.com", "aol.com",
}
PUBLIC_QUERIES = ('"{}"', '"{}" site:github.com', '"{}" site:linkedin.com')


class EmailModule(BaseModule):
    name = "email"
    description = "Analyse d'email: domaine, fuites de données, mentions publiques"
    requires = ["email"]

    async def run(
        self,
        target_data: dict,
        session: aiohttp.ClientSession,
        progress_cb: ProgressCallback | None = None,
    ) -> list[OsintResult]:
        email = target_data.get("email", "").strip()
        if not _EMAIL_RE.match(email):
            return []

        def report(message: str, percent: float) -> None:
            if progress_cb:
                progress_cb(message, percent)

        results: list[OsintResult] = []
        report("Vérification des fuites de données...", 10)
        results += await self._check_breaches(session, email, report)
        report("Analyse du domaine...", 50)
        results += self._analyze_domain(email.rsplit("@", 1)[1].lower())
        report("Recherche publique de l'email...", 70)
        results += await self._search_public(session, email, report)
        return results

    async def _check_breaches(self, session, email: str, report) -> list[OsintResult]:
        """Interroge l'API HIBP v3, qui exige une clé API."""
        api_key = get_settings().hibp_api_key
        if not api_key:
            report("Clé HaveIBeenPwned absente : vérification des fuites ignorée.", 30)
            return []

        response = await fetch(
            session,
            HIBP_URL.format(quote(email, safe="")),
            headers={"hibp-api-key": api_key, "user-agent": "EchoTrace", "Accept": "application/json"},
            timeout=15,
        )
        if response is None:
            log.warning("HIBP injoignable")
            return []
        if response.status == 404:  # aucune fuite connue
            return [self._breach_result(email, [])]
        if response.status != 200:
            log.warning("HIBP a répondu %s (clé invalide ou quota dépassé)", response.status)
            report(f"HaveIBeenPwned a répondu {response.status} : vérification ignorée.", 30)
            return []
        try:
            breaches = json.loads(response.text)
        except ValueError:
            log.warning("Réponse HIBP illisible")
            return []
        await random_delay()
        return [self._breach_result(email, breaches)]

    def _breach_result(self, email: str, breaches: list[dict]) -> OsintResult:
        found = bool(breaches)
        confidence = compute_result_confidence("email", {"email_match": True})
        return OsintResult(
            module=self.name,
            platform="HaveIBeenPwned",
            url="https://haveibeenpwned.com/",
            title=f"{len(breaches)} fuite(s) connue(s)" if found else "Aucune fuite connue",
            confidence=confidence if found else confidence * 0.7,
            data={
                "email": email,
                "breach_count": len(breaches),
                "breaches": [
                    {
                        "name": b.get("Name", ""),
                        "date": b.get("BreachDate", ""),
                        "data_classes": b.get("DataClasses", []),
                    }
                    for b in breaches
                ],
            },
        )

    def _analyze_domain(self, domain: str) -> list[OsintResult]:
        confidence = compute_result_confidence("email", {"email_match": True})
        if domain in KNOWN_PROVIDERS:
            return [
                OsintResult(
                    module=self.name,
                    platform=f"Email Provider ({domain})",
                    url=f"https://{domain}",
                    title=f"Fournisseur email: {domain}",
                    confidence=confidence * 0.8,
                    data={"domain": domain, "provider_type": "public"},
                )
            ]
        # Domaine personnel ou professionnel : un WHOIS est une piste utile.
        return [
            OsintResult(
                module=self.name,
                platform="WHOIS",
                url=f"https://www.whois.com/whois/{quote(domain, safe='')}",
                title=f"Informations WHOIS: {domain}",
                confidence=confidence * 0.6,
                data={"domain": domain, "provider_type": "custom"},
            )
        ]

    async def _search_public(self, session, email: str, report) -> list[OsintResult]:
        """Cherche les pages qui mentionnent réellement l'adresse (extrait ou titre)."""
        needle = email.lower()
        results: dict[str, OsintResult] = {}
        for index, template in enumerate(PUBLIC_QUERIES):
            query = template.format(email)
            for hit in await search(session, "DuckDuckGo", query):
                if hit.url in results or needle not in f"{hit.title} {hit.snippet}".lower():
                    continue
                confidence = compute_result_confidence(
                    "email", {"email_match": True, "cross_link": is_cross_link(hit.url)}
                )
                results[hit.url] = OsintResult(
                    module=self.name,
                    platform="Public Search",
                    url=hit.url,
                    title=hit.title or f"Mention de {email}",
                    confidence=confidence * 0.5,
                    data={"email": email, "search_query": query, "snippet": hit.snippet},
                )
            report(f"Recherche {index + 1}/{len(PUBLIC_QUERIES)}",
                   70 + (index + 1) / len(PUBLIC_QUERIES) * 30)
            await random_delay()
        return list(results.values())
