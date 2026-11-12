from helpers import fake_llm


def test_auth_rate_limit_and_log(app_env, client, monkeypatch):
    monkeypatch.setattr(app_env.rag, "llm_stream", fake_llm())
    c = client()
    body = {"customer_id": "acme", "question": "What is the monthly rent?"}
    assert c.post("/chat", json=body).status_code == 401
    h = {"Authorization": "Bearer t", "X-User-Id": "u1"}
    r = c.post("/chat", json=body, headers=h)
    assert r.status_code == 200 and '"type": "final"' in r.text
    c.post("/chat", json=body, headers=h); c.post("/chat", json=body, headers=h)
    assert c.post("/chat", json=body, headers=h).status_code == 429
    log = c.get("/admin/log", headers={"Authorization": "Bearer a"}).json()
    assert len(log) == 3 and log[0]["sources"]


def test_admin_prompt(client):
    c = client()
    admin = {"Authorization": "Bearer a"}
    assert c.get("/admin/prompt").status_code == 401
    assert c.put("/admin/prompt", json={"system_prompt": "Only use sources. {refusal}"}, headers=admin).status_code == 200
    assert c.get("/admin/prompt", headers=admin).json()["system_prompt"] == "Only use sources. {refusal}"


def test_bad_customer_id_rejected(client):
    c = client()
    h = {"Authorization": "Bearer t"}
    for bad in ["../acme", "acme/../globex", "a b", "."]:
        assert c.post("/chat", json={"customer_id": bad, "question": "rent?"}, headers=h).status_code == 422


def test_customer_tokens_bind_tenant(app_env, client, monkeypatch):
    monkeypatch.setenv("CUSTOMER_TOKENS", "acme:tok-acme, globex:tok-globex")
    c = client()
    monkeypatch.setattr(app_env.main, "answer_stream", _fake_answer_stream)
    body = {"customer_id": "acme", "question": "What is the monthly rent?"}
    assert c.post("/chat", json=body, headers={"Authorization": "Bearer tok-globex"}).status_code == 403
    assert c.post("/chat", json=body, headers={"Authorization": "Bearer t"}).status_code == 401   # shared token disabled
    assert c.post("/chat", json=body, headers={"Authorization": "Bearer tok-acme"}).status_code == 200


async def _fake_answer_stream(customer_id, question, user_id):
    yield {"type": "final", "answer": "ok", "sources": []}


def test_react_panel_served(client):
    c = client()
    assert "/static/react/panel.js" in c.get("/app").text
    assert c.get("/static/react/panel.js").status_code == 200
    assert c.get("/static/react/panel.css").status_code == 200
