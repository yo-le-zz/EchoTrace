import time

from echotrace.database import db
from echotrace.modules.base import OsintResult


def test_target_and_results_roundtrip():
    target_id = db.save_target({"pseudo": "alice"}, 50, "Alice")
    db.save_results(target_id, None, [
        OsintResult("username", "GitHub", "https://github.com/alice", "t", "alice", 0.9, {"a": 1}),
        OsintResult("google", "Bing", "https://example.org", "t2", "", 0.3),
    ])
    results = db.get_results(target_id)
    assert [r["platform"] for r in results] == ["GitHub", "Bing"]  # tri par confiance
    assert results[0]["data"] == {"a": 1}
    listed = db.list_targets()
    assert listed[0]["results_count"] == 2
    assert db.get_target(target_id)["data"] == {"pseudo": "alice"}


def test_delete_target_cascades():
    target_id = db.save_target({"pseudo": "alice"}, 50)
    db.save_result(target_id, None, "m", "p", "u", "t", "", 0.5, {})
    db.delete_target(target_id)
    assert db.get_results(target_id) == []
    assert db.get_target(target_id) is None


def test_cache_ttl_and_clean():
    db.cache_set("k", {"v": 1}, ttl_seconds=60)
    assert db.cache_get("k") == {"v": 1}
    db.cache_set("old", 1, ttl_seconds=-1)
    assert db.cache_get("old") is None
    db.cache_clean()
    db.cache_clear()
    assert db.cache_get("k") is None


def test_search_tracking():
    target_id = db.save_target({}, 0)
    search_id = db.start_search(target_id, "username", "q")
    time.sleep(0.01)
    db.finish_search(search_id, "done")
    with db.get_conn() as conn:
        row = conn.execute("SELECT status, finished_at FROM searches WHERE id=?", (search_id,)).fetchone()
    assert row["status"] == "done" and row["finished_at"] is not None
