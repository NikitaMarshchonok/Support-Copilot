from __future__ import annotations

import hashlib
import json
import random
import re
from typing import Any

from openai import OpenAI
from pydantic import BaseModel, Field
import requests

from .settings import settings
from .schemas import SuggestReplyResponse, Citation
from .vector_store import get_qdrant, search


# --------- Structured output schema (Pydantic) ----------
class CopilotOut(BaseModel):
    draft_reply: str = Field(description="Agent-ready reply draft.")
    citations: list[dict[str, Any]] = Field(description="List of citations referencing ONLY provided sources.")
    next_actions: list[str] = Field(description="Concrete next steps for the agent.")
    clarifying_questions: list[str] = Field(default_factory=list, description="Questions to ask if info missing.")
    language: str = Field(description="Language of the draft reply: en|ru|he")


MOCK_EMBEDDING_DIM = 1536


def _has_openai_key() -> bool:
    key = (settings.openai_api_key or "").strip()
    return bool(key) and key != "YOUR_KEY_HERE"


def _provider() -> str:
    return (settings.llm_provider or "openai").strip().lower()


def get_active_provider_model() -> tuple[str, str | None]:
    provider = _provider()
    use_openai = provider == "openai" and _has_openai_key()
    use_ollama = provider == "ollama" and bool(settings.ollama_url)
    if use_openai:
        return "openai", settings.openai_model
    if use_ollama:
        return "ollama", settings.ollama_model
    return "mock", None


def _mock_embedding(text: str, dim: int = MOCK_EMBEDDING_DIM) -> list[float]:
    seed = int.from_bytes(hashlib.sha256(text.encode("utf-8")).digest()[:8], "big")
    rng = random.Random(seed)
    return [rng.uniform(-1.0, 1.0) for _ in range(dim)]


def _ollama_embedding(text: str) -> list[float]:
    r = requests.post(
        f"{settings.ollama_url}/api/embeddings",
        json={"model": settings.ollama_embedding_model, "prompt": text},
        timeout=60,
    )
    r.raise_for_status()
    data = r.json()
    return list(data.get("embedding") or [])


def _ollama_generate(prompt: str) -> str:
    r = requests.post(
        f"{settings.ollama_url}/api/generate",
        json={"model": settings.ollama_model, "prompt": prompt, "stream": False},
        timeout=120,
    )
    r.raise_for_status()
    data = r.json()
    return str(data.get("response") or "").strip()


def _extract_json(text: str) -> dict[str, Any] | None:
    if not text:
        return None
    start = text.find("{")
    end = text.rfind("}")
    if start == -1 or end == -1 or end <= start:
        return None
    try:
        return json.loads(text[start : end + 1])
    except json.JSONDecodeError:
        return None


def _normalize_actions(items: list[Any]) -> list[str]:
    out: list[str] = []
    for it in items:
        if isinstance(it, dict):
            action = str(it.get("action") or it.get("title") or "").strip()
            desc = str(it.get("description") or "").strip()
            if action and desc:
                out.append(f"{action} — {desc}")
            elif action:
                out.append(action)
            elif desc:
                out.append(desc)
        else:
            s = str(it).strip()
            if s:
                out.append(s)
    return out


def _normalize_draft(value: Any) -> str:
    if isinstance(value, dict):
        for key in ("draft_reply", "text", "reply", "answer"):
            if key in value and str(value[key]).strip():
                return str(value[key]).strip()
        return ""
    if isinstance(value, list):
        return " ".join(str(v).strip() for v in value if str(v).strip())
    return str(value).strip()


def _clean_snippet(text: str, limit: int = 260) -> str:
    lines = [line.strip() for line in text.splitlines() if line.strip()]
    cleaned: list[str] = []
    for line in lines:
        line = re.sub(r"^#{1,6}\s*", "", line)
        line = re.sub(r"^[-*]\s+", "", line)
        line = re.sub(r"^\d+\.\s+", "", line)
        cleaned.append(line)
    joined = " ".join(cleaned).strip()
    if len(joined) > limit:
        return joined[:limit] + "…"
    return joined


