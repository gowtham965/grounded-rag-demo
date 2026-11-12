from helpers import ask, fake_llm, no_llm


def test_cited_answer(app_env, monkeypatch):
    monkeypatch.setattr(app_env.rag, "llm_stream", fake_llm("[1]"))
    f = ask(app_env.rag, "acme", "What is the monthly rent and the late fee?")
    assert f["grounded"] and not f["refused"]
    assert f["sources"][0]["source"] == "Acme_Office_Lease.pdf" and f["sources"][0]["page"]


def test_invalid_citation_flagged(app_env, monkeypatch):
    monkeypatch.setattr(app_env.rag, "llm_stream", fake_llm("[99]"))
    f = ask(app_env.rag, "acme", "What is the monthly rent and the late fee?")
    assert not f["grounded"] and f["sources"] == []


def test_off_topic_refused_without_llm(app_env, monkeypatch):
    monkeypatch.setattr(app_env.rag, "llm_stream", no_llm)
    f = ask(app_env.rag, "acme", "zebra quantum basketball")
    assert f["refused"] and f["answer"] == app_env.config.settings.refusal_message


def test_exact_identifier_passes_gate(app_env, monkeypatch):
    # Even with a dense threshold nothing can reach, an exact ID found by BM25 must not be refused.
    monkeypatch.setattr(app_env.config.settings, "min_relevance", 0.99)
    monkeypatch.setattr(app_env.rag, "llm_stream", fake_llm("[1]"))
    assert not ask(app_env.rag, "acme", "What is INV-1057 for?")["refused"]


def test_unknown_identifier_still_refused(app_env, monkeypatch):
    monkeypatch.setattr(app_env.config.settings, "min_relevance", 0.99)
    monkeypatch.setattr(app_env.rag, "llm_stream", no_llm)
    assert ask(app_env.rag, "acme", "What is INV-9999 for?")["refused"]
