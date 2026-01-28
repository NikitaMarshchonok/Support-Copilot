from __future__ import annotations

import argparse
import json
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Iterable

from openai import OpenAI
import requests

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from apps.api.app.settings import settings
from apps.api.app.vector_store import get_qdrant, search
from apps.api.app.rag import generate_suggested_reply


def _has_openai_key() -> bool:
    key = (settings.openai_api_key or "").strip()
    return bool(key) and key != "YOUR_KEY_HERE"


def _provider() -> str:
    return (settings.llm_provider or "openai").strip().lower()


def _mock_embedding(text: str, dim: int = 1536) -> list[float]:
    import hashlib
    import random

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


def _embed(text: str) -> list[float]:
    provider = _provider()
    use_openai = provider == "openai" and _has_openai_key()
    use_ollama = provider == "ollama" and bool(settings.ollama_url)
    llm = OpenAI(api_key=settings.openai_api_key) if use_openai else None

    if use_openai and llm:
        return llm.embeddings.create(
            model=settings.embedding_model,
            input=[text.replace("\n", " ")],
        ).data[0].embedding
    if use_ollama:
        try:
            return _ollama_embedding(text.replace("\n", " "))
        except requests.RequestException:
            return _mock_embedding(text)
    return _mock_embedding(text)


def _load_cases(path: Path) -> list[dict]:
    rows: list[dict] = []
    if not path.exists():
        return rows
    for line in path.read_text(encoding="utf-8").splitlines():
        if not line.strip():
            continue
        rows.append(json.loads(line))
    return rows


def _normalize(text: str) -> str:
    return (text or "").strip().lower()


def _match_any(text: str, keywords: list[str]) -> bool:
    hay = _normalize(text)
    return any(_normalize(k) in hay for k in keywords if _normalize(k))


def _match_titles(titles: list[str], expected: list[str]) -> bool:
    normalized = [_normalize(t) for t in titles]
    return any(_normalize(e) in t for e in expected for t in normalized if _normalize(e))


def _precision_at_k(hit_titles: list[str], expected: list[str], k: int) -> float:
    if not expected:
        return 1.0
    top = hit_titles[:k]
    return 1.0 if _match_titles(top, expected) else 0.0


def _avg(values: Iterable[float]) -> float:
    values = list(values)
    if not values:
        return 0.0
    return sum(values) / len(values)


def _quality_checklist(resp: Any, case: dict) -> dict[str, bool]:
    checklist = {
        "has_citations": bool(resp.citations),
        "has_actions": bool(resp.next_actions),
        "has_draft": bool(resp.draft_reply.strip()),
        "language_match": (case.get("language") or "en") == (resp.language or "en"),
    }
    if case.get("require_clarifying"):
        checklist["has_clarifying"] = bool(resp.clarifying_questions)
    return checklist


def _evaluate_case(case: dict, no_llm: bool) -> dict[str, Any]:
    ticket_text = case.get("ticket_text", "")
    language = case.get("language") or "en"
    category = case.get("category")
    expected_titles = case.get("expected_citation_titles") or []
    expected_reply = case.get("expected_reply_contains") or []
    expected_actions = case.get("expected_actions_contains") or []
    require_clarifying = bool(case.get("require_clarifying"))

    emb = _embed(ticket_text)
    qdrant = get_qdrant(settings.qdrant_url)
    hits = search(qdrant, settings.qdrant_collection, emb, limit=settings.top_k)
    hit_titles = [str(h.payload.get("title") or "") for h in hits]
    retrieval_hit = _match_titles(hit_titles, expected_titles) if expected_titles else True
    p_at_1 = _precision_at_k(hit_titles, expected_titles, 1)
    p_at_3 = _precision_at_k(hit_titles, expected_titles, 3)
    p_at_5 = _precision_at_k(hit_titles, expected_titles, 5)

    result: dict[str, Any] = {
        "id": case.get("id"),
        "ts": datetime.now(timezone.utc).isoformat(),
        "retrieval_hit": retrieval_hit,
        "retrieval_titles": hit_titles[:4],
        "expected_titles": expected_titles,
        "precision_at_1": p_at_1,
        "precision_at_3": p_at_3,
        "precision_at_5": p_at_5,
    }

    if no_llm:
        result["passed"] = retrieval_hit
        return result

    resp = generate_suggested_reply(ticket_text, language=language, category=category)
    citations = [c.title for c in resp.citations]
    citation_hit = _match_titles(citations, expected_titles) if expected_titles else True
    draft_hit = _match_any(resp.draft_reply, expected_reply) if expected_reply else True
    actions_hit = _match_any(" ".join(resp.next_actions), expected_actions) if expected_actions else True
    clarifying_hit = bool(resp.clarifying_questions) if require_clarifying else True

    quality = _quality_checklist(resp, case)
    result.update(
        {
            "citation_hit": citation_hit,
            "draft_hit": draft_hit,
            "actions_hit": actions_hit,
            "clarifying_hit": clarifying_hit,
            "quality_checklist": quality,
            "confidence": resp.confidence,
            "provider": (resp.debug or {}).get("mode"),
            "model": (resp.debug or {}).get("model"),
        }
    )
    result["passed"] = all([retrieval_hit, citation_hit, draft_hit, actions_hit, clarifying_hit])
    return result


def main() -> int:
    parser = argparse.ArgumentParser(description="Lightweight RAG eval")
    parser.add_argument("--cases", default="data/eval/cases.jsonl")
    parser.add_argument("--output", default="data/eval/results.jsonl")
    parser.add_argument("--no-llm", action="store_true")
    parser.add_argument("--limit", type=int, default=0)
    args = parser.parse_args()

    cases_path = Path(args.cases)
    out_path = Path(args.output)
    out_path.parent.mkdir(parents=True, exist_ok=True)

    cases = _load_cases(cases_path)
    if args.limit:
        cases = cases[: args.limit]
    if not cases:
        print("No eval cases found.")
        return 1

    results: list[dict[str, Any]] = []
    for case in cases:
        results.append(_evaluate_case(case, no_llm=args.no_llm))

    passed = sum(1 for r in results if r.get("passed"))
    total = len(results)
    p1 = _avg(r.get("precision_at_1", 0.0) for r in results)
    p3 = _avg(r.get("precision_at_3", 0.0) for r in results)
    p5 = _avg(r.get("precision_at_5", 0.0) for r in results)
    print(f"✅ Passed {passed}/{total} ({(passed / total) * 100:.1f}%)")
    print(f"Retrieval: P@1={p1:.2f} P@3={p3:.2f} P@5={p5:.2f}")

    with out_path.open("w", encoding="utf-8") as f:
        for r in results:
            f.write(json.dumps(r, ensure_ascii=False) + "\n")

    report = {
        "ts": datetime.now(timezone.utc).isoformat(),
        "total": total,
        "passed": passed,
        "pass_rate": round(passed / total, 3),
        "precision_at_1": round(p1, 3),
        "precision_at_3": round(p3, 3),
        "precision_at_5": round(p5, 3),
        "no_llm": bool(args.no_llm),
    }
    report_path = out_path.with_suffix(".summary.json")
    report_path.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
