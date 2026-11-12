"""Ingest PDFs, web pages and customer records into a per-customer vector index.

Layout:  data/docs/<customer_id>/*.pdf     -> chunks keep document name + page
         data/urls.txt  lines "<customer_id> <url>"  -> web pages
         data/records/<customer_id>.json   -> one chunk per record, cited by record id

Usage:   python -m app.ingest            # build (skips if unchanged)
         python -m app.ingest --reindex  # wipe and rebuild
"""
import argparse
import hashlib
import json
import re
import shutil

import numpy as np
import pymupdf

from .config import settings
from .embed import embed

CHUNK_WORDS, OVERLAP = 180, 40


def _chunks(text: str):
    words = text.split()
    step = CHUNK_WORDS - OVERLAP
    for i in range(0, max(len(words), 1), step):
        piece = " ".join(words[i:i + CHUNK_WORDS])
        if piece.strip():
            yield piece
        if i + CHUNK_WORDS >= len(words):
            break


def load_pdfs(customer_dir):
    for pdf in sorted(customer_dir.glob("*.pdf")):
        with pymupdf.open(pdf) as doc:
            for page_no, page in enumerate(doc, start=1):
                text = re.sub(r"\s+", " ", page.get_text()).strip()
                for c in _chunks(text):
                    yield {"text": c, "source": pdf.name, "page": page_no, "kind": "document"}


def load_urls(customer):
    if not settings.urls_file.exists():
        return
    import trafilatura
    for line in settings.urls_file.read_text().splitlines():
        parts = line.split()
        if len(parts) != 2 or parts[0] != customer:
            continue
        html = trafilatura.fetch_url(parts[1])
        text = trafilatura.extract(html) if html else None
        if not text:
            print(f"  ! could not fetch {parts[1]}")
            continue
        for c in _chunks(text):
            yield {"text": c, "source": parts[1], "page": None, "kind": "web"}


def load_records(customer):
    f = settings.records_dir / f"{customer}.json"
    if not f.exists():
        return
    for rec in json.loads(f.read_text()):
        text = "; ".join(f"{k}: {v}" for k, v in rec.items())
        yield {"text": text, "source": f"record {rec['id']}", "page": None, "kind": "record"}


def customers():
    names = {p.name for p in settings.docs_dir.iterdir() if p.is_dir()} if settings.docs_dir.exists() else set()
    names |= {p.stem for p in settings.records_dir.glob("*.json")} if settings.records_dir.exists() else set()
    return sorted(names)


def _fingerprint(customer):
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
        chunks = list(load_pdfs(settings.docs_dir / cust)) + list(load_urls(cust)) + list(load_records(cust))
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
