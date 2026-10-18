"""
EchoTrace — Scoring System
"""

from config.settings import FIELD_SCORES, SETTINGS


def compute_input_score(data: dict) -> int:
    """Calcule le score des données d'entrée."""
    score = 0
    for field, value in data.items():
        if value and field in FIELD_SCORES:
            score += FIELD_SCORES[field]
    return score


def is_input_valid(data: dict) -> tuple[bool, int, str]:
    """
    Vérifie si l'input est suffisant pour lancer une analyse.
    Retourne (valide, score, message)
    """
    score = compute_input_score(data)
    min_req = SETTINGS.min_score_required

    filled = [f for f, v in data.items() if v and f in FIELD_SCORES]
    
    if len(filled) < 2:
        return False, score, "Minimum 2 informations requises."
    
    if score < min_req:
        return False, score, f"Score insuffisant: {score}/{min_req} points."
    
    return True, score, f"Score valide: {score} points ✓"


def confidence_label(confidence: float) -> tuple[str, str]:
    """Retourne (label, couleur_hex) selon le niveau de confiance."""
    if confidence >= 0.85:
        return "HAUTE CONFIANCE", "#a6da95"   # vert
    elif confidence >= 0.65:
        return "CONFIANCE MOYENNE", "#eed49f"  # jaune
    elif confidence >= 0.40:
        return "FAIBLE CONFIANCE", "#f5a97f"   # orange
    else:
        return "INCERTAIN", "#ed8796"           # rouge


def compute_result_confidence(module: str, checks: dict) -> float:
    """
    Calcule la confiance d'un résultat selon les checks effectués.
    checks: dict avec des booléens (username_exact, bio_match, avatar_match, ...)
    """
    weights = {
        "username_exact":   0.35,
        "username_similar": 0.15,
        "email_match":      0.40,
        "avatar_match":     0.30,
        "bio_match":        0.15,
        "location_match":   0.10,
        "http_200":         0.20,
        "profile_exists":   0.25,
        "cross_link":       0.35,
    }
    
    score = 0.0
    total_weight = 0.0
    
    for check, present in checks.items():
        if check in weights:
            total_weight += weights[check]
            if present:
                score += weights[check]
    
    if total_weight == 0:
        return 0.0
    
    return min(score / total_weight, 1.0)


def score_username_similarity(a: str, b: str) -> float:
    """Similarité simple entre deux usernames (0.0 → 1.0)."""
    if not a or not b:
        return 0.0
    a, b = a.lower().strip(), b.lower().strip()
    if a == b:
        return 1.0
    
    # Levenshtein simplifié
    if a in b or b in a:
        shorter = min(len(a), len(b))
        longer = max(len(a), len(b))
        return shorter / longer * 0.9
    
    # Common prefix
    common = 0
    for ca, cb in zip(a, b):
        if ca == cb:
            common += 1
        else:
            break
    
    if common >= 4:
        return common / max(len(a), len(b)) * 0.75
    
    return 0.0