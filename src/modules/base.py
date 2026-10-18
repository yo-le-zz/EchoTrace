"""
EchoTrace — Base Module Interface
"""

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import List, Optional
import asyncio
import aiohttp
import random
import time
from config.settings import SETTINGS


@dataclass
class OsintResult:
    """Un résultat OSINT standardisé."""
    module:     str
    platform:   str
    url:        str
    title:      str       = ""
    username:   str       = ""
    confidence: float     = 0.0
    data:       dict      = field(default_factory=dict)
    
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


# ─── User agents pool ─────────────────────────────────────────────────────────

USER_AGENTS = [
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
    "Mozilla/5.0 (X11; Linux x86_64; rv:120.0) Gecko/20100101 Firefox/120.0",
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:120.0) Gecko/20100101 Firefox/120.0",
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 14_2) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/17.2 Safari/605.1.15",
]


def random_headers() -> dict:
    return {
        "User-Agent": random.choice(USER_AGENTS),
        "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
        "Accept-Language": "fr-FR,fr;q=0.9,en-US;q=0.8,en;q=0.7",
        "Accept-Encoding": "gzip, deflate",  # Remove br to avoid Brotli issues
        "DNT": "1",
        "Connection": "keep-alive",
    }


async def random_delay():
    delay = random.uniform(SETTINGS.request_delay_min, SETTINGS.request_delay_max)
    await asyncio.sleep(delay)


# ─── Base class ───────────────────────────────────────────────────────────────

class BaseModule(ABC):
    """Classe de base pour tous les modules OSINT."""
    
    name: str = "base"
    description: str = ""
    requires: List[str] = []  # Champs requis dans les données cible
    
    def can_run(self, target_data: dict) -> bool:
        """Vérifie si le module peut s'exécuter avec les données disponibles."""
        return any(target_data.get(req) for req in self.requires)
    
    @abstractmethod
    async def run(self, target_data: dict, session: aiohttp.ClientSession,
                  progress_cb=None) -> List[OsintResult]:
        """
        Lance le module OSINT.
        progress_cb: callable(message: str, percent: float)
        """
        ...
    
    async def safe_get(self, session: aiohttp.ClientSession, url: str,
                       headers: dict = None, timeout: int = None) -> Optional[aiohttp.ClientResponse]:
        """GET avec gestion d'erreurs et retry."""
        _timeout = timeout or SETTINGS.request_timeout
        _headers = headers or random_headers()
        
        try:
            async with session.get(
                url,
                headers=_headers,
                timeout=aiohttp.ClientTimeout(total=_timeout),
                allow_redirects=True,
                ssl=False
            ) as resp:
                # Read body to close properly
                await resp.read()
                return resp
        except Exception:
            return None
    
    async def safe_get_json(self, session: aiohttp.ClientSession, url: str,
                            headers: dict = None) -> Optional[dict]:
        """GET JSON avec gestion d'erreurs."""
        _headers = headers or random_headers()
        _headers["Accept"] = "application/json"
        
        try:
            async with session.get(
                url,
                headers=_headers,
                timeout=aiohttp.ClientTimeout(total=SETTINGS.request_timeout),
                ssl=False
            ) as resp:
                if resp.status == 200:
                    return await resp.json(content_type=None)
        except Exception:
            pass
        return None
    
    async def safe_get_text(self, session: aiohttp.ClientSession, url: str,
                            headers: dict = None) -> Optional[str]:
        """GET text content."""
        _headers = headers or random_headers()
        try:
            async with session.get(
                url,
                headers=_headers,
                timeout=aiohttp.ClientTimeout(total=SETTINGS.request_timeout),
                ssl=False
            ) as resp:
                if resp.status == 200:
                    return await resp.text(errors="ignore")
        except Exception:
            pass
        return None