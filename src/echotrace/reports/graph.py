"""Graphe de corrélation pseudo ↔ plateforme, rendu en SVG sans dépendance."""

from __future__ import annotations

import math
from html import escape

SIZE = 720
CENTER = SIZE / 2


def _positions(names: list[str], radius: float, offset: float = 0.0) -> dict[str, tuple[float, float]]:
    """Répartit les noms régulièrement sur un cercle ; un nom seul reste au centre."""
    if len(names) == 1:
        return {names[0]: (CENTER, CENTER)}
    step = 2 * math.pi / max(len(names), 1)
    return {
        name: (CENTER + radius * math.cos(offset + i * step),
               CENTER + radius * math.sin(offset + i * step))
        for i, name in enumerate(names)
    }


def build_graph_svg(results: list[dict]) -> str:
    """SVG des liens pseudo ↔ plateforme, ou chaîne vide s'il n'y a rien à relier.

    Les textes proviennent de pages web : tout passe par `escape`.
    """
    edges: dict[tuple[str, str], float] = {}
    for result in results:
        username, platform = result.get("username", ""), result.get("platform", "")
        if username and platform:
            key = (username, platform)
            edges[key] = max(edges.get(key, 0.0), float(result.get("confidence", 0.0)))
    if not edges:
        return ""

    usernames = sorted({u for u, _ in edges})
    platforms = sorted({p for _, p in edges})
    user_pos = _positions(usernames, SIZE * 0.14)
    platform_pos = _positions(platforms, SIZE * 0.4, offset=-math.pi / 2)

    parts = [
        f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 {SIZE} {SIZE}" '
        f'role="img" aria-label="Graphe de corrélation" style="max-width:100%;height:auto">'
    ]
    for (username, platform), confidence in edges.items():
        (x1, y1), (x2, y2) = user_pos[username], platform_pos[platform]
        parts.append(
            f'<line x1="{x1:.1f}" y1="{y1:.1f}" x2="{x2:.1f}" y2="{y2:.1f}" stroke="#8aadf4" '
            f'stroke-opacity="{0.2 + 0.8 * confidence:.2f}" stroke-width="{1 + 2 * confidence:.1f}"/>'
        )
    for name, (x, y) in platform_pos.items():
        parts.append(
            f'<g><title>{escape(name)}</title><circle cx="{x:.1f}" cy="{y:.1f}" r="9" fill="#007bff"/>'
            f'<text x="{x:.1f}" y="{y + 22:.1f}" font-size="11" text-anchor="middle" '
            f'fill="currentColor">{escape(name)}</text></g>'
        )
    for name, (x, y) in user_pos.items():
        parts.append(
            f'<g><title>{escape(name)}</title><circle cx="{x:.1f}" cy="{y:.1f}" r="12" fill="#28a745"/>'
            f'<text x="{x:.1f}" y="{y - 16:.1f}" font-size="12" font-weight="bold" '
            f'text-anchor="middle" fill="currentColor">{escape(name)}</text></g>'
        )
    parts.append("</svg>")
    return "".join(parts)
