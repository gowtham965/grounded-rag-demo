"""Build the messages sent to the LLM: the editable system prompt + numbered sources + question."""
from . import db
from .config import settings


def label(hit):
    """How a source is shown to the model and the user: 'doc.pdf (page 2)' or 'record INV-1057'."""
    return f"{hit['source']} (page {hit['page']})" if hit.get("page") else hit["source"]


def build_messages(question, hits):
    system = db.get_system_prompt().replace("{refusal}", settings.refusal_message)
    ctx = "\n\n".join(f"[{i}] {label(h)}\n{h['text']}" for i, h in enumerate(hits, 1))
    return [
        {"role": "system", "content": system},
        {"role": "user", "content": f"SOURCES:\n{ctx}\n\nQUESTION: {question}"},
    ]
