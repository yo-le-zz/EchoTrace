"""Vérification des profils trouvés : on relit la page publique pour y chercher des indices.

Indices recherchés (aucun n'est une preuve) :
  - nom : le prénom et le nom de la cible apparaissent dans le titre ou la description ;
  - entreprise, ville : idem ;
  - avatar : l'image du profil est la même image (empreinte proche) qu'une des photos fournies.
    C'est une comparaison de fichiers image, pas de la reconnaissance faciale.

Une page de connexion (réseau qui masque le profil) est détectée : sa confiance est plafonnée.
"""

from __future__ import annotations

import asyncio
import logging
import re
import unicodedata
from dataclasses import dataclass, field
from urllib.parse import urljoin

import aiohttp
from bs4 import BeautifulSoup

from echotrace.core.identity import split_photos
from echotrace.database import db
from echotrace.modules.base import ProgressCallback, fetch
from echotrace.modules.image_module import SAME_IMAGE_DISTANCE, hash_distance, image_hash, load_image

log = logging.getLogger(__name__)

MAX_PROFILES = 40
MAX_PHOTOS = 5
WALL_CAP = 0.5
BONUS = {"name": 0.15, "company": 0.10, "location": 0.05, "avatar": 0.30}
LABELS = {
    "name": "nom présent dans le profil",
    "company": "entreprise présente",
    "location": "ville présente",
    "avatar": "même image que l'une de vos photos",
}
_WALL_MARKERS = ("log in", "login", "sign in", "sign up", "se connecter", "connexion",
                 "inscription", "create an account", "join ")


@dataclass
class PageInfo:
    title: str = ""
    description: str = ""
    image_url: str = ""
    text: str = ""
    wall: bool = False
    signals: list[str] = field(default_factory=list)


def normalize(text: str) -> str:
    """Minuscules sans accents ni ponctuation, pour comparer « Hélène » et « helene »."""
    decomposed = unicodedata.normalize("NFKD", text.lower())
    stripped = "".join(c for c in decomposed if not unicodedata.combining(c))
    return re.sub(r"[^a-z0-9]+", " ", stripped).strip()


def _meta(soup: BeautifulSoup, *names: str) -> str:
    for name in names:
        tag = soup.find("meta", attrs={"property": name}) or soup.find("meta", attrs={"name": name})
        if tag and tag.get("content"):
            return str(tag["content"]).strip()
    return ""


def parse_profile_page(html: str, base_url: str, username: str = "") -> PageInfo:
    """Titre, description et image d'un profil ; détecte les pages de connexion."""
    soup = BeautifulSoup(html, "html.parser")
    title = _meta(soup, "og:title", "twitter:title") or (soup.title.get_text(strip=True) if soup.title else "")
    description = _meta(soup, "og:description", "description", "twitter:description")
    image = _meta(soup, "og:image", "twitter:image")
    text = normalize(f"{title} {description}")
    wall = any(marker in f" {text} " or marker in f"{title} {description}".lower() for marker in _WALL_MARKERS)
    # Si le pseudo apparaît, le profil est lisible malgré un bouton « connexion » dans la page.
    if wall and username and normalize(username) in text:
        wall = False
    return PageInfo(title, description, urljoin(base_url, image) if image else "", text, wall)


def find_signals(info: PageInfo, target: dict) -> list[str]:
    """Indices (clés de BONUS, sauf `avatar`) trouvés dans le titre et la description."""
    signals = []
    first, last = normalize(target.get("prenom", "")), normalize(target.get("nom", ""))
    if first and last and re.search(rf"\b{re.escape(first)}\b", info.text) \
            and re.search(rf"\b{re.escape(last)}\b", info.text):
        signals.append("name")
    company = normalize(target.get("entreprise", ""))
    if company and re.search(rf"\b{re.escape(company)}\b", info.text):
        signals.append("company")
    city = normalize(target.get("ville", ""))
    if city and re.search(rf"\b{re.escape(city)}\b", info.text):
        signals.append("location")
    return signals


def adjust_confidence(base: float, signals: list[str], wall: bool) -> float:
    """Ajoute le bonus de chaque indice ; une page de connexion plafonne la confiance."""
    confidence = min(1.0, base + sum(BONUS[s] for s in signals))
    return round(min(confidence, WALL_CAP) if wall else confidence, 3)


async def _photo_hashes(session: aiohttp.ClientSession, target: dict) -> list[str]:
    hashes = []
    for source in split_photos(target.get("photo"))[:MAX_PHOTOS]:
        data = await load_image(session, source)
        digest = image_hash(data) if data else None
        if digest:
            hashes.append(digest)
    return hashes


async def verify_rows(
    session: aiohttp.ClientSession,
    rows: list[dict],
    target: dict,
    progress_cb: ProgressCallback | None = None,
) -> int:
    """Relit les profils trouvés par le module pseudo et met leur confiance à jour en base.

    Retourne le nombre de profils effectivement lus.
    """
    profiles = sorted((r for r in rows if r["module"] == "username" and r["url"].startswith("http")),
                      key=lambda r: r["confidence"], reverse=True)[:MAX_PROFILES]
    if not profiles:
        return 0
    photo_hashes = await _photo_hashes(session, target)
    semaphore = asyncio.Semaphore(8)
    read = 0

    async def verify(row: dict) -> bool:
        async with semaphore:
            response = await fetch(session, row["url"], timeout=10)
            if response is None or response.status != 200:
                return False
            info = parse_profile_page(response.text, response.url, row["username"])
            signals = find_signals(info, target)
            if photo_hashes and info.image_url and not info.wall:
                avatar = await load_image(session, info.image_url)
                digest = image_hash(avatar) if avatar else None
                if digest and any(hash_distance(digest, h) <= SAME_IMAGE_DISTANCE for h in photo_hashes):
                    signals.append("avatar")
            data = dict(row["data"])
            data.update(signals=[LABELS[s] for s in signals], page_title=info.title[:120])
            if info.wall:
                data["verifiable"] = False
            confidence = adjust_confidence(row["confidence"], signals, info.wall)
            db.update_result(row["id"], confidence, data)
            row["confidence"], row["data"] = confidence, data
            return True

    tasks = [asyncio.create_task(verify(row)) for row in profiles]
    try:
        for done, finished in enumerate(asyncio.as_completed(tasks), 1):
            read += await finished
            if progress_cb:
                progress_cb(f"Vérification des profils : {done}/{len(tasks)}", done / len(tasks) * 100)
    finally:
        for task in tasks:
            if not task.done():
                task.cancel()
    return read
