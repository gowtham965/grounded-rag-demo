"""Grounded answering: retrieve -> relevance gate -> stream LLM answer -> check citations -> log.

Each step lives in its own module:
  retrieve.py   hybrid search + identifier_match     prompt.py     messages sent to the model
  llm.py        streaming model call                  citations.py  refusal / citation / grounded checks
  db.py         question log
"""
import time

from . import db
from .citations import check
from .config import settings
from .llm import llm_stream
from .prompt import build_messages
from .retrieve import identifier_match, retrieve


def _ms_since(t0):
    return int((time.perf_counter() - t0) * 1000)


def _passes_gate(question, hits, best):
    """Gate 1: something relevant was retrieved (a close embedding or an exact ID match)."""
    return bool(hits) and (best >= settings.min_relevance or identifier_match(question, hits))


async def answer_stream(customer_id: str, question: str, user_id: str = "anon"):
    """Async generator of events: {'type':'token'}..., then one {'type':'final', ...}."""
    t0 = time.perf_counter()
    hits, best = retrieve(customer_id, question)
    first_ms, text, usage = None, "", {}

    if not _passes_gate(question, hits, best):
        # Fixed refusal; the LLM is never called.
        text, first_ms, hits = settings.refusal_message, _ms_since(t0), []
        yield {"type": "token", "text": text}
    else:
        async for piece in llm_stream(build_messages(question, hits)):
            if isinstance(piece, dict):
                usage = piece
                continue
            if first_ms is None:
                first_ms = _ms_since(t0)
            text += piece
            yield {"type": "token", "text": piece}

    sources, refused, grounded = check(text, hits)
    final = {"type": "final", "answer": text, "sources": sources, "refused": refused,
             "grounded": grounded, "first_token_ms": first_ms, "total_ms": _ms_since(t0), **usage}
    db.log(customer_id=customer_id, user_id=user_id, question=question, answer=text, sources=sources,
           refused=int(refused), grounded=int(grounded), prompt_tokens=usage.get("prompt_tokens", 0),
           completion_tokens=usage.get("completion_tokens", 0), cost_usd=usage.get("cost_usd"),
           first_token_ms=first_ms, total_ms=final["total_ms"])
    yield final
