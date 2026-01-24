from __future__ import annotations

import json
from datetime import datetime
from pathlib import Path

from fastapi import APIRouter

from .schemas import SuggestReplyRequest, SuggestReplyResponse, FeedbackRequest
from .rag import generate_suggested_reply
from .settings import settings


router = APIRouter()


@router.get("/health")
def health():
    return {"status": "ok", "collection": settings.qdrant_collection, "model": settings.openai_model}


@router.post("/suggest-reply", response_model=SuggestReplyResponse)
def suggest_reply(req: SuggestReplyRequest):
    return generate_suggested_reply(req.ticket_text, language=req.language, category=req.category)


@router.post("/feedback")
def feedback(req: FeedbackRequest):
    Path("data/feedback").mkdir(parents=True, exist_ok=True)
    row = {
        "ts": datetime.utcnow().isoformat() + "Z",
        "helpful": req.helpful,
        "comment": req.comment,
        "model": req.model,
        "ticket_text": req.ticket_text[:4000],
    }
    with open("data/feedback/feedback.jsonl", "a", encoding="utf-8") as f:
        f.write(json.dumps(row, ensure_ascii=False) + "\n")
    return {"status": "saved"}
