"""FastAPI app: POST /chat streams Server-Sent Events; /admin for prompt + log."""
import json
import time
from collections import defaultdict, deque

from fastapi import FastAPI, Header, HTTPException
from fastapi.responses import FileResponse, StreamingResponse
from pydantic import BaseModel, Field

from . import db
from .config import settings, ROOT
from .rag import answer_stream

app = FastAPI(title="Grounded RAG demo")
db.init()
_hits: dict[str, deque] = defaultdict(deque)


def _auth(authorization: str | None, expected: str):
    if not expected:
        raise HTTPException(500, "Server token not configured")
    if authorization != f"Bearer {expected}":
        raise HTTPException(401, "Unauthorized")


def _auth_chat(authorization: str | None, customer_id: str):
    """With CUSTOMER_TOKENS set, a token may only query the customer it belongs to."""
    if not settings.customer_tokens:
        return _auth(authorization, settings.api_token)
    token = authorization[7:] if authorization and authorization.startswith("Bearer ") else None
    owner = settings.customer_tokens.get(token) if token else None
    if owner is None:
        raise HTTPException(401, "Unauthorized")
    if owner != customer_id:
        raise HTTPException(403, "This token can't access that customer")


def _throttle(user: str):
    now, q = time.time(), _hits[user]
    while q and now - q[0] > 60:
        q.popleft()
    if len(q) >= settings.rate_limit_per_min:
        raise HTTPException(429, "Too many questions - try again in a minute")
    q.append(now)


class ChatIn(BaseModel):
    customer_id: str = Field(pattern=r"^[A-Za-z0-9_-]{1,64}$")
    question: str = Field(min_length=1, max_length=2000)


@app.post("/chat")
async def chat(body: ChatIn, authorization: str | None = Header(None), x_user_id: str = Header("anon")):
    # In your app, customer_id comes from the logged-in session, never from the client body.
    _auth_chat(authorization, body.customer_id)
    _throttle(f"{body.customer_id}:{x_user_id}")

    async def sse():
        try:
            async for ev in answer_stream(body.customer_id, body.question, x_user_id):
                yield f"data: {json.dumps(ev)}\n\n"
        except Exception as e:  # never leave the panel hanging on a provider error
            yield f"data: {json.dumps({'type': 'error', 'message': type(e).__name__})}\n\n"

    return StreamingResponse(sse(), media_type="text/event-stream")


class PromptIn(BaseModel):
    system_prompt: str = Field(min_length=10)


@app.get("/admin/prompt")
def get_prompt(authorization: str | None = Header(None)):
    _auth(authorization, settings.admin_token)
    return {"system_prompt": db.get_system_prompt()}


@app.put("/admin/prompt")
def put_prompt(body: PromptIn, authorization: str | None = Header(None)):
    _auth(authorization, settings.admin_token)
    db.set_system_prompt(body.system_prompt)
    return {"ok": True}


@app.get("/admin/log")
def get_log(authorization: str | None = Header(None), limit: int = 100):
    _auth(authorization, settings.admin_token)
    return db.recent(limit)


@app.get("/")
def panel():
    return FileResponse(ROOT / "web/index.html")


@app.get("/admin")
def admin_page():
    return FileResponse(ROOT / "web/admin.html")
