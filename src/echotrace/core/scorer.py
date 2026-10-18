"""Système de scoring : validité des entrées et confiance des résultats."""

from __future__ import annotations

from echotrace.config.fields import FIELD_SCORES
from echotrace.config.settings import get_settings

# Poids de chaque vérification dans la confiance d'un résultat.
CHECK_WEIGHTS: dict[str, float] = {
    "username_exact": 0.35,
    "username_similar": 0.15,
    "email_match": 0.40,
    "avatar_match": 0.30,
    "bio_match": 0.15,
    "location_match": 0.10,
    "http_200": 0.20,
    "profile_exists": 0.25,
    "cross_link": 0.35,
}


def compute_input_score(data: dict) -> int:
    """Somme des points des champs renseignés."""
    return sum(FIELD_SCORES[name] for name, value in data.items() if value and name in FIELD_SCORES)


def is_input_valid(data: dict) -> tuple[bool, int, str]:
    """Indique si les données suffisent à lancer une analyse : (valide, score, message)."""
    score = compute_input_score(data)
    minimum = get_settings().min_score_required
    filled = [name for name, value in data.items() if value and name in FIELD_SCORES]

    if len(filled) < 2:
        return False, score, "Minimum 2 informations requises."
    if score < minimum:
        return False, score, f"Score insuffisant: {score}/{minimum} points."
    return True, score, f"Score valide: {score} points ✓"


def confidence_label(confidence: float) -> tuple[str, str]:
    """Retourne (libellé, couleur hexadécimale) selon le niveau de confiance."""
    if confidence >= 0.85:
        return "HAUTE CONFIANCE", "#a6da95"
    if confidence >= 0.65:
        return "CONFIANCE MOYENNE", "#eed49f"
    if confidence >= 0.40:
        return "FAIBLE CONFIANCE", "#f5a97f"
    return "INCERTAIN", "#ed8796"


def compute_result_confidence(module: str, checks: dict) -> float:
    """Confiance d'un résultat (0.0 → 1.0) à partir des vérifications effectuées.

    `checks` associe un nom de vérification à un booléen ; les noms absents de
    CHECK_WEIGHTS sont ignorés. Le paramètre `module` est conservé pour permettre
    des barèmes par module.
    """
    total_weight = 0.0
    score = 0.0
    for check, present in checks.items():
        weight = CHECK_WEIGHTS.get(check)
        if weight is None:
            continue
        total_weight += weight
        if present:
            score += weight
    if total_weight == 0:
        return 0.0
    return min(score / total_weight, 1.0)


def score_username_similarity(a: str, b: str) -> float:
    """Similarité simple entre deux pseudos (0.0 → 1.0)."""
    if not a or not b:
        return 0.0
    a, b = a.lower().strip(), b.lower().strip()
    if a == b:
        return 1.0

    if a in b or b in a:
        return min(len(a), len(b)) / max(len(a), len(b)) * 0.9

    common = 0
    for char_a, char_b in zip(a, b, strict=False):
        if char_a != char_b:
            break
        common += 1
    if common >= 4:
        return common / max(len(a), len(b)) * 0.75
    return 0.0
