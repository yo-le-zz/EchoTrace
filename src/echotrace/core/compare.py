"""Comparaison de deux analyses de la même cible."""

from __future__ import annotations

from dataclasses import dataclass, field

# Écart de confiance à partir duquel un résultat est considéré comme ayant changé.
CONFIDENCE_DELTA = 0.1


@dataclass
class Diff:
    appeared: list[dict] = field(default_factory=list)
    disappeared: list[dict] = field(default_factory=list)
    changed: list[tuple[dict, dict]] = field(default_factory=list)  # (ancien, nouveau)
    unchanged: int = 0

    @property
    def has_changes(self) -> bool:
        return bool(self.appeared or self.disappeared or self.changed)


def _key(result: dict) -> tuple[str, str]:
    # Les lignes sans URL (empreintes d'image, validation du numéro...) se distinguent par leur titre.
    return result["module"] + "|" + result["platform"], result["url"] or result["title"]


def diff_results(old: list[dict], new: list[dict]) -> Diff:
    """Résultats apparus, disparus ou dont la confiance a sensiblement changé."""
    old_by_key = {_key(r): r for r in old}
    new_by_key = {_key(r): r for r in new}
    diff = Diff()
    for key, result in new_by_key.items():
        before = old_by_key.get(key)
        if before is None:
            diff.appeared.append(result)
        elif abs(result["confidence"] - before["confidence"]) >= CONFIDENCE_DELTA:
            diff.changed.append((before, result))
        else:
            diff.unchanged += 1
    diff.disappeared = [r for key, r in old_by_key.items() if key not in new_by_key]
    return diff


def format_diff(diff: Diff) -> str:
    """Résumé texte d'une comparaison, lisible en terminal comme dans une boîte de dialogue."""
    lines = [f"{len(diff.appeared)} nouveau(x), {len(diff.disappeared)} disparu(s), "
             f"{len(diff.changed)} modifié(s), {diff.unchanged} inchangé(s)."]
    for result in diff.appeared:
        lines.append(f"+ {result['platform']} : {result['url'] or result['title']} ({result['confidence']:.2f})")
    for result in diff.disappeared:
        lines.append(f"- {result['platform']} : {result['url'] or result['title']}")
    for before, after in diff.changed:
        lines.append(f"~ {after['platform']} : {after['url'] or after['title']} "
                     f"({before['confidence']:.2f} → {after['confidence']:.2f})")
    return "\n".join(lines)
