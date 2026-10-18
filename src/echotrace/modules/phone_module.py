"""Module téléphone : validation du format et mentions publiques du numéro."""

from __future__ import annotations

import logging
import re

import aiohttp

from echotrace.core.scorer import compute_result_confidence
from echotrace.modules.base import BaseModule, OsintResult, ProgressCallback, random_delay
from echotrace.modules.search import search

log = logging.getLogger(__name__)

COUNTRY_CODES = {
    "+33": "France", "+1": "USA/Canada", "+44": "UK", "+49": "Allemagne", "+34": "Espagne",
    "+39": "Italie", "+41": "Suisse", "+31": "Pays-Bas", "+32": "Belgique",
}
# Indicatifs d'une longueur de 1 à 3 chiffres : on teste du plus long au plus court.
_PHONE_RE = re.compile(r"^(\+\d{1,3})(\d+)$")


def normalize_phone(phone: str) -> str:
    """Normalise un numéro au format international ; chaîne vide si non reconnu.

    Un numéro sans indicatif est supposé français (public visé par l'outil).
    """
    cleaned = re.sub(r"[^\d+]", "", phone)
    if cleaned.startswith("00"):
        cleaned = "+" + cleaned[2:]
    if cleaned.startswith("+"):
        return cleaned if 8 <= len(cleaned) <= 16 else ""
    if len(cleaned) == 10 and cleaned.startswith("0"):
        return "+33" + cleaned[1:]
    if len(cleaned) == 9:  # format français sans le 0 initial
        return "+33" + cleaned
    return ""


def analyze_phone_format(phone: str) -> dict:
    """Pays et type de ligne déduits du préfixe et de la longueur du numéro."""
    match = _PHONE_RE.match(phone)
    if not match:
        return {}
    code, number = match.groups()
    # Les codes pays à 1-3 chiffres se chevauchent (+1 / +123) : on prend le plus long connu.
    for length in (4, 3, 2):
        if phone[:length] in COUNTRY_CODES:
            code, number = phone[:length], phone[length:]
            break
    info = {"country": COUNTRY_CODES.get(code, f"Inconnu ({code})"), "country_code": code}

    if code == "+33" and len(number) == 9:
        if number[0] in "67":
            info["type"] = "Mobile"
        elif number[0] in "12345":
            info["type"] = "Fixe"
        else:
            info["type"] = "Autre"
    elif code == "+1" and len(number) == 10:
        info["type"] = "Amérique du Nord"
    else:
        info["type"] = "International"
    return info


def _national_variants(phone: str) -> set[str]:
    """Chiffres seuls sous lesquels le numéro peut apparaître dans une page."""
    digits = phone.lstrip("+")
    variants = {digits}
    if phone.startswith("+33"):
        variants.add("0" + digits[2:])
    return variants


class PhoneModule(BaseModule):
    name = "phone"
    description = "Analyse de numéro: validation, format, et recherche publique"
    requires = ["telephone"]

    async def run(
        self,
        target_data: dict,
        session: aiohttp.ClientSession,
        progress_cb: ProgressCallback | None = None,
    ) -> list[OsintResult]:
        raw = target_data.get("telephone", "").strip()
        phone = normalize_phone(raw)
        if not phone:
            return []

        if progress_cb:
            progress_cb("Analyse du numéro de téléphone...", 10)

        results: list[OsintResult] = []
        info = analyze_phone_format(phone)
        if info:
            confidence = compute_result_confidence("phone", {"phone_match": True})
            results.append(
                OsintResult(
                    module=self.name,
                    platform="Phone Validation",
                    url="",
                    title=f"Numéro valide: {phone}",
                    confidence=confidence * 0.8,
                    data={"original_phone": raw, "normalized_phone": phone, **info},
                )
            )

        results += await self._search_public(session, phone, progress_cb)
        return results

    async def _search_public(self, session, phone: str, progress_cb) -> list[OsintResult]:
        """Cherche les pages dont le titre ou l'extrait contient réellement le numéro."""
        variants = _national_variants(phone)
        national = sorted(variants - {phone.lstrip("+")}) or [phone]
        queries = [f'"{phone}"', *(f'"{n}" "annuaire"' for n in national)]

        results: dict[str, OsintResult] = {}
        for index, query in enumerate(queries):
            if progress_cb:
                progress_cb(f"Recherche {index + 1}/{len(queries)}",
                            70 + index / len(queries) * 30)
            for hit in await search(session, "DuckDuckGo", query):
                digits = re.sub(r"\D", "", f"{hit.title} {hit.snippet}")
                if hit.url in results or not any(v in digits for v in variants):
                    continue
                confidence = compute_result_confidence("phone", {"phone_match": True})
                results[hit.url] = OsintResult(
                    module=self.name,
                    platform="Public Search",
                    url=hit.url,
                    title=hit.title or f"Mention de {phone}",
                    confidence=confidence * 0.4,
                    data={"phone": phone, "search_query": query, "snippet": hit.snippet},
                )
            await random_delay()
        return list(results.values())
