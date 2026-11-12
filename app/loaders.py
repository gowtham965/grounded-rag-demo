"""Turn each kind of source into chunks: {"text", "source", "page", "kind"}.

  PDFs     data/docs/<customer_id>/*.pdf          -> chunks keep document name + page
  Web      data/urls.txt "<customer_id> <url>"   -> chunks cited by URL
  Records  data/records/<customer_id>.json        -> one chunk per record, cited by record id
"""
import json
import re

import pymupdf

from .config import settings

CHUNK_WORDS, OVERLAP = 180, 40


def split_words(text: str):
    """~180-word chunks with 40 words of overlap, so a fact on a boundary lands whole in one chunk."""
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
                for c in split_words(text):
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
        for c in split_words(text):
            yield {"text": c, "source": parts[1], "page": None, "kind": "web"}


def load_records(customer):
    f = settings.records_dir / f"{customer}.json"
    if not f.exists():
        return
    for rec in json.loads(f.read_text()):
        text = "; ".join(f"{k}: {v}" for k, v in rec.items())
        yield {"text": text, "source": f"record {rec['id']}", "page": None, "kind": "record"}


def load_all(customer):
    return (list(load_pdfs(settings.docs_dir / customer))
            + list(load_urls(customer))
            + list(load_records(customer)))
