"""Module image : empreintes, détection de visages (comptage) et pistes de recherche inversée.

Ce module ne reconnaît ni n'identifie personne : il calcule des empreintes, compte
les visages détectés et prépare des liens vers les moteurs de recherche d'images,
à ouvrir manuellement. Les liens ne sont générés que si la photo est une URL publique.
Plusieurs photos peuvent être fournies (une par ligne ou séparées par `;`).
"""

from __future__ import annotations

import asyncio
import hashlib
import io
import logging
from pathlib import Path
from urllib.parse import quote, urlparse

import aiohttp
from PIL import Image

from echotrace.core.identity import split_photos
from echotrace.modules.base import BaseModule, OsintResult, ProgressCallback
from echotrace.network import host_semaphore

log = logging.getLogger(__name__)

try:  # dépendance optionnelle : pip install "echotrace[image]"
    import cv2
    import numpy as np
except ImportError:
    cv2 = None
    np = None

MAX_IMAGE_BYTES = 20 * 1024 * 1024
# Deux empreintes à 6 bits d'écart ou moins (sur 64) sont la même image, recadrée ou recompressée.
SAME_IMAGE_DISTANCE = 6

REVERSE_SEARCH_ENGINES = {
    "Google Lens": "https://lens.google.com/uploadbyurl?url={}",
    "Yandex Images": "https://yandex.com/images/search?rpt=imageview&url={}",
    "Bing Visual Search": "https://www.bing.com/images/search?view=detailv2&iss=sbi&q=imgurl:{}",
}


def is_remote(source: str) -> bool:
    return urlparse(source).scheme in ("http", "https")


def average_hash(image: Image.Image) -> str:
    """Empreinte perceptuelle 64 bits (hexadécimal) : deux images proches ont des empreintes proches."""
    pixels = image.convert("L").resize((8, 8), Image.Resampling.LANCZOS).tobytes()
    mean = sum(pixels) / len(pixels)
    bits = "".join("1" if value > mean else "0" for value in pixels)
    return f"{int(bits, 2):016x}"


def hash_distance(first: str, second: str) -> int:
    """Nombre de bits différents entre deux empreintes hexadécimales."""
    return bin(int(first, 16) ^ int(second, 16)).count("1")


def image_hash(data: bytes) -> str | None:
    """Empreinte d'une image ; None si les octets ne sont pas une image lisible."""
    try:
        with Image.open(io.BytesIO(data)) as image:
            return average_hash(image)
    except (OSError, ValueError, Image.DecompressionBombError):
        return None


def image_similarity(first: bytes, second: bytes) -> float:
    """Similarité (0.0 → 1.0) entre deux images, d'après la distance de leurs empreintes."""
    hash_a, hash_b = image_hash(first), image_hash(second)
    if hash_a is None or hash_b is None:
        return 0.0
    return 1 - hash_distance(hash_a, hash_b) / 64


def describe_image(data: bytes) -> dict:
    """Dimensions, format et empreintes d'une image ; lève OSError si elle est illisible."""
    with Image.open(io.BytesIO(data)) as image:
        return {
            "width": image.width,
            "height": image.height,
            "format": image.format or "inconnu",
            "md5": hashlib.md5(data, usedforsecurity=False).hexdigest(),
            "perceptual_hash": average_hash(image),
        }


def count_faces(data: bytes) -> int | None:
    """Nombre de visages détectés, ou None si OpenCV n'est pas installé."""
    if cv2 is None:
        return None
    frame = cv2.imdecode(np.frombuffer(data, np.uint8), cv2.IMREAD_GRAYSCALE)
    if frame is None:
        return 0
    cascade = cv2.CascadeClassifier(cv2.data.haarcascades + "haarcascade_frontalface_default.xml")
    return len(cascade.detectMultiScale(frame, scaleFactor=1.1, minNeighbors=5))


async def load_image(session: aiohttp.ClientSession, source: str) -> bytes | None:
    """Charge une image depuis une URL ou un fichier local, avec plafond de taille."""
    try:
        if is_remote(source):
            async with host_semaphore(session, source), session.get(source) as resp:
                if resp.status != 200:
                    log.warning("Image inaccessible (%s) : HTTP %s", source, resp.status)
                    return None
                return await resp.content.read(MAX_IMAGE_BYTES)

        path = Path(source).expanduser()
        if path.stat().st_size > MAX_IMAGE_BYTES:
            log.warning("Image trop volumineuse : %s", path)
            return None
        return await asyncio.to_thread(path.read_bytes)
    except (OSError, aiohttp.ClientError, asyncio.TimeoutError, ValueError) as exc:
        log.warning("Chargement de l'image impossible (%s) : %s", source, exc)
        return None


class ImageModule(BaseModule):
    name = "image"
    description = "Analyse d'images : empreintes, visages détectés, pistes de recherche inversée"
    requires = ["photo"]

    async def run(
        self,
        target_data: dict,
        session: aiohttp.ClientSession,
        progress_cb: ProgressCallback | None = None,
    ) -> list[OsintResult]:
        sources = split_photos(target_data.get("photo"))
        results: list[OsintResult] = []
        hashes: dict[str, str] = {}
        for index, source in enumerate(sources):
            if progress_cb:
                progress_cb(f"Analyse de l'image {index + 1}/{len(sources)}", index / len(sources) * 100)
            data = await load_image(session, source)
            if data is None:
                continue
            try:
                info = await asyncio.to_thread(describe_image, data)
            except (OSError, ValueError, Image.DecompressionBombError) as exc:
                log.warning("Image illisible (%s) : %s", source, exc)
                continue
            faces = await asyncio.to_thread(count_faces, data)
            if faces is not None:
                info["faces_detected"] = faces
            hashes[source] = info["perceptual_hash"]
            results += self._results_for(source, info, faces)

        results += self._duplicates(hashes)
        return results

    def _results_for(self, source: str, info: dict, faces: int | None) -> list[OsintResult]:
        title = f"Image {info['width']}x{info['height']} ({info['format']})"
        if faces is not None:
            title += f", {faces} visage(s) détecté(s)"
        # Fait relatif à la donnée fournie, pas à une correspondance : confiance nulle.
        results = [
            OsintResult(
                module=self.name,
                platform="Image Analysis",
                url=source if is_remote(source) else "",
                title=title,
                confidence=0.0,
                data={"kind": "info", "source": source, **info},
            )
        ]
        if is_remote(source):
            encoded = quote(source, safe="")
            results += [
                OsintResult(
                    module=self.name,
                    platform=engine,
                    url=template.format(encoded),
                    title=f"Recherche inversée sur {engine} (à ouvrir manuellement)",
                    confidence=0.0,
                    data={"kind": "manual_lead", "image_url": source},
                )
                for engine, template in REVERSE_SEARCH_ENGINES.items()
            ]
        return results

    def _duplicates(self, hashes: dict[str, str]) -> list[OsintResult]:
        """Signale les photos fournies qui sont en fait la même image."""
        results = []
        sources = list(hashes)
        for i, first in enumerate(sources):
            for second in sources[i + 1:]:
                distance = hash_distance(hashes[first], hashes[second])
                if distance <= SAME_IMAGE_DISTANCE:
                    results.append(OsintResult(
                        module=self.name, platform="Image Analysis", url="",
                        title="Deux des photos fournies sont la même image",
                        confidence=0.0,
                        data={"kind": "duplicate", "first": first, "second": second, "distance": distance},
                    ))
        return results
