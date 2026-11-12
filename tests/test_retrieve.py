def test_tenant_isolation(app_env):
    hits, _ = app_env.retrieve.retrieve("globex", "monthly rent Orion Business Park lease")
    assert all("Acme" not in h["source"] and "INV" not in h["source"] for h in hits)


def test_bad_customer_id_opens_nothing(app_env):
    assert app_env.retrieve.retrieve("../index", "rent") == ([], 0.0)


def test_exact_identifier_is_found(app_env):
    hits, _ = app_env.retrieve.retrieve("acme", "What is INV-1057 for?")
    assert any(h["source"] == "record INV-1057" for h in hits)
    assert app_env.retrieve.identifier_match("What is INV-1057 for?", hits)
    assert not app_env.retrieve.identifier_match("What is INV-9999 for?", hits)
