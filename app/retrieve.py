"""Hybrid retrieval (vector + BM25, fused with reciprocal rank fusion), strictly per customer."""
import json
import re
from functools import lru_cache

import numpy as np
from rank_bm25 import BM25Okapi

from .config import settings
from .embed import embed


CUSTOMER_ID = re.compile(r"^[A-Za-z0-9_-]{1,64}$")


def _tok(s):
    return re.findall(r"[a-z0-9]+", s.lower())


def identifier_match(question: str, hits) -> bool:
    """True if the question names an exact identifier (a token with a digit, 3+ chars, e.g. the
    '1057' in INV-1057) that appears verbatim in a retrieved chunk. Dense embeddings often score
    such questions low, so this lets BM25's exact matches through the relevance gate."""
    ids = {t for t in _tok(question) if len(t) >= 3 and any(ch.isdigit() for ch in t)}
    return bool(ids) and any(ids & set(_tok(h["text"])) for h in hits)


@lru_cache(maxsize=64)
def _load(customer: str):
    if not CUSTOMER_ID.match(customer):   # never let a customer id turn into a path outside the index
        return None
    d = settings.index_dir / customer
    if not (d / "chunks.json").exists():
        return None
    chunks = json.loads((d / "chunks.json").read_text())
    return chunks, np.load(d / "vectors.npy"), BM25Okapi([_tok(c["text"]) for c in chunks])


def clear_cache():
    _load.cache_clear()


def retrieve(customer: str, question: str, k: int | None = None):
    """Returns (hits, best_similarity). Only this customer's index is ever opened."""
    k = k or settings.top_k
    loaded = _load(customer)
    if not loaded:
        return [], 0.0
    chunks, vecs, bm25 = loaded
    sims = vecs @ embed([question])[0]
    bm = bm25.get_scores(_tok(question))
    rrf = np.zeros(len(chunks))
    for ranking in (np.argsort(-sims), np.argsort(-bm)):
        for rank, idx in enumerate(ranking):
            rrf[idx] += 1.0 / (60 + rank)
    order = np.argsort(-rrf)[:k]
    hits = [{**chunks[i], "similarity": float(sims[i])} for i in order]
    return hits, float(sims.max())
