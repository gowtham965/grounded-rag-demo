"""Grounded answering: retrieve -> gate -> stream with numbered citations -> verify citations -> log."""
import re
import time

from . import db
from .config import settings
from .retrieve import retrieve

CITE = re.compile(r"\[(\d+)\]")


def _label(h):
    return f"{h['source']} (page {h['page']})" if h.get("page") else h["source"]


def build_messages(question, hits):
    system = db.get_system_prompt().replace("{refusal}", settings.refusal_message)
    ctx = "\n\n".join(f"[{i}] {_label(h)}\n{h['text']}" for i, h in enumerate(hits, 1))
    return [
        {"role": "system", "content": system},
        {"role": "user", "content": f"SOURCES:\n{ctx}\n\nQUESTION: {question}"},
    ]


async def llm_stream(messages):
    """Yields text deltas, then a final dict with usage/cost. Patched out in tests."""
    import litellm
    if not settings.chat_model:
        raise RuntimeError("Set CHAT_MODEL in .env")
    resp = await litellm.acompletion(
        model=settings.chat_model, messages=messages, stream=True, temperature=0,
        max_tokens=settings.max_answer_tokens, stream_options={"include_usage": True},
    )
    usage = None
    async for chunk in resp:
        if getattr(chunk, "usage", None):
            usage = chunk.usage
        if chunk.choices and chunk.choices[0].delta and chunk.choices[0].delta.content:
            yield chunk.choices[0].delta.content
    pt = getattr(usage, "prompt_tokens", 0) or 0
    ct = getattr(usage, "completion_tokens", 0) or 0
    try:
        p, c = litellm.cost_per_token(model=settings.chat_model, prompt_tokens=pt, completion_tokens=ct)
        cost = p + c
    except Exception:
        cost = None
    yield {"prompt_tokens": pt, "completion_tokens": ct, "cost_usd": cost}


async def answer_stream(customer_id: str, question: str, user_id: str = "anon"):
    """Async generator of events: {'type':'token'}, then {'type':'final', ...}."""
    t0 = time.perf_counter()
    hits, best = retrieve(customer_id, question)
    first_ms, text, usage = None, "", {}

    if not hits or best < settings.min_relevance:
        # Gate 1: nothing relevant retrieved -> fixed refusal, the LLM is never called.
        text = settings.refusal_message
        first_ms = int((time.perf_counter() - t0) * 1000)
        yield {"type": "token", "text": text}
        hits = []
    else:
        async for piece in llm_stream(build_messages(question, hits)):
            if isinstance(piece, dict):
                usage = piece
                continue
            if first_ms is None:
                first_ms = int((time.perf_counter() - t0) * 1000)
            text += piece
            yield {"type": "token", "text": piece}

    refused = settings.refusal_message.lower().rstrip(".") in text.lower()
    # Gate 2: keep only citations that point at a chunk we actually passed to the model.
    cited_ids = sorted({int(n) for n in CITE.findall(text) if 1 <= int(n) <= len(hits)})
    sources = [{"n": i, "label": _label(hits[i - 1]), "source": hits[i - 1]["source"],
                "page": hits[i - 1].get("page"), "kind": hits[i - 1]["kind"],
                "excerpt": hits[i - 1]["text"][:300]} for i in cited_ids]
    grounded = refused or bool(sources)   # an answer with no valid citation is flagged as ungrounded

    final = {"type": "final", "answer": text, "sources": sources, "refused": refused,
             "grounded": grounded, "first_token_ms": first_ms,
             "total_ms": int((time.perf_counter() - t0) * 1000), **usage}
    db.log(customer_id=customer_id, user_id=user_id, question=question, answer=text, sources=sources,
           refused=int(refused), grounded=int(grounded), prompt_tokens=usage.get("prompt_tokens", 0),
           completion_tokens=usage.get("completion_tokens", 0), cost_usd=usage.get("cost_usd"),
           first_token_ms=first_ms, total_ms=final["total_ms"])
    yield final
