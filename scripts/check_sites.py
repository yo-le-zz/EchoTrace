"""Vérifie que chaque site du catalogue se comporte comme prévu (nécessite internet).

    uv run python scripts/check_sites.py            # tous les sites
    uv run python scripts/check_sites.py GitHub Reddit

Deux contrôles par site :
  - ABSENT : un pseudo aléatoire ne doit PAS être « trouvé » (sinon le site produit des faux positifs) ;
  - PRÉSENT : le compte réel `known_user` du catalogue doit être trouvé (si le site en déclare un).

Code de sortie 1 si un site échoue : lancez-le de temps en temps, les sites changent leurs pages.
"""

from __future__ import annotations

import asyncio
import secrets
import sys

from echotrace.modules.base import fetch
from echotrace.modules.sites import Site, load_sites
from echotrace.modules.username_module import is_found
from echotrace.network import create_session


async def probe(session, site: Site, username: str) -> bool | None:
    """True/False selon la détection, None si le site ne répond pas."""
    url = site.url.format(username)
    response = await fetch(session, url, read_body=site.check != "status_200", timeout=12)
    if response is None:
        return None
    return is_found(site, url, response.status, response.url, response.text)


async def check(session, semaphore: asyncio.Semaphore, site: Site) -> tuple[Site, str, str]:
    async with semaphore:
        absent = await probe(session, site, "zq" + secrets.token_hex(7))
        present = await probe(session, site, site.known_user) if site.known_user else None
    problems = []
    if absent is None:
        problems.append("injoignable")
    elif absent:
        problems.append("FAUX POSITIF (un pseudo aléatoire est « trouvé »)")
    if site.known_user and present is False:
        problems.append(f"compte connu « {site.known_user} » non détecté")
    detail = "; ".join(problems) if problems else ("ok" if site.known_user else "ok (absent seulement)")
    return site, "ECHEC" if problems else "ok", detail


async def main(names: list[str]) -> int:
    sites = [s for s in load_sites() if not names or s.name.lower() in {n.lower() for n in names}]
    if not sites:
        print("Aucun site correspondant.")
        return 1
    semaphore = asyncio.Semaphore(8)
    async with create_session() as session:
        rows = await asyncio.gather(*(check(session, semaphore, s) for s in sites))
    failures = 0
    for site, state, detail in sorted(rows, key=lambda r: (r[1] == "ok", r[0].name.lower())):
        failures += state != "ok"
        print(f"{state:<6} {site.name:<16} [{site.reliability:<6}] {detail}")
    print(f"\n{len(rows) - failures}/{len(rows)} sites conformes.")
    return 1 if failures else 0


if __name__ == "__main__":
    sys.exit(asyncio.run(main(sys.argv[1:])))
