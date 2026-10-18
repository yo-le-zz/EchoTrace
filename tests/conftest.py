"""Fixtures communes : chaque test travaille dans un dossier ECHOTRACE_HOME isolé."""

import pytest

from echotrace.config import settings as settings_module
from echotrace.database import db


@pytest.fixture(autouse=True)
def isolated_home(tmp_path, monkeypatch):
    monkeypatch.setenv("ECHOTRACE_HOME", str(tmp_path))
    db._initialized.clear()
    settings_module._settings = None
    yield tmp_path
    settings_module._settings = None
    db._initialized.clear()
