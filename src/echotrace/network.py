"""Briques réseau communes : TLS vérifié, session HTTP, en-têtes, proxies, délais."""

from __future__ import annotations

import asyncio
import random
import ssl
import weakref
from dataclasses import dataclass
from functools import lru_cache
from urllib.parse import urlparse

import aiohttp
import certifi

from echotrace.config.settings import get_settings

# Plafond de lecture d'une réponse : évite qu'une page géante épuise la mémoire.
MAX_BODY_BYTES = 2_000_000

USER_AGENTS = [
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) "
    "Chrome/120.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) "
    "Chrome/120.0.0.0 Safari/537.36",
    "Mozilla/5.0 (X11; Linux x86_64; rv:120.0) Gecko/20100101 Firefox/120.0",
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:120.0) Gecko/20100101 Firefox/120.0",
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 14_2) AppleWebKit/605.1.15 (KHTML, like Gecko) "
    "Version/17.2 Safari/605.1.15",
]


@lru_cache(maxsize=1)
def ssl_context() -> ssl.SSLContext:
    """Contexte TLS qui vérifie les certificats.

    Les certificats de certifi évitent de dépendre du magasin système, parfois
    absent ou incomplet dans un binaire PyInstaller sous Linux ou macOS.
    """
    return ssl.create_default_context(cafile=certifi.where())


def create_session() -> aiohttp.ClientSession:
    """Session HTTP configurée d'après les réglages utilisateur."""
    settings = get_settings()
    connector = aiohttp.TCPConnector(limit=settings.max_concurrent * 2, ssl=ssl_context())
    timeout = aiohttp.ClientTimeout(total=settings.request_timeout)
    return aiohttp.ClientSession(connector=connector, timeout=timeout)


def random_headers() -> dict[str, str]:
    return {
        "User-Agent": random.choice(USER_AGENTS),
        "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
        "Accept-Language": "fr-FR,fr;q=0.9,en-US;q=0.8,en;q=0.7",
        # Pas de "br" : aiohttp ne sait décoder Brotli qu'avec un paquet optionnel.
        "Accept-Encoding": "gzip, deflate",
        "DNT": "1",
    }


async def random_delay() -> None:
    """Pause aléatoire entre deux requêtes, bornée par les réglages."""
    settings = get_settings()
    await asyncio.sleep(random.uniform(settings.request_delay_min, settings.request_delay_max))


def pick_proxy() -> str | None:
    """Un proxy tiré au hasard si l'option est activée, sinon None."""
    settings = get_settings()
    if settings.use_proxies and settings.proxy_list:
        return random.choice(settings.proxy_list)
    return None


@dataclass
class HttpResponse:
    status: int
    text: str
    url: str


# Un jeu de sémaphores par session et par hôte : une analyse n'assomme jamais un même site.
_host_limits: weakref.WeakKeyDictionary = weakref.WeakKeyDictionary()


def host_semaphore(session: aiohttp.ClientSession, url: str) -> asyncio.Semaphore:
    limits = _host_limits.setdefault(session, {})
    host = urlparse(url).hostname or ""
    if host not in limits:
        limits[host] = asyncio.Semaphore(get_settings().per_host_limit)
    return limits[host]


async def fetch(
    session: aiohttp.ClientSession,
    url: str,
    *,
    headers: dict[str, str] | None = None,
    timeout: float | None = None,
    read_body: bool = True,
) -> HttpResponse | None:
    """GET tolérant aux pannes : None en cas d'erreur réseau ou de timeout.

    Les annulations (asyncio.CancelledError) ne sont volontairement pas capturées,
    sinon l'arrêt d'une analyse serait ignoré.
    """
    total = timeout or get_settings().request_timeout
    try:
        async with host_semaphore(session, url), session.get(
            url,
            headers=headers or random_headers(),
            timeout=aiohttp.ClientTimeout(total=total),
            allow_redirects=True,
            proxy=pick_proxy(),
        ) as resp:
            text = ""
            if read_body:
                raw = await resp.content.read(MAX_BODY_BYTES)
                # resp.charset évite get_encoding(), qui exige un corps déjà lu via read()
                text = raw.decode(resp.charset or "utf-8", errors="ignore")
            return HttpResponse(resp.status, text, str(resp.url))
    # asyncio.TimeoutError et TimeoutError ne fusionnent qu'à partir de Python 3.11
    except (aiohttp.ClientError, asyncio.TimeoutError, TimeoutError, UnicodeError, LookupError):
        return None
