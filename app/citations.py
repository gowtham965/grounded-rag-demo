"""Check a finished answer: was it a refusal, which [n] citations are real, is it grounded?"""
import re

from .config import settings
from .prompt import label

CITE = re.compile(r"\[(\d+)\]")


def is_refusal(text: str) -> bool:
    return settings.refusal_message.lower().rstrip(".") in text.lower()


def valid_sources(text: str, hits):
    """Keep only citations that point at a chunk we actually passed to the model."""
    cited = sorted({int(n) for n in CITE.findall(text) if 1 <= int(n) <= len(hits)})
    return [{"n": i, "label": label(hits[i - 1]), "source": hits[i - 1]["source"],
             "page": hits[i - 1].get("page"), "kind": hits[i - 1]["kind"],
             "excerpt": hits[i - 1]["text"][:300]} for i in cited]


def check(text: str, hits):
    """Returns (sources, refused, grounded). An answer with no valid citation is ungrounded."""
    refused = is_refusal(text)
    sources = valid_sources(text, hits)
    return sources, refused, refused or bool(sources)
