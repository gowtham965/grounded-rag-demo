"""Admin API: read/edit the system prompt and read the question log (ADMIN_TOKEN required)."""
from fastapi import APIRouter, Header
from pydantic import BaseModel, Field

from . import db
from .auth import require_admin

router = APIRouter(prefix="/admin")


class PromptIn(BaseModel):
    system_prompt: str = Field(min_length=10)


@router.get("/prompt")
def get_prompt(authorization: str | None = Header(None)):
    require_admin(authorization)
    return {"system_prompt": db.get_system_prompt()}


@router.put("/prompt")
def put_prompt(body: PromptIn, authorization: str | None = Header(None)):
    require_admin(authorization)
    db.set_system_prompt(body.system_prompt)
    return {"ok": True}


@router.get("/log")
def get_log(authorization: str | None = Header(None), limit: int = 100):
    require_admin(authorization)
    return db.recent(limit)
