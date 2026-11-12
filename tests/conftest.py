"""Shared offline test fixtures: local-hash embeddings and a fake LLM, so no API key or network is needed."""
import importlib

import pytest

# Reload order matters: each module must be reloaded after the modules it imports from.
CORE = ["config", "embed", "loaders", "ingest", "retrieve", "db", "prompt", "llm", "citations", "rag"]
API = ["auth", "admin", "main"]


def _reload(names):
    for m in [importlib.import_module(f"app.{n}") for n in names]:
        importlib.reload(m)


@pytest.fixture()
def app_env(tmp_path, monkeypatch):
    monkeypatch.setenv("EMBED_MODEL", "local-hash")
    monkeypatch.setenv("CHAT_MODEL", "fake")
    monkeypatch.setenv("INDEX_DIR", str(tmp_path / "index"))
    monkeypatch.setenv("DB_PATH", str(tmp_path / "log.sqlite3"))
    monkeypatch.setenv("API_TOKEN", "t")
    monkeypatch.setenv("ADMIN_TOKEN", "a")
    monkeypatch.setenv("MIN_RELEVANCE", "0.2")
    monkeypatch.setenv("RATE_LIMIT_PER_MIN", "3")
    monkeypatch.delenv("CUSTOMER_TOKENS", raising=False)
    _reload(CORE)
    import app
    app.ingest.build(reindex=True)
    app.db.init()
    return app


@pytest.fixture()
def client(app_env):
    """Call client() to build a TestClient from the current env (after any setenv)."""
    from fastapi.testclient import TestClient

    def make():
        _reload(["config"] + API)
        return TestClient(app_env.main.app)
    return make
