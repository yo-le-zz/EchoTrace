import asyncio
import threading

from echotrace.core.engine import EchoTraceEngine, build_summary, default_label
from echotrace.database import db
from echotrace.modules.base import BaseModule, OsintResult

TARGET = {"pseudo": "alice", "email": "alice@example.org"}


class FakeModule(BaseModule):
    name = "fake"
    description = "module de test"
    requires = ["pseudo"]

    async def run(self, target_data, session, progress_cb=None):
        if progress_cb:
            progress_cb("travail", 50)
        return [OsintResult("fake", "Site", "https://example.org/alice", "t", "alice", 0.9)]


class BrokenModule(FakeModule):
    name = "broken"

    async def run(self, target_data, session, progress_cb=None):
        raise RuntimeError("boum")


class SlowModule(FakeModule):
    name = "slow"

    async def run(self, target_data, session, progress_cb=None):
        await asyncio.sleep(30)
        return []


def test_analysis_saves_results_and_isolates_module_errors():
    engine = EchoTraceEngine([FakeModule(), BrokenModule()])
    messages = []
    result = asyncio.run(engine.run_analysis(TARGET, lambda m, p: messages.append((m, p))))

    assert result["success"] and not result["cancelled"]
    assert result["results_count"] == 1
    assert "broken" in result["errors"]
    assert result["summary"]["total"] == 1
    assert messages[-1][1] == 100
    assert db.list_targets()[0]["label"] == "alice"
    assert not engine.running


def test_invalid_input_is_rejected():
    result = asyncio.run(EchoTraceEngine([FakeModule()]).run_analysis({"pseudo": "alice"}))
    assert not result["success"] and result["target_id"] is None


def test_stop_analysis_cancels_running_modules():
    engine = EchoTraceEngine([FakeModule(), SlowModule()])
    started = threading.Event()
    timer = threading.Timer(0.5, lambda: (started.set(), engine.stop_analysis()))
    timer.start()
    result = asyncio.run(asyncio.wait_for(engine.run_analysis(TARGET), timeout=10))
    timer.cancel()

    assert started.is_set()
    assert result["success"] and result["cancelled"]
    assert result["results_count"] == 1  # le module terminé conserve ses résultats


def test_summary_and_label_helpers():
    assert build_summary([])["avg_confidence"] == 0.0
    summary = build_summary([{"platform": "A", "module": "m", "confidence": 0.9},
                             {"platform": "A", "module": "m", "confidence": 0.1}])
    assert summary["platforms"] == [("A", 2)] and summary["high_confidence"] == 1
    assert default_label({"prenom": "Jean", "nom": "Dupont"}) == "Jean Dupont"
    assert default_label({}) == "Sans nom"
