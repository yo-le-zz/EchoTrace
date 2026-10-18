import asyncio
import json
import sqlite3

import pytest

from echotrace import cli, paths
from echotrace.config.settings import PROFILES, Settings, get_settings
from echotrace.core import verify
from echotrace.core.compare import diff_results, format_diff
from echotrace.core.engine import EchoTraceEngine
from echotrace.core.identity import PURPOSES, target_key
from echotrace.database import db
from echotrace.modules import load_plugins
from echotrace.modules.base import BaseModule, OsintResult
from echotrace.modules.image_module import ImageModule
from echotrace.modules.sites import Site, load_sites
from echotrace.modules.username_module import UsernameModule, is_found
from echotrace.network import HttpResponse, host_semaphore

TARGET = {"pseudo": "alice", "email": "alice@example.org"}


# ── Module pseudo : deux passes, mode joker ─────────────────────────────────────────────────


@pytest.fixture
def fake_web(monkeypatch):
    """Deux sites : A (sonde) trouve `found_on_a`, B (non-sonde) trouve tout. Compte les requêtes."""
    calls: list[str] = []
    sites = [Site("A", "https://a.test/{}", probe=True, reliability="high"),
             Site("B", "https://b.test/{}", reliability="medium")]
    found_on_a: set[str] = set()

    async def fake_fetch(session, url, *, headers=None, timeout=None, read_body=True):
        calls.append(url)
        host, name = url.split("//")[1].split("/")
        ok = host == "b.test" or name in found_on_a
        return HttpResponse(200 if ok else 404, "", url)

    monkeypatch.setattr("echotrace.modules.username_module.fetch", fake_fetch)
    monkeypatch.setattr("echotrace.modules.username_module.load_sites", lambda: sites)
    get_settings().cache_enabled = False
    return calls, found_on_a


def test_two_pass_tests_only_living_variants_on_all_sites(fake_web):
    calls, found_on_a = fake_web
    found_on_a.add("yo_le_zz")
    results = asyncio.run(UsernameModule().run({"pseudo": "yolezz"}, None))

    b_calls = [c for c in calls if "b.test" in c]
    assert sorted(b_calls) == ["https://b.test/yo_le_zz", "https://b.test/yolezz"]  # variante vivante + exact
    assert {r.platform for r in results} == {"A", "B"}
    assert next(r for r in results if r.username == "yolezz").confidence > \
        next(r for r in results if r.username == "yo_le_zz" and r.platform == "B").confidence


def test_without_two_pass_every_variant_hits_every_site(fake_web):
    calls, _ = fake_web
    get_settings().two_pass = False
    asyncio.run(UsernameModule().run({"pseudo": "yolezz"}, None))
    assert len([c for c in calls if "b.test" in c]) == len([c for c in calls if "a.test" in c]) > 2


def test_wildcard_mode_tests_discovered_and_common_suffixes(fake_web, monkeypatch):
    calls, found_on_a = fake_web
    found_on_a.update({"yolezz.testrandom", "yolezz.secret"})

    async def fake_discover(session, pattern):
        return {"yolezz.testrandom"}

    monkeypatch.setattr("echotrace.modules.username_module.discover_handles", fake_discover)
    results = asyncio.run(UsernameModule().run({"pseudo": "yolezz."}, None))
    names = {r.username for r in results if r.platform == "A"}
    assert names == {"yolezz.testrandom", "yolezz.secret"}  # la liste de suffixes contient « secret »
    discovered = next(r for r in results if r.username == "yolezz.testrandom")
    assert discovered.data["discovered_online"] is True


def test_several_pseudos_are_all_searched(fake_web):
    calls, _ = fake_web
    asyncio.run(UsernameModule().run({"pseudo": "alice ; bobby"}, None))
    assert any("/alice" in c for c in calls) and any("/bobby" in c for c in calls)


def test_is_found_rules():
    site = Site("S", "https://x.io/{}", check="body_not_contains", marker="introuvable")
    assert not is_found(site, "https://x.io/a", 200, "https://x.io/a", "page introuvable")
    assert is_found(site, "https://x.io/a", 200, "https://x.io/a", "profil")
    plain = Site("S", "https://x.io/{}")
    assert not is_found(plain, "https://x.io/a", 200, "https://x.io/", "")  # redirigé vers l'accueil
    assert not is_found(plain, "https://x.io/a", 404, "https://x.io/a", "")


# ── Catalogue de sites, plugins, limiteur ───────────────────────────────────────────────────


def test_bundled_catalog_is_valid_and_has_probes():
    sites = load_sites()
    assert len(sites) >= 50
    assert 5 <= sum(s.probe for s in sites) < len(sites)
    assert all(s.url.count("{}") == 1 for s in sites)


def test_user_sites_override_and_invalid_entries_are_skipped(isolated_home):
    custom = {"sites": [
        {"name": "GitHub", "url": "https://example.test/{}", "reliability": "low"},  # remplace GitHub
        {"name": "Nouveau", "url": "https://nouveau.test/u/{}"},
        {"name": "Cassé", "url": "pas-une-url"},
        {"name": "SansMarqueur", "url": "https://x.test/{}", "check": "body_contains"},
    ]}
    (paths.config_dir() / "sites.json").write_text(json.dumps(custom), encoding="utf-8")
    by_name = {s.name: s for s in load_sites()}
    assert by_name["GitHub"].url == "https://example.test/{}"
    assert "Nouveau" in by_name and "Cassé" not in by_name and "SansMarqueur" not in by_name


def test_plugins_are_loaded_and_broken_ones_ignored(isolated_home):
    folder = paths.config_dir() / "plugins"
    folder.mkdir()
    (folder / "hello.py").write_text(
        "from echotrace.modules.base import BaseModule\n"
        "class Hello(BaseModule):\n    name='hello'\n    requires=['pseudo']\n"
        "    async def run(self, target_data, session, progress_cb=None):\n        return []\n",
        encoding="utf-8")
    (folder / "broken.py").write_text("raise RuntimeError('boum')\n", encoding="utf-8")
    (folder / "_private.py").write_text("raise RuntimeError('jamais chargé')\n", encoding="utf-8")
    assert [cls.name for cls in load_plugins()] == ["hello"]


def test_host_semaphore_is_shared_per_host_and_session():
    class Session:
        pass

    first, second = Session(), Session()
    a1 = host_semaphore(first, "https://a.test/x")
    assert a1 is host_semaphore(first, "https://a.test/y")
    assert a1 is not host_semaphore(first, "https://b.test/x")
    assert a1 is not host_semaphore(second, "https://a.test/x")


# ── Vérification des profils ──────────────────────────────────────────────────────────────


PROFILE_HTML = """<html><head><title>Fallback</title>
<meta property="og:title" content="Hélène Dupont - Développeuse chez TechCorp">
<meta property="og:description" content="Basée à Lyon. Projets open source.">
<meta property="og:image" content="/img/avatar.png"></head></html>"""


def test_profile_signals_ignore_accents_and_case():
    info = verify.parse_profile_page(PROFILE_HTML, "https://site.test/helene", "helene")
    assert info.image_url == "https://site.test/img/avatar.png"
    target = {"prenom": "helene", "nom": "DUPONT", "entreprise": "TechCorp", "ville": "Lyon"}
    signals = verify.find_signals(info, target)
    assert signals == ["name", "company", "location"]
    assert verify.find_signals(info, {"prenom": "Jean", "nom": "Dupont"}) == []


def test_login_wall_is_detected_and_caps_confidence():
    wall = verify.parse_profile_page("<title>Log in to continue</title>", "https://x.test/u", "alice")
    assert wall.wall
    assert verify.adjust_confidence(0.9, [], wall=True) == verify.WALL_CAP
    # le pseudo visible dans le titre prouve que le profil est lisible
    readable = verify.parse_profile_page("<title>alice (@alice) - Log in</title>", "https://x.test/u", "alice")
    assert not readable.wall


def test_confidence_bonus_is_capped_at_one():
    assert verify.adjust_confidence(0.8, ["avatar", "name", "company"], wall=False) == 1.0
    assert verify.adjust_confidence(0.5, ["location"], wall=False) == 0.55


def test_verify_rows_updates_database_and_detects_reused_avatar(monkeypatch):
    import io

    from PIL import Image

    buffer = io.BytesIO()
    Image.effect_noise((32, 32), 80).save(buffer, "PNG")
    avatar = buffer.getvalue()

    async def fake_fetch(session, url, *, headers=None, timeout=None, read_body=True):
        return HttpResponse(200, PROFILE_HTML, url)

    async def fake_load(session, source):
        return avatar

    monkeypatch.setattr(verify, "fetch", fake_fetch)
    monkeypatch.setattr(verify, "load_image", fake_load)

    target_id = db.save_target({}, 0)
    result = OsintResult("username", "GitHub", "https://github.com/helene", "t", "helene", 0.5)
    db.save_results(target_id, None, [result])
    rows = db.get_results(target_id)
    target = {"prenom": "Hélène", "nom": "Dupont", "photo": "photo.png"}

    assert asyncio.run(verify.verify_rows(None, rows, target)) == 1
    stored = db.get_results(target_id)[0]
    assert stored["confidence"] == 0.95  # 0.5 + nom (0.15) + avatar (0.30)
    assert "même image que l'une de vos photos" in stored["data"]["signals"]


# ── Base de données : statuts, faux positifs, conservation, migration ──────────────────────


def test_false_positive_is_remembered_and_can_be_restored():
    key = target_key(TARGET)
    target_id = db.save_target(TARGET, 140, "alice", "Ma propre empreinte en ligne", key)
    result = OsintResult("username", "GitHub", "https://github.com/alice", "t", "alice", 0.9)
    [rid] = db.save_results(target_id, None, [result])

    db.set_result_review(rid, status="false_positive", note="homonyme")
    assert db.ignored_urls(key) == {"https://github.com/alice"}
    assert db.get_results(target_id)[0]["note"] == "homonyme"
    db.set_result_review(rid, status="confirmed")
    assert db.ignored_urls(key) == set()
    with pytest.raises(ValueError):
        db.set_result_review(rid, status="n'importe quoi")


class OneProfile(BaseModule):
    name = "fake"
    description = "d"
    requires = ["pseudo"]

    async def run(self, target_data, session, progress_cb=None):
        return [OsintResult("fake", "Site", "https://example.org/alice", "t", "alice", 0.9),
                OsintResult("fake", "Site", "https://example.org/other", "t", "alice", 0.9)]


def test_engine_skips_ignored_urls_streams_results_and_reports_diff():
    get_settings().verify_profiles = False
    streamed = []
    engine = EchoTraceEngine([OneProfile()])
    first = asyncio.run(engine.run_analysis(TARGET, result_cb=streamed.extend, purpose=PURPOSES[0]))
    assert first["results_count"] == 2 and len(streamed) == 2 and first["diff"] is None
    assert first["purpose"] == PURPOSES[0]

    bad = next(r for r in first["results"] if r["url"].endswith("/alice"))
    db.set_result_review(bad["id"], status="false_positive")
    second = asyncio.run(engine.run_analysis(TARGET))
    assert [r["url"] for r in second["results"]] == ["https://example.org/other"]
    assert second["previous_target_id"] == first["target_id"]
    assert len(second["diff"].disappeared) == 1 and not second["diff"].appeared


def test_retention_purge_export_and_erase():
    old = db.save_target({"pseudo": "vieux"}, 50, "vieux")
    db.save_target({"pseudo": "recent"}, 50, "recent")
    with db.get_conn() as conn:
        conn.execute("UPDATE targets SET created_at = created_at - 100*86400 WHERE id=?", (old,))
    assert db.purge_older_than(0) == 0  # 0 = conservation illimitée
    assert db.purge_older_than(90) == 1
    assert [t["label"] for t in db.list_targets()] == ["recent"]
    assert db.export_everything()["targets"][0]["label"] == "recent"
    db.erase_everything()
    assert db.list_targets() == [] and db.export_everything() == {"targets": [], "ignored": []}


def test_old_database_is_migrated(isolated_home):
    legacy = sqlite3.connect(paths.database_file())
    legacy.executescript(
        "CREATE TABLE targets (id INTEGER PRIMARY KEY AUTOINCREMENT, created_at REAL NOT NULL, "
        "data TEXT NOT NULL, input_score INTEGER NOT NULL DEFAULT 0, label TEXT NOT NULL DEFAULT '');"
        "CREATE TABLE results (id INTEGER PRIMARY KEY AUTOINCREMENT, target_id INTEGER NOT NULL, "
        "search_id INTEGER, module TEXT NOT NULL, platform TEXT NOT NULL DEFAULT '', url TEXT NOT NULL "
        "DEFAULT '', title TEXT NOT NULL DEFAULT '', username TEXT NOT NULL DEFAULT '', "
        "confidence REAL NOT NULL DEFAULT 0.0, data TEXT NOT NULL DEFAULT '{}', found_at REAL NOT NULL);"
        "INSERT INTO targets (created_at, data, label) VALUES (1, '{}', 'ancien');")
    legacy.commit()
    legacy.close()
    assert db.list_targets()[0]["purpose"] == ""  # colonne ajoutée sans perdre la ligne


# ── Comparaison, profils, images multiples, CLI ──────────────────────────────────────────


def _row(url, confidence, platform="GitHub"):
    return {"module": "username", "platform": platform, "url": url, "title": "", "confidence": confidence}


def test_diff_results():
    old = [_row("u1", 0.9), _row("u2", 0.5), _row("u3", 0.5)]
    new = [_row("u1", 0.9), _row("u2", 0.8), _row("u4", 0.6)]
    diff = diff_results(old, new)
    assert [r["url"] for r in diff.appeared] == ["u4"]
    assert [r["url"] for r in diff.disappeared] == ["u3"]
    assert [(a["url"], b["confidence"]) for a, b in diff.changed] == [("u2", 0.8)]
    assert diff.unchanged == 1 and diff.has_changes
    assert "+ GitHub : u4" in format_diff(diff)
    assert not diff_results(old, old).has_changes


def test_profiles_apply_known_presets_only():
    settings = Settings()
    settings.apply_profile("discret")
    assert settings.profile == "discret" and settings.per_host_limit == 1
    settings.apply_profile("inconnu")
    assert settings.profile == "discret"
    for name in PROFILES:
        Settings().apply_profile(name)
        Settings(**{**Settings().__dict__, **PROFILES[name]}).validate()


def test_image_module_handles_several_photos_and_duplicates(tmp_path):
    from PIL import Image

    first, second, other = tmp_path / "a.png", tmp_path / "b.png", tmp_path / "c.png"
    Image.new("RGB", (40, 40), (10, 10, 10)).save(first)
    Image.new("RGB", (80, 80), (10, 10, 10)).save(second)  # même image à une autre taille
    gradient = Image.linear_gradient("L").convert("RGB")
    gradient.save(other)

    results = asyncio.run(ImageModule().run({"photo": f"{first}\n{second};{other}"}, None))
    infos = [r for r in results if r.data["kind"] == "info"]
    assert len(infos) == 3
    duplicates = [r for r in results if r.data["kind"] == "duplicate"]
    assert len(duplicates) == 1 and duplicates[0].data["first"] == str(first)


def test_cli_run_exports_and_signals_new_results(tmp_path, monkeypatch, capsys):
    get_settings().verify_profiles = False
    counter = {"n": 0}

    class Evolving(BaseModule):
        name = "fake"
        description = "d"
        requires = ["pseudo"]

        async def run(self, target_data, session, progress_cb=None):
            counter["n"] += 1
            urls = ["https://example.org/a"] + (["https://example.org/b"] if counter["n"] > 1 else [])
            return [OsintResult("fake", "Site", u, "t", "alice", 0.9) for u in urls]

    monkeypatch.setattr(cli, "EchoTraceEngine", lambda: EchoTraceEngine([Evolving()]))
    out = tmp_path / "exports"  # tmp_path sert aussi de ECHOTRACE_HOME : on isole les exports
    argv = ["run", "--pseudo", "alice", "--email", "a@b.fr", "--purpose", "1", "--quiet",
            "--export", "json,csv", "--out", str(out)]
    assert cli.main(argv) == cli.EXIT_OK
    assert sorted(p.suffix for p in out.iterdir()) == [".csv", ".json"]
    assert cli.main(argv) == cli.EXIT_NEW_RESULTS  # « b » est apparu depuis la première analyse
    assert "+ Site : https://example.org/b" in capsys.readouterr().out


def test_cli_rejects_unknown_purpose_and_format(capsys):
    assert cli.main(["run", "--pseudo", "alice", "--purpose", "curiosité"]) == cli.EXIT_INVALID
    assert cli.main(["run", "--pseudo", "alice", "--email", "a@b.fr", "--purpose", "1",
                     "--export", "docx", "--quiet"]) == cli.EXIT_INVALID
    assert cli.resolve_purpose("2") == PURPOSES[1] and cli.resolve_purpose("9") is None
