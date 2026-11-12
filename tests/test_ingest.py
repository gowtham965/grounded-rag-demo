import json


def test_ingest_keeps_pages_and_records(app_env):
    chunks = json.loads((app_env.config.settings.index_dir / "acme" / "chunks.json").read_text())
    pages = {(c["source"], c["page"]) for c in chunks}
    assert ("Acme_Office_Lease.pdf", 2) in pages
    assert any(c["source"] == "record INV-1057" for c in chunks)
    assert not any("Warranty" in c["source"] for c in chunks)   # held-back doc never ingested
