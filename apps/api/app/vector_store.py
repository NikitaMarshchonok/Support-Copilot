from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from qdrant_client import QdrantClient
from qdrant_client.http import models as qm


@dataclass
class SearchHit:
    score: float
    payload: dict[str, Any]


def get_qdrant(url: str) -> QdrantClient:
    return QdrantClient(url=url)


def ensure_collection(client: QdrantClient, collection: str, vector_size: int) -> None:
    existing = [c.name for c in client.get_collections().collections]
    if collection in existing:
        return
    client.create_collection(
        collection_name=collection,
        vectors_config=qm.VectorParams(size=vector_size, distance=qm.Distance.COSINE),
    )


def search(client: QdrantClient, collection: str, query_vector: list[float], limit: int) -> list[SearchHit]:
    results = client.search(
        collection_name=collection,
        query_vector=query_vector,
        limit=limit,
        with_payload=True,
    )
    hits: list[SearchHit] = []
    for r in results:
        hits.append(SearchHit(score=float(r.score), payload=dict(r.payload or {})))
    return hits
