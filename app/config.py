"""All settings come from the environment (.env). No keys or model names are hard-coded."""
import os
from pathlib import Path
from dotenv import load_dotenv

load_dotenv()
ROOT = Path(__file__).resolve().parent.parent


def _req(name: str) -> str:
    v = os.getenv(name)
    if not v:
        raise RuntimeError(f"Missing required env var {name} (see .env.example)")
    return v


class Settings:
    chat_model = os.getenv("CHAT_MODEL", "")            # e.g. gpt-4o-mini, claude-..., any LiteLLM id
    embed_model = os.getenv("EMBED_MODEL", "")          # e.g. text-embedding-3-small, or local-hash for offline tests
    docs_dir = Path(os.getenv("DOCS_DIR", ROOT / "data/docs"))
    records_dir = Path(os.getenv("RECORDS_DIR", ROOT / "data/records"))
    urls_file = Path(os.getenv("URLS_FILE", ROOT / "data/urls.txt"))
    index_dir = Path(os.getenv("INDEX_DIR", ROOT / "index"))
    db_path = Path(os.getenv("DB_PATH", ROOT / "rag_log.sqlite3"))
    top_k = int(os.getenv("TOP_K", "5"))
    min_relevance = float(os.getenv("MIN_RELEVANCE", "0.30"))   # below this, refuse without calling the LLM
    max_answer_tokens = int(os.getenv("MAX_ANSWER_TOKENS", "400"))
    rate_limit_per_min = int(os.getenv("RATE_LIMIT_PER_MIN", "10"))
    api_token = os.getenv("API_TOKEN", "")              # bearer token for /chat (stand-in for your app's login)
    admin_token = os.getenv("ADMIN_TOKEN", "")
    refusal_message = os.getenv(
        "REFUSAL_MESSAGE", "That isn't in your documents, so I can't answer it."
    )


settings = Settings()

DEFAULT_SYSTEM_PROMPT = """You answer questions for one customer using ONLY the numbered sources below.
Rules:
- Every factual sentence must end with the source number(s) it came from, like [1] or [2][3].
- If the sources do not contain the answer, reply with exactly: {refusal}
- Never use outside or general knowledge, even if you know the answer.
- Be concise."""
