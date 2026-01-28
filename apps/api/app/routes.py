from __future__ import annotations

import json
from datetime import datetime
from time import perf_counter
from pathlib import Path

from fastapi import APIRouter

from .schemas import SuggestReplyRequest, SuggestReplyResponse, FeedbackRequest
from .rag import generate_suggested_reply, get_active_provider_model
from .settings import settings


router = APIRouter()


@router.get("/health")
def health():
    provider, model = get_active_provider_model()
    kb_version = _read_kb_version()
    return {
        "status": "ok",
        "collection": settings.qdrant_collection,
        "provider": provider,
        "model": model,
        "kb_version": kb_version,
    }


@router.post("/suggest-reply", response_model=SuggestReplyResponse)
def suggest_reply(req: SuggestReplyRequest):
    started = perf_counter()
    resp = generate_suggested_reply(req.ticket_text, language=req.language, category=req.category)
    _log_history(req, resp)
    _log_metrics(req, resp, started)
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


def _log_metrics(req: SuggestReplyRequest, resp: SuggestReplyResponse, started: float) -> None:
    try:
        Path("data/metrics").mkdir(parents=True, exist_ok=True)
        payload = resp.model_dump()
        row = {
            "ts": datetime.utcnow().isoformat() + "Z",
            "duration_ms": int((perf_counter() - started) * 1000),
            "provider": (payload.get("debug") or {}).get("mode"),
            "model": (payload.get("debug") or {}).get("model"),
            "confidence": payload.get("confidence"),
            "language": payload.get("language"),
            "category": req.category,
            "citations_count": len(payload.get("citations") or []),
        }
        with open("data/metrics/metrics.jsonl", "a", encoding="utf-8") as f:
            f.write(json.dumps(row, ensure_ascii=False) + "\n")
    except Exception:
        pass


def _read_kb_version() -> dict | None:
    path = Path("data/kb_version.json")
    if not path.exists():
        return None
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError:
        return None


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
