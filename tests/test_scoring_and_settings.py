import pytest

from echotrace.config.settings import MASK, Settings, get_settings
from echotrace.core.scorer import (
    compute_input_score,
    compute_result_confidence,
    confidence_label,
    is_input_valid,
    score_username_similarity,
)


def test_input_score_sums_filled_known_fields():
    assert compute_input_score({"email": "a@b.fr", "pseudo": "x", "inconnu": "y", "nom": ""}) == 140


def test_input_validation_requires_two_fields_and_minimum_score():
    assert not is_input_valid({"email": "a@b.fr"})[0]
    assert not is_input_valid({"ville": "Paris", "pays": "France"})[0]
    assert is_input_valid({"email": "a@b.fr", "pseudo": "x"})[0]


def test_minimum_score_follows_settings():
    get_settings().min_score_required = 10
    assert is_input_valid({"ville": "Paris", "pays": "France"})[0]


def test_result_confidence():
    assert compute_result_confidence("m", {"http_200": True, "profile_exists": True}) == 1.0
    assert compute_result_confidence("m", {"unknown": True}) == 0.0
    assert 0 < compute_result_confidence("m", {"http_200": True, "cross_link": False}) < 1


@pytest.mark.parametrize(("value", "label"), [(0.9, "HAUTE CONFIANCE"), (0.7, "CONFIANCE MOYENNE"),
                                              (0.5, "FAIBLE CONFIANCE"), (0.1, "INCERTAIN")])
def test_confidence_label(value, label):
    assert confidence_label(value)[0] == label


def test_username_similarity():
    assert score_username_similarity("Alice", "alice") == 1.0
    assert score_username_similarity("alice", "alice_dev") > 0.4
    assert score_username_similarity("alice", "bob") == 0.0


def test_settings_roundtrip(isolated_home):
    settings = Settings(hibp_api_key="secret", request_timeout=7)
    settings.save()
    loaded = Settings.load()
    assert loaded.hibp_api_key == "secret"
    assert loaded.request_timeout == 7


def test_settings_corrupt_file_falls_back_to_defaults(isolated_home):
    from echotrace import paths

    paths.config_file().write_text("{ pas du json", encoding="utf-8")
    assert Settings.load() == Settings()


def test_settings_export_masks_secrets_and_import_drops_them(tmp_path):
    target = tmp_path / "export.json"
    Settings(github_token="s3cret-token", hibp_api_key="s3cret-key").export_to_file(target)
    content = target.read_text(encoding="utf-8")
    assert MASK in content
    assert "s3cret" not in content
    imported = Settings.import_from_file(target)
    assert imported.github_token == "" and imported.hibp_api_key == ""


def test_settings_validation():
    with pytest.raises(ValueError):
        Settings(request_delay_min=2, request_delay_max=1).validate()
    with pytest.raises(ValueError):
        Settings(confidence_threshold=1.5).validate()
    Settings().validate()