def _confidence_from_score(score: float) -> float:
    """
    Qdrant cosine score often in [0..1] range.
    Map: 0.20 -> 0.0, 0.60 -> 1.0 (clamped)
    """
    return float(max(0.0, min(1.0, (score - 0.20) / 0.40)))


def _build_sources_block(hits: list[dict[str, Any]]) -> str:
    lines = []
    for i, h in enumerate(hits, start=1):
        title = h.get("title") or f"Source {i}"
        url = h.get("url") or ""
        text = (h.get("text") or "").strip()
        snippet = (text[:260] + "…") if len(text) > 260 else text
        lines.append(
            f"[S{i}] title: {title}\n"
            f"[S{i}] url: {url}\n"
            f"[S{i}] snippet: {snippet}\n"
            f"[S{i}] full_text:\n{text}\n"
        )
    return "\n".join(lines)


def generate_suggested_reply(ticket_text: str, language: str = "en", category: str | None = None) -> SuggestReplyResponse:
    ticket_text = (ticket_text or "").strip()
    if len(ticket_text) < 3:
        return SuggestReplyResponse(
            draft_reply="Please provide more details.",
            citations=[],
            next_actions=["Ask the user for more context"],
            clarifying_questions=["What exactly happened? Provide booking ID, dates, and what you want to change."],
            confidence=0.0,
            language=language,
        )

    # Clients
    qdrant = get_qdrant(settings.qdrant_url)
    provider = _provider()
    use_openai = provider == "openai" and _has_openai_key()
    use_ollama = provider == "ollama" and bool(settings.ollama_url)
    llm = OpenAI(api_key=settings.openai_api_key) if use_openai else None

    # 1) Embed query
    if use_openai and llm:
        emb = llm.embeddings.create(
            model=settings.embedding_model,
            input=[ticket_text.replace("\n", " ")],
        ).data[0].embedding
    elif use_ollama:
        try:
            emb = _ollama_embedding(ticket_text.replace("\n", " "))
        except requests.RequestException:
            emb = _mock_embedding(ticket_text)
    else:
        emb = _mock_embedding(ticket_text)

    # 2) Retrieve
    raw_hits = search(qdrant, settings.qdrant_collection, emb, limit=settings.top_k)
    if not raw_hits:
        return SuggestReplyResponse(
            draft_reply="I couldn’t find a relevant policy article. Please clarify the issue and share booking details.",
            citations=[],
            next_actions=["Ask clarifying questions", "Escalate if urgent"],
            clarifying_questions=["What is the booking ID?", "What dates are involved?", "What outcome do you want?"],
            confidence=0.0,
            language=language,
        )

    top_score = raw_hits[0].score
    conf = _confidence_from_score(top_score)

    # Guardrail: if score too low -> no LLM call
    if top_score < settings.min_score:
        return SuggestReplyResponse(
            draft_reply=(
                "I’m not confident which policy applies. Please уточните детали (booking ID, даты, что именно нужно)."
                if language == "ru"
                else "I’m not confident which policy applies. Please share booking ID, dates, and what you want to change."
            ),
            citations=[],
            next_actions=["Ask clarifying questions", "If needed, escalate to L2"],
            clarifying_questions=["Booking ID?", "Exact dates?", "Cancel/change/refund?"],
            confidence=conf,
            language=language,
            debug={"top_score": top_score, "min_score": settings.min_score},
        )

    hits_payloads = [h.payload for h in raw_hits]
    citations: list[Citation] = []
    for p in hits_payloads[:4]:
        text = (p.get("text") or "").strip()
        snippet = _clean_snippet(text)
        citations.append(
            Citation(
                title=str(p.get("title") or "Policy")[:200],
                url=(str(p.get("url")) if p.get("url") else None),
                snippet=snippet[:500],
            )
        )

    # 3) Build prompt with sources
    sources_block = _build_sources_block(hits_payloads)

    if not use_openai:
        if use_ollama:
            prompt = (
                "You are a Customer Support Copilot for a travel booking platform.\n"
                "RULES:\n"
                "1) Use ONLY the provided SOURCES to answer.\n"
                "2) If sources do not contain the answer, ask clarifying questions.\n"
                "3) Keep the tone helpful, calm, professional.\n"
                "4) Return JSON with keys: draft_reply, next_actions, clarifying_questions, language.\n\n"
                f"TICKET:\n{ticket_text}\n\n"
                f"LANGUAGE: {language}\n"
                f"CATEGORY: {category or ''}\n\n"
                f"SOURCES:\n{sources_block}\n"
            )
            try:
                raw = _ollama_generate(prompt)
                parsed = _extract_json(raw) or {}
                draft = _normalize_draft(parsed.get("draft_reply") or parsed.get("text") or parsed)
                next_actions = _normalize_actions(parsed.get("next_actions") or [])
                clarifying = _normalize_actions(parsed.get("clarifying_questions") or [])
                lang = str(parsed.get("language") or language)
            except requests.RequestException:
                draft = ""
                next_actions = []
                clarifying = []
                lang = language
        else:
            draft = ""
            next_actions = []
            clarifying = []
            lang = language

        if not draft:
            draft = (
                "По нашим правилам ниже приведены релевантные источники. Я подготовил черновик и список шагов."
                if language == "ru"
                else "Based on the policy sources below, I prepared a draft reply and suggested next steps."
            )
        if not next_actions:
            next_actions = [
                "Confirm booking ID and dates",
                "Verify rate conditions and applicable policy",
                "Escalate if exception handling is required",
            ]
        if not clarifying:
            clarifying = ["Booking ID?", "Exact dates?", "Desired outcome?"]

        return SuggestReplyResponse(
            draft_reply=draft,
            citations=citations,
            next_actions=_normalize_actions(next_actions)[:8],
            clarifying_questions=_normalize_actions(clarifying)[:6],
            confidence=conf,
            language=lang,
            debug={
                "top_score": top_score,
                "mode": "ollama" if use_ollama else "mock",
                "model": settings.ollama_model if use_ollama else None,
            },
        )

    sys = (
        "You are a Customer Support Copilot for a travel booking platform.\n"
        "RULES:\n"
        "1) Use ONLY the provided SOURCES to answer.\n"
        "2) If sources do not contain the answer, ask clarifying questions.\n"
        "3) Provide citations as a list of objects with: title, url, snippet.\n"
        "4) Keep the tone helpful, calm, professional.\n"
        "5) Output must match the JSON schema.\n"
    )

    user = (
        f"TICKET:\n{ticket_text}\n\n"
        f"LANGUAGE: {language}\n"
        f"CATEGORY: {category or ''}\n\n"
        f"SOURCES:\n{sources_block}\n\n"
        "TASK:\n"
        "Create:\n"
        "- draft_reply: a ready-to-send reply\n"
        "- next_actions: 3-6 bullet actions for the agent\n"
        "- clarifying_questions: if needed\n"
        "- citations: choose 1-4 most relevant sources (use their snippets)\n"
        "IMPORTANT: citations must come from SOURCES only.\n"
    )

    # 4) Structured output via Responses API (Pydantic parsing)
    parsed = llm.responses.parse(
        model=settings.openai_model,
        input=[
            {"role": "system", "content": sys},
            {"role": "user", "content": user},
        ],
        text_format=CopilotOut,
        store=settings.openai_store,
    ).output_parsed

    # 5) Normalize citations to our API schema
    citations: list[Citation] = []
    for c in (parsed.citations or [])[:4]:
        citations.append(
            Citation(
                title=str(c.get("title", ""))[:200] or "Policy",
                url=(str(c.get("url")) if c.get("url") else None),
                snippet=str(c.get("snippet", ""))[:500],
            )
        )

    # Hard guardrail: if model returned no citations, downgrade confidence
    if not citations:
        conf = min(conf, 0.35)

    return SuggestReplyResponse(
        draft_reply=parsed.draft_reply.strip(),
        citations=citations,
        next_actions=[a.strip() for a in parsed.next_actions if str(a).strip()][:8],
        clarifying_questions=[q.strip() for q in parsed.clarifying_questions if str(q).strip()][:6],
        confidence=conf,
        language=parsed.language or language,
        debug={"top_score": top_score, "mode": "openai", "model": settings.openai_model},
    )
