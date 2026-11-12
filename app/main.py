"""FastAPI app: POST /chat streams Server-Sent Events; HTML pages; admin API from admin.py."""
import json

from fastapi import FastAPI, Header
from fastapi.responses import FileResponse, StreamingResponse
from pydantic import BaseModel, Field

from . import db
from .admin import router as admin_router
from .auth import require_customer, throttle
from .config import ROOT
from .rag import answer_stream

app = FastAPI(title="Grounded RAG demo")
app.include_router(admin_router)
db.init()


class ChatIn(BaseModel):
    customer_id: str = Field(pattern=r"^[A-Za-z0-9_-]{1,64}$")
    question: str = Field(min_length=1, max_length=2000)


@app.post("/chat")
async def chat(body: ChatIn, authorization: str | None = Header(None), x_user_id: str = Header("anon")):
    # In your app, customer_id comes from the logged-in session, never from the client body.
    require_customer(authorization, body.customer_id)
    throttle(f"{body.customer_id}:{x_user_id}")

    async def sse():
        try:
            async for ev in answer_stream(body.customer_id, body.question, x_user_id):
                yield f"data: {json.dumps(ev)}\n\n"
        except Exception as e:  # never leave the panel hanging on a provider error
            yield f"data: {json.dumps({'type': 'error', 'message': type(e).__name__})}\n\n"

    return StreamingResponse(sse(), media_type="text/event-stream")


@app.get("/")
def panel():
    return FileResponse(ROOT / "web/index.html")


@app.get("/admin")
def admin_page():
    return FileResponse(ROOT / "web/admin.html")
