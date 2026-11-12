"""Offline tests: local-hash embeddings and a fake LLM, so no API key or network is needed."""
import asyncio
import importlib

import pytest


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
    import app.config, app.embed, app.ingest, app.retrieve, app.db, app.rag
    for m in (app.config, app.embed, app.ingest, app.retrieve, app.db, app.rag):
        importlib.reload(m)
    app.ingest.build(reindex=True)
    app.db.init()
    return app


def fake_llm(cite="[1]"):
    async def _stream(messages):
        src = messages[1]["content"].split("\n")[2]          # body text of source [1]
        for w in f"{src[:80]} {cite}".split(" "):
            yield w + " "
        yield {"prompt_tokens": 10, "completion_tokens": 5, "cost_usd": 0.0}
    return _stream


def collect(rag, customer, q):
    async def go():
        return [ev async for ev in rag.answer_stream(customer, q)][-1]
    return asyncio.run(go())


def test_ingest_keeps_pages_and_records(app_env):
    import json
    chunks = json.loads((app_env.config.settings.index_dir / "acme" / "chunks.json").read_text())
    pages = {(c["source"], c["page"]) for c in chunks}
    assert ("Acme_Office_Lease.pdf", 2) in pages
    assert any(c["source"] == "record INV-1057" for c in chunks)
    assert not any("Warranty" in c["source"] for c in chunks)   # held-back doc never ingested


def test_tenant_isolation(app_env):
    hits, _ = app_env.retrieve.retrieve("globex", "monthly rent Orion Business Park lease")
    assert all("Acme" not in h["source"] and "INV" not in h["source"] for h in hits)


def test_cited_answer(app_env, monkeypatch):
    monkeypatch.setattr(app_env.rag, "llm_stream", fake_llm("[1]"))
    f = collect(app_env.rag, "acme", "What is the monthly rent and the late fee?")
    assert f["grounded"] and not f["refused"]
    assert f["sources"][0]["source"] == "Acme_Office_Lease.pdf" and f["sources"][0]["page"]


def test_invalid_citation_flagged(app_env, monkeypatch):
    monkeypatch.setattr(app_env.rag, "llm_stream", fake_llm("[99]"))
    f = collect(app_env.rag, "acme", "What is the monthly rent and the late fee?")
    assert not f["grounded"] and f["sources"] == []


def test_off_topic_refused_without_llm(app_env, monkeypatch):
    async def boom(_):
        raise AssertionError("LLM must not be called")
        yield
    monkeypatch.setattr(app_env.rag, "llm_stream", boom)
    f = collect(app_env.rag, "acme", "zebra quantum basketball")
    assert f["refused"] and f["answer"] == app_env.config.settings.refusal_message


def test_api_auth_rate_limit_and_log(app_env, monkeypatch):
    import app.main
    importlib.reload(app.main)
    from fastapi.testclient import TestClient
    monkeypatch.setattr(app_env.rag, "llm_stream", fake_llm())
    c = TestClient(app.main.app)
    body = {"customer_id": "acme", "question": "What is the monthly rent?"}
    assert c.post("/chat", json=body).status_code == 401
    h = {"Authorization": "Bearer t", "X-User-Id": "u1"}
    r = c.post("/chat", json=body, headers=h)
    assert r.status_code == 200 and '"type": "final"' in r.text
    c.post("/chat", json=body, headers=h); c.post("/chat", json=body, headers=h)
    assert c.post("/chat", json=body, headers=h).status_code == 429
    log = c.get("/admin/log", headers={"Authorization": "Bearer a"}).json()
    assert len(log) == 3 and log[0]["sources"]
    assert c.put("/admin/prompt", json={"system_prompt": "Only use sources. {refusal}"},
                 headers={"Authorization": "Bearer a"}).status_code == 200
