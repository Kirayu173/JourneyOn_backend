from __future__ import annotations

from typing import Any, Iterable, List, Optional

from qdrant_client import QdrantClient
from qdrant_client.http import models as qmodels

from app.core.config import settings


_client: Optional[QdrantClient] = None


def get_client() -> Optional[QdrantClient]:
    global _client
    if _client is not None:
        return _client
    if not settings.QDRANT_URL:
        return None
    _client = QdrantClient(url=settings.QDRANT_URL, api_key=settings.QDRANT_API_KEY)
    return _client


def ensure_collection() -> bool:
    client = get_client()
    if client is None:
        return False
    cname = settings.QDRANT_COLLECTION_NAME
    try:
        exists = client.get_collection(cname)
        if exists:
            return True
    except Exception:
        pass
    # Create new collection
    try:
        client.recreate_collection(
            collection_name=cname,
            vectors_config=qmodels.VectorParams(
                size=settings.VECTOR_DIM,
                distance=qmodels.Distance.COSINE if settings.VECTOR_DISTANCE.lower() == "cosine" else qmodels.Distance.DOT,
            ),
        )
        return True
    except Exception:
        return False


def upsert_points(ids: Iterable[int], vectors: Iterable[List[float]], payloads: Iterable[dict[str, Any]]) -> bool:
    client = get_client()
    if client is None:
        return False
    points: List[qmodels.PointStruct] = []
    for pid, vec, pl in zip(ids, vectors, payloads):
        if not vec:
            continue
        points.append(qmodels.PointStruct(id=int(pid), vector=vec, payload=pl))
    if not points:
        return True
    client.upsert(collection_name=settings.QDRANT_COLLECTION_NAME, points=points)
    return True


def search(vector: List[float], top_k: int = 10, filter_: Optional[qmodels.Filter] = None) -> List[qmodels.ScoredPoint]:
    client = get_client()
    if client is None or not vector:
        return []
    return client.search(
        collection_name=settings.QDRANT_COLLECTION_NAME,
        query_vector=vector,
        limit=top_k,
        query_filter=filter_,
    )

