import io

import pytest
from PIL import Image

from echotrace.modules.google_module import generate_queries
from echotrace.modules.image_module import (
    average_hash,
    describe_image,
    hash_distance,
    image_hash,
    image_similarity,
)
from echotrace.modules.phone_module import analyze_phone_format, normalize_phone
from echotrace.modules.search import clean_url, parse_hits


def _png(color, size=(32, 32)) -> bytes:
    buffer = io.BytesIO()
    Image.new("RGB", size, color).save(buffer, "PNG")
    return buffer.getvalue()


@pytest.mark.parametrize(
    ("raw", "expected"),
    [("06 12 34 56 78", "+33612345678"), ("612345678", "+33612345678"),
     ("0033612345678", "+33612345678"), ("+44 20 7946 0958", "+442079460958"),
     ("123", ""), ("", "")],
)
def test_normalize_phone(raw, expected):
    assert normalize_phone(raw) == expected


def test_analyze_phone_format():
    assert analyze_phone_format("+33612345678")["type"] == "Mobile"
    assert analyze_phone_format("+33112345678")["type"] == "Fixe"
    assert analyze_phone_format("+33612345678")["country"] == "France"


def test_clean_url_rejects_dangerous_schemes():
    assert clean_url("javascript:alert(1)") == ""
    assert clean_url("/url?q=https://example.org/page&sa=U") == "https://example.org/page"
    assert clean_url("//duckduckgo.com/l/?uddg=https%3A%2F%2Fexample.org%2Fx") == "https://example.org/x"
    assert clean_url("https://example.org") == "https://example.org"


def test_parse_hits_skips_unsafe_links():
    html = (
        '<div class="g"><a href="https://example.org/a"><h3>Titre A</h3></a> extrait</div>'
        '<div class="g"><a href="javascript:void(0)">Mauvais</a></div>'
    )
    hits = parse_hits(html, "div.g")
    assert [h.url for h in hits] == ["https://example.org/a"]
    assert hits[0].title == "Titre A"


def test_generate_queries_deduplicated_and_empty_when_no_data():
    assert generate_queries({}) == []
    queries = generate_queries({"pseudo": "alice", "email": "a@b.fr"})
    assert len(queries) == len(set(queries))
    assert '"alice"' in queries and '"a@b.fr"' in queries


def test_generate_queries_handles_several_pseudos_and_wildcards():
    queries = generate_queries({"pseudo": "alice ; bob."})
    assert '"alice"' in queries and '"bob"' in queries  # le point final du joker est retiré


def test_image_hash_and_similarity():
    black = _png((0, 0, 0))
    assert image_similarity(black, black) == 1.0
    with Image.open(io.BytesIO(black)) as image:
        assert len(average_hash(image)) == 16
    assert image_similarity(b"pas une image", black) == 0.0
    assert image_hash(b"pas une image") is None
    assert hash_distance("0000000000000000", "ffffffffffffffff") == 64


def test_describe_image():
    info = describe_image(_png((10, 20, 30), (40, 20)))
    assert (info["width"], info["height"], info["format"]) == (40, 20, "PNG")
    assert len(info["md5"]) == 32
