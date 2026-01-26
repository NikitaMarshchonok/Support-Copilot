from __future__ import annotations

import json
from datetime import datetime
from pathlib import Path

from fastapi import APIRouter

from .schemas import SuggestReplyRequest, SuggestReplyResponse, FeedbackRequest
from .rag import generate_suggested_reply, get_active_provider_model
from .settings import settings


router = APIRouter()


@router.get("/health")
def health():
    provider, model = get_active_provider_model()
    return {
        "status": "ok",
        "collection": settings.qdrant_collection,
        "provider": provider,
        "model": model,
    }


@router.post("/suggest-reply", response_model=SuggestReplyResponse)
def suggest_reply(req: SuggestReplyRequest):
    resp = generate_suggested_reply(req.ticket_text, language=req.language, category=req.category)
    _log_history(req, resp)
    return resp


def _log_history(req: SuggestReplyRequest, resp: SuggestReplyResponse) -> None:
    try:
        Path("data/history").mkdir(parents=True, exist_ok=True)
        payload = resp.model_dump()
        row = {
            "ts": datetime.utcnow().isoformat() + "Z",
            "ticket_text": (req.ticket_text or "")[:4000],
            "language": req.language,
            "category": req.category,
            "draft_reply": (payload.get("draft_reply") or "")[:4000],
            "next_actions": payload.get("next_actions") or [],
            "clarifying_questions": payload.get("clarifying_questions") or [],
            "citations": (payload.get("citations") or [])[:4],
            "provider": (payload.get("debug") or {}).get("mode"),
            "model": (payload.get("debug") or {}).get("model"),
        }
        with open("data/history/history.jsonl", "a", encoding="utf-8") as f:
            f.write(json.dumps(row, ensure_ascii=False) + "\n")
    except Exception:
        pass


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
