import pytest

from echotrace.core.identity import split_photos, split_pseudos, target_key
from echotrace.modules.variants import (
    Pattern,
    extract_handles,
    generate_variants,
    parse_pattern,
    separator_variants,
    split_syllables,
    wildcard_candidates,
)


def test_split_syllables():
    assert split_syllables("yolezz") == ["yo", "le", "zz"]
    assert split_syllables("yo_le_zz") == ["yo", "le", "zz"]
    assert split_syllables("alex123") == ["a", "le", "x", "123"]
    assert split_syllables("") == []


def test_separator_variants_cover_the_documented_examples():
    variants = separator_variants("yolezz")
    for expected in ("yo_le_zz", "yo-le-zz", "yo.le.zz", "yolezz", "yo_lezz", "yole.zz"):
        assert expected in variants
    assert separator_variants("zz") == []  # une seule unité : rien à recomposer


def test_generate_variants_start_with_original_and_stay_valid():
    variants = generate_variants("yolezz", limit=12)
    assert variants[0] == "yolezz"
    assert {"yo_le_zz", "yo-le-zz", "yo.le.zz"} <= set(variants)
    assert len(variants) == len(set(variants)) <= 12
    assert all(" " not in v and "@" not in v for v in variants)


def test_variants_from_a_separated_pseudo_find_the_compact_form():
    assert "yolezz" in generate_variants("yo_le_zz", limit=10)


def test_original_kept_even_if_unusual():
    assert generate_variants("john doe")[0] == "john doe"
    assert generate_variants("   ") == []


@pytest.mark.parametrize(
    ("raw", "expected"),
    [
        ("yolezz", Pattern("yolezz")),
        ("yolezz.", Pattern("yolezz", True, ".")),
        ("yolezz.*", Pattern("yolezz", True, ".")),
        ("yolezz.{}", Pattern("yolezz", True, ".")),
        ("yolezz_*", Pattern("yolezz", True, "_")),
        ("yolezz*", Pattern("yolezz", True, "")),
        ("alice_", Pattern("alice_")),  # un « _ » final seul reste un pseudo ordinaire
        (".", Pattern(".")),
    ],
)
def test_parse_pattern(raw, expected):
    assert parse_pattern(raw) == expected


def test_wildcard_candidates_mix_wordlist_and_discovered_handles():
    pattern = Pattern("yolezz", True, ".")
    names = wildcard_candidates(pattern, {"yolezz.testrandom"}, limit=100)
    assert names[0] == "yolezz"
    assert "yolezz.secret" in names and "yolezz.official" in names
    assert "yolezz.testrandom" in names
    assert len(wildcard_candidates(pattern, limit=5)) == 5


def test_extract_handles_requires_word_start_and_ignores_the_bare_base():
    pattern = Pattern("yolezz", True, ".")
    text = "Voir yolezz.secret et YOLEZZ.Dev, pas xyolezz.nope ni yolezz. seul. Écrire à yolezz.contact@x.org"
    handles = extract_handles(text, pattern)
    assert {"yolezz.secret", "yolezz.Dev", "yolezz.contact"} <= handles
    assert not any("nope" in h for h in handles)
    assert "yolezz" not in handles


def test_split_helpers_and_target_key():
    assert split_photos("a.png; b.png\n a.png") == ["a.png", "b.png"]
    assert split_photos(None) == []
    assert split_pseudos("alice ; bob\nalice") == ["alice", "bob"]
    assert target_key({"pseudo": "Alice;Bob"}) == target_key({"pseudo": "bob ; alice"})
    assert target_key({"pseudo": "alice"}) != target_key({"pseudo": "bob"})
    assert target_key({"ville": "Paris"}) == ""  # la ville seule n'identifie personne
