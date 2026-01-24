from __future__ import annotations

import hashlib
import random
import sys
import uuid
from pathlib import Path

from openai import OpenAI
from qdrant_client.http import models as qm
import requests

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from apps.api.app.settings import settings
from apps.api.app.vector_store import get_qdrant, ensure_collection


def stable_id(text: str) -> str:
    return str(uuid.uuid5(uuid.NAMESPACE_URL, text))


MOCK_EMBEDDING_DIM = 1536


def _has_openai_key() -> bool:
    key = (settings.openai_api_key or "").strip()
    return bool(key) and key != "YOUR_KEY_HERE"


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


def _get_existing_vector_size(client) -> int | None:
    try:
        info = client.get_collection(settings.qdrant_collection)
    except Exception:
        return None
    vectors = getattr(info.config.params, "vectors", None)
    if vectors is None:
        return None
    size = getattr(vectors, "size", None)
    if isinstance(size, int):
        return size
    if isinstance(vectors, dict):
        first = next(iter(vectors.values()), None)
        return getattr(first, "size", None)
    return None


def chunk_text(text: str, chunk_size: int, overlap: int) -> list[str]:
    text = text.replace("\r\n", "\n")
    if len(text) <= chunk_size:
        return [text.strip()]
    chunks = []
    start = 0
    while start < len(text):
        end = min(len(text), start + chunk_size)
        chunk = text[start:end].strip()
        if chunk:
            chunks.append(chunk)
        start = end - overlap
        if start < 0:
            start = 0
        if end == len(text):
            break
    return chunks


def main():
    kb_root = Path("data/kb")
    kb_root.mkdir(parents=True, exist_ok=True)

    # Seed minimal KB if empty
    if not any(kb_root.rglob("*.md")):
        (kb_root / "policies").mkdir(parents=True, exist_ok=True)
        (kb_root / "policies" / "cancellations.md").write_text(
            "# Cancellations (Sample)\n\n"
            "If a guest requests cancellation, verify booking ID, dates, and reason.\n"
            "If the booking is non-refundable, politely explain the policy and offer alternatives if available.\n"
            "If a refund exception applies, escalate to L2 with full context.\n",
            encoding="utf-8",
        )
        (kb_root / "payments.md").write_text(
            "# Payments (Sample)\n\n"
            "Payouts are processed after check-in or according to the partner agreement.\n"
            "For payment disputes, collect transaction ID and screenshots and escalate if needed.\n",
            encoding="utf-8",
        )

    qdrant = get_qdrant(settings.qdrant_url)
    use_openai = _has_openai_key()
    use_ollama = not use_openai and bool(settings.ollama_url)
    llm = OpenAI(api_key=settings.openai_api_key) if use_openai else None

    points = []
    sample_emb_dim = None

    md_files = list(kb_root.rglob("*.md"))
    for path in md_files:
        raw = path.read_text(encoding="utf-8")
        chunks = chunk_text(raw, settings.chunk_size, settings.chunk_overlap)

        for idx, ch in enumerate(chunks):
            if use_openai and llm:
                emb = llm.embeddings.create(
                    model=settings.embedding_model,
                    input=[ch.replace("\n", " ")],
                ).data[0].embedding
            elif use_ollama:
                try:
                    emb = _ollama_embedding(ch.replace("\n", " "))
                except requests.RequestException:
                    emb = _mock_embedding(ch)
            else:
                emb = _mock_embedding(ch)

            if sample_emb_dim is None:
                sample_emb_dim = len(emb)
                existing_size = _get_existing_vector_size(qdrant)
                if existing_size and existing_size != sample_emb_dim:
                    qdrant.delete_collection(collection_name=settings.qdrant_collection)
                ensure_collection(qdrant, settings.qdrant_collection, vector_size=sample_emb_dim)

            payload = {
                "title": path.stem.replace("_", " ").title(),
                "url": None,
                "source_path": str(path),
                "chunk_index": idx,
                "text": ch,
            }

            pid = stable_id(f"{path}:{idx}")
            points.append(qm.PointStruct(id=pid, vector=emb, payload=payload))

    if not points:
        print("No KB files found to ingest.")
        return

    # Upsert in batches
    B = 64
    for i in range(0, len(points), B):
        qdrant.upsert(collection_name=settings.qdrant_collection, points=points[i:i+B])

    print(f"✅ Ingested {len(points)} chunks into collection '{settings.qdrant_collection}'")


if __name__ == "__main__":
    main()
