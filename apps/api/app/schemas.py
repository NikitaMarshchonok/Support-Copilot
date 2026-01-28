from __future__ import annotations

from pydantic import BaseModel, Field


class SuggestReplyRequest(BaseModel):
    ticket_text: str = Field(min_length=3, description="Raw customer ticket / chat text")
    language: str = Field(default="en", description="en|ru|he")
    category: str | None = Field(default=None, description="Optional: cancellation|payment|account|...")


class Citation(BaseModel):
    title: str
    url: str | None = None
    snippet: str


class SuggestReplyResponse(BaseModel):
    draft_reply: str
    citations: list[Citation]
    next_actions: list[str]
    clarifying_questions: list[str] = []
    confidence: float = Field(ge=0.0, le=1.0)
    low_confidence: bool = False
    language: str
    debug: dict | None = None


class FeedbackRequest(BaseModel):
    ticket_text: str
    helpful: bool
    comment: str | None = None
    model: str | None = None
