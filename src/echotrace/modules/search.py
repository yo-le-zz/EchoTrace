"""Recherche web via les moteurs publics (HTML), partagée par les modules."""

from __future__ import annotations

from dataclasses import dataclass
from urllib.parse import parse_qs, quote, urlparse

import aiohttp
from bs4 import BeautifulSoup

from echotrace.network import fetch

# moteur -> (modèle d'URL, sélecteur CSS d'un résultat)
SEARCH_ENGINES: dict[str, tuple[str, str]] = {
    "Google": ("https://www.google.com/search?q={}", "div.g"),
    "Bing": ("https://www.bing.com/search?q={}", "li.b_algo"),
    "DuckDuckGo": ("https://duckduckgo.com/html/?q={}", "div.result"),
}

# Domaines dont un lien renforce la corrélation d'un résultat.
CROSS_LINK_DOMAINS = (
    "linkedin.com", "github.com", "instagram.com", "twitter.com", "x.com", "reddit.com",
    "youtube.com",
)


@dataclass
class SearchHit:
    title: str
    url: str
    snippet: str


def clean_url(raw: str) -> str:
    """Extrait l'URL réelle d'un lien de redirection Google ou DuckDuckGo.

    Retourne une chaîne vide si le lien n'est pas en http(s) : un lien
    `javascript:` ou `data:` ne doit jamais atteindre les rapports.
    """
    url = raw.strip()
    if url.startswith("//"):
        url = "https:" + url
    parsed = urlparse(url)
    query = parse_qs(parsed.query)
    if parsed.path == "/url" and "q" in query:  # redirection Google
        url = query["q"][0]
    elif "uddg" in query:  # redirection DuckDuckGo
        url = query["uddg"][0]
    return url if urlparse(url).scheme in ("http", "https") else ""


def parse_hits(html: str, selector: str, limit: int = 10) -> list[SearchHit]:
    """Extrait titre, URL et extrait des premiers résultats d'une page de moteur."""
    soup = BeautifulSoup(html, "html.parser")
    hits: list[SearchHit] = []
    for block in soup.select(selector)[:limit]:
        link = block.find("a")
        if link is None:
            continue
        url = clean_url(link.get("href", ""))
        if not url:
            continue
        title_node = block.find("h3") or link
        hits.append(
            SearchHit(
                title=title_node.get_text(strip=True),
                url=url,
                snippet=block.get_text(" ", strip=True)[:200],
            )
        )
    return hits


async def search(session: aiohttp.ClientSession, engine: str, query: str,
                 limit: int = 10) -> list[SearchHit]:
    """Interroge un moteur ; liste vide si le moteur refuse ou ne répond pas."""
    template, selector = SEARCH_ENGINES[engine]
    response = await fetch(session, template.format(quote(query)), timeout=15)
    if response is None or response.status != 200:
        return []
    return parse_hits(response.text, selector, limit)


def is_cross_link(url: str) -> bool:
    host = urlparse(url).hostname or ""
    return any(host == domain or host.endswith("." + domain) for domain in CROSS_LINK_DOMAINS)
