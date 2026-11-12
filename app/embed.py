"""Embedding wrapper. Uses LiteLLM so any provider works; 'local-hash' is an offline mode for tests/CI."""
import hashlib
import re
import numpy as np
from .config import settings

_DIM = 512


def _hash_embed(text: str) -> np.ndarray:
    v = np.zeros(_DIM, dtype=np.float32)
    for tok in re.findall(r"[a-z0-9]+", text.lower()):
        v[int(hashlib.md5(tok.encode()).hexdigest(), 16) % _DIM] += 1.0
    return v


def embed(texts: list[str]) -> np.ndarray:
    if not settings.embed_model:
        raise RuntimeError("Set EMBED_MODEL in .env")
    if settings.embed_model == "local-hash":
        m = np.stack([_hash_embed(t) for t in texts])
    else:
        import litellm
        out = []
        for i in range(0, len(texts), 64):
            resp = litellm.embedding(model=settings.embed_model, input=texts[i:i + 64])
            out.extend(d["embedding"] for d in resp.data)
        m = np.array(out, dtype=np.float32)
    norms = np.linalg.norm(m, axis=1, keepdims=True)
    return m / np.where(norms == 0, 1, norms)
