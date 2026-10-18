"""Variantes d'un pseudo : séparateurs, syllabes, suffixes, et mode joker (`yolezz.`).

Fonctions pures, sans réseau, pour rester faciles à tester.
"""

from __future__ import annotations

import re
from dataclasses import dataclass

SEPARATORS = ("_", "-", ".")

# Seuls ces caractères ont un sens dans un nom d'utilisateur d'URL.
VALID_USERNAME = re.compile(r"^[A-Za-z0-9._-]{1,64}$")

_LEET = {"a": "4", "e": "3", "i": "1", "o": "0", "s": "5", "t": "7", "l": "1", "z": "2"}
_PREFIXES = ("_", "x", "xx", "the", "real")
_SUFFIXES = ("_", "x", "xx", "official", "real")

# Suffixes courants testés en mode joker (`yolezz.` → yolezz.official, yolezz.dev...).
WILDCARD_WORDS = (
    "official", "real", "off", "dev", "tv", "fr", "pro", "main", "alt", "backup", "private",
    "secret", "art", "music", "games", "game", "live", "yt", "ig", "me", "app", "bot",
    "2", "01", "1", "x",
)

# Les voyelles servent à découper en syllabes ; « y » compte comme voyelle (« yo »).
_VOWELS = "aeiouyàâäéèêëîïôöùûüœ"
_SYLLABLE = re.compile(rf"[^{_VOWELS}]*[{_VOWELS}]+|[^{_VOWELS}]+", re.IGNORECASE)
_WILDCARD = re.compile(r"^(?P<base>.*?)(?P<sep>[._-]?)(?:\*|\{\})?$")


@dataclass(frozen=True)
class Pattern:
    """Pseudo saisi : texte de base et, en mode joker, le séparateur attendu avant le suffixe."""

    base: str
    wildcard: bool = False
    separator: str = ""


def parse_pattern(raw: str) -> Pattern:
    """Reconnaît le mode joker : `yolezz.`, `yolezz.*`, `yolezz.{}`, `yolezz_*`, `yolezz*`.

    Un `_` ou `-` final seul reste un pseudo ordinaire (`alice_` existe vraiment) ;
    il faut `*` ou `{}` pour demander un joker avec ces séparateurs.
    """
    raw = raw.strip()
    marked = raw.endswith(("*", "{}", "."))
    match = _WILDCARD.match(raw)
    if not marked or match is None or not match.group("base"):
        return Pattern(raw)
    return Pattern(match.group("base"), True, match.group("sep"))


def split_syllables(name: str) -> list[str]:
    """Découpe un pseudo en unités : séparateurs existants, chiffres, puis syllabes.

    `yolezz` → ['yo', 'le', 'zz'] ; `john_doe` → ['jo', 'hn', 'do', 'e'] (heuristique,
    il n'y a pas de vrai dictionnaire de syllabes pour des pseudos).
    """
    units: list[str] = []
    for part in re.split(r"[._\-\s]+", name):
        for group in re.findall(r"\d+|[^\W\d_]+", part):
            units.extend([group] if group.isdigit() else _SYLLABLE.findall(group))
    return units


def separator_variants(name: str) -> list[str]:
    """Recompositions d'un pseudo avec `_`, `-`, `.` ou rien, entre syllabes ou en deux blocs."""
    units = split_syllables(name)
    if len(units) < 2:
        return []
    variants: list[str] = []
    for sep in (*SEPARATORS, ""):
        variants.append(sep.join(units))
    if len(units) >= 3:  # deux blocs : yo_lezz, yole_zz...
        for cut in range(1, len(units)):
            left, right = "".join(units[:cut]), "".join(units[cut:])
            variants.extend(f"{left}{sep}{right}" for sep in SEPARATORS)
    return variants


def generate_variants(username: str, limit: int = 10) -> list[str]:
    """Variantes plausibles d'un pseudo, l'original toujours en premier.

    Ordre : séparateurs et syllabes, casse, préfixes et suffixes, puis substitutions
    de type « leet ». Seules les variantes valides dans une URL sont gardées.
    """
    username = username.strip()
    if not username:
        return []
    candidates: list[str] = [username]

    # 1. Séparateurs, syllabes et casse : les variantes les plus probables
    if any(sep in username for sep in SEPARATORS):
        compact = re.sub(r"[._\-]", "", username)
        for sep in SEPARATORS:
            candidates.append(re.sub(r"[._\-]", sep, username))
        candidates.append(compact)
        candidates += separator_variants(compact)
    else:
        candidates += separator_variants(username)
    candidates.append(username.lower())

    # 2. Préfixes et suffixes courants
    candidates += [p + username for p in _PREFIXES if not username.startswith(p)]
    candidates += [username + s for s in _SUFFIXES if not username.endswith(s)]

    # 3. Substitutions leet, un caractère à la fois pour éviter l'explosion combinatoire
    lowered = username.lower()
    candidates += [lowered.replace(char, digit) for char, digit in _LEET.items() if char in lowered]

    unique: list[str] = []
    for candidate in candidates:
        # L'original est toujours testé tel que saisi, même s'il sort du format habituel.
        if candidate not in unique and (candidate == username or VALID_USERNAME.match(candidate)):
            unique.append(candidate)
    return unique[: max(limit, 1)]


def wildcard_candidates(pattern: Pattern, discovered: set[str] | None = None, limit: int = 40) -> list[str]:
    """Pseudos à tester en mode joker : suffixes courants puis pseudos découverts en ligne."""
    names = [pattern.base]
    names += [f"{pattern.base}{pattern.separator}{word}" for word in WILDCARD_WORDS]
    names += sorted(discovered or ())
    unique = [n for n in dict.fromkeys(names) if VALID_USERNAME.match(n)]
    return unique[: max(limit, 1)]


def extract_handles(text: str, pattern: Pattern) -> set[str]:
    """Pseudos de la forme `base<sep>mot` repérés dans un texte (titres, extraits, URL).

    Le préfixe doit commencer un mot : `xyolezz.dev` ne correspond pas à `yolezz.`.
    """
    prefix = re.escape(pattern.base + pattern.separator)
    regex = re.compile(rf"(?<![\w.\-]){prefix}([A-Za-z0-9][A-Za-z0-9_\-]{{0,29}})", re.IGNORECASE)
    found = set()
    for match in regex.finditer(text):
        handle = (pattern.base + pattern.separator + match.group(1)).strip("._-")
        if VALID_USERNAME.match(handle) and handle.lower() != pattern.base.lower():
            found.add(handle)
    return found
