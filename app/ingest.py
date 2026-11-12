"""Build the per-customer index (vectors.npy + chunks.json) from the sources in app/loaders.py.

Usage:   python -m app.ingest            # build (skips customers whose files are unchanged)
         python -m app.ingest --reindex  # wipe and rebuild
"""
import argparse
import hashlib
import json
import shutil

import numpy as np

from .config import settings
from .embed import embed
from .loaders import load_all


def customers():
    names = {p.name for p in settings.docs_dir.iterdir() if p.is_dir()} if settings.docs_dir.exists() else set()
    names |= {p.stem for p in settings.records_dir.glob("*.json")} if settings.records_dir.exists() else set()
    return sorted(names)


def _fingerprint(customer):
    """Changes whenever the embed model or any of this customer's files change."""
    h = hashlib.sha256(settings.embed_model.encode())
    for p in sorted((settings.docs_dir / customer).glob("*.pdf")):
        h.update(p.name.encode()); h.update(p.read_bytes())
    for p in [settings.records_dir / f"{customer}.json", settings.urls_file]:
        if p.exists():
            h.update(p.read_bytes())
    return h.hexdigest()


def build(reindex: bool = False):
    if reindex and settings.index_dir.exists():
        shutil.rmtree(settings.index_dir)
    settings.index_dir.mkdir(parents=True, exist_ok=True)
    for cust in customers():
        out = settings.index_dir / cust
        fp = _fingerprint(cust)
        if (out / "fingerprint").exists() and (out / "fingerprint").read_text() == fp:
            print(f"{cust}: up to date")
            continue
        chunks = load_all(cust)
        if not chunks:
            continue
        vecs = embed([c["text"] for c in chunks])
        out.mkdir(parents=True, exist_ok=True)
        np.save(out / "vectors.npy", vecs)
        (out / "chunks.json").write_text(json.dumps(chunks, indent=1))
        (out / "fingerprint").write_text(fp)
        n_src = len({c["source"] for c in chunks})
        print(f"{cust}: indexed {len(chunks)} chunks from {n_src} sources")


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--reindex", action="store_true", help="wipe the index and rebuild everything")
    build(ap.parse_args().reindex)
