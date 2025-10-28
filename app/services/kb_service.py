from __future__ import annotations

import asyncio
import logging
from typing import Any, Optional, Sequence

from fastapi import HTTPException
from qdrant_client import AsyncQdrantClient
from qdrant_client.http import models as qmodels
from sqlalchemy.orm import Session

from app.core.config import settings
from app.db.models import KBEntry
from app.db.session import SessionLocal
from app.services.embedding_service import EmbeddingService, RerankService
from app.services.trip_service import get_trip

logger = logging.getLogger(__name__)


class QdrantService:
    def __init__(self) -> None:
        if not settings.QDRANT_URL:
            raise RuntimeError("QDRANT_URL not configured")
        self._client = AsyncQdrantClient(url=settings.QDRANT_URL, api_key=settings.QDRANT_API_KEY)
        self._collection = settings.QDRANT_COLLECTION_NAME
        self._lock = asyncio.Lock()

    async def ensure_collection(self) -> bool:
        async with self._lock:
            try:
                await self._client.get_collection(self._collection)
                return True
            except Exception:
                pass
            try:
                await self._client.recreate_collection(
                    collection_name=self._collection,
                    vectors_config=qmodels.VectorParams(
                        size=settings.VECTOR_DIM,
                        distance=qmodels.Distance.COSINE
                        if settings.VECTOR_DISTANCE.lower() == "cosine"
                        else qmodels.Distance.DOT,
                    ),
                )
                return True
            except Exception:
                logger.exception("qdrant_collection_init_failed")
                return False

    async def upsert_points(
        self,
        *,
        ids: list[int],
        vectors: list[list[float]],
        payloads: list[dict],
    ) -> None:
        if not vectors:
            return
        points: list[qmodels.PointStruct] = []
        for pid, vec, payload in zip(ids, vectors, payloads):
            if not vec:
                continue
            points.append(qmodels.PointStruct(id=int(pid), vector=vec, payload=payload))
        if not points:
            return
        await self._client.upsert(collection_name=self._collection, points=points)

    async def delete_point(self, point_id: int) -> None:
        selector = qmodels.PointIdsList(points=[point_id])
        await self._client.delete(collection_name=self._collection, points_selector=selector)

    async def search(
        self,
        vector: list[float],
        *,
        top_k: int,
        filter_: Optional[qmodels.Filter] = None,
    ) -> list[qmodels.ScoredPoint]:
        if not vector:
            return []
        return await self._client.search(
            collection_name=self._collection,
            query_vector=vector,
            limit=top_k,
            query_filter=filter_,
        )


_qdrant_instance: QdrantService | None = None
_qdrant_lock = asyncio.Lock()


async def get_qdrant_service() -> QdrantService | None:
    global _qdrant_instance
    if _qdrant_instance is not None:
        return _qdrant_instance
    if not settings.QDRANT_URL:
        return None
    async with _qdrant_lock:
        if _qdrant_instance is None:
            _qdrant_instance = QdrantService()
            await _qdrant_instance.ensure_collection()
        return _qdrant_instance


def _ensure_trip_ownership(db: Session, trip_id: int, user_id: int) -> None:
    trip = get_trip(db, trip_id, user_id)
    if trip is None:
        raise HTTPException(status_code=404, detail="trip_not_found")


def create_kb_entry(
    db: Session,
    *,
    trip_id: int,
    user_id: int,
    source: Optional[str],
    title: Optional[str],
    content: Optional[str],
    meta: Optional[dict] = None,
) -> KBEntry:
    _ensure_trip_ownership(db, trip_id, user_id)
    entry = KBEntry(
        trip_id=trip_id,
        source=source,
        title=title,
        content=content,
        meta=meta or {},
    )
    db.add(entry)
    db.commit()
    db.refresh(entry)
    return entry


def get_kb_entries(
    db: Session,
    *,
    trip_id: int,
    user_id: int,
    q: Optional[str] = None,
    source: Optional[str] = None,
    limit: int = 20,
    offset: int = 0,
) -> Sequence[KBEntry]:
    _ensure_trip_ownership(db, trip_id, user_id)
    qset = db.query(KBEntry).filter(KBEntry.trip_id == trip_id)
    if source:
        qset = qset.filter(KBEntry.source == source)
    if q:
        like = f"%{q}%"
        qset = qset.filter((KBEntry.title.ilike(like)) | (KBEntry.content.ilike(like)))
    return (
        qset.order_by(KBEntry.id.desc())
        .offset(offset)
        .limit(limit)
        .all()
    )


def get_kb_entry(db: Session, *, entry_id: int, trip_id: int, user_id: int) -> KBEntry:
    _ensure_trip_ownership(db, trip_id, user_id)
    entry = db.query(KBEntry).filter(KBEntry.id == entry_id, KBEntry.trip_id == trip_id).first()
    if not entry:
        raise HTTPException(status_code=404, detail="kb_entry_not_found")
    return entry


def update_kb_entry(
    db: Session,
    *,
    entry_id: int,
    trip_id: int,
    user_id: int,
    source: Optional[str] = None,
    title: Optional[str] = None,
    content: Optional[str] = None,
    meta: Optional[dict] = None,
) -> KBEntry:
    entry = get_kb_entry(db, entry_id=entry_id, trip_id=trip_id, user_id=user_id)
    if source is not None:
        entry.source = source
    if title is not None:
        entry.title = title
    if content is not None:
        entry.content = content
    if meta is not None:
        entry.meta = meta
    db.add(entry)
    db.commit()
    db.refresh(entry)
    return entry


def delete_kb_entry(db: Session, *, entry_id: int, trip_id: int, user_id: int) -> None:
    entry = get_kb_entry(db, entry_id=entry_id, trip_id=trip_id, user_id=user_id)
    db.delete(entry)
    db.commit()


async def process_entry_embedding(entry_id: int) -> None:
    if not settings.ENABLE_EMBEDDING:
        return
    try:
        embedding_service = EmbeddingService()
    except RuntimeError:
        logger.warning("embedding_service_disabled")
        return

    qdrant = await get_qdrant_service()
    session = SessionLocal()
    try:
        entry = session.query(KBEntry).filter(KBEntry.id == entry_id).first()
        if not entry:
            return
        doc_text = "\n\n".join([t for t in [entry.title or "", entry.content or ""] if t])
        vector = await embedding_service.embed(doc_text)
        entry.embedding = vector
        session.add(entry)
        session.commit()
        if qdrant and vector:
            await qdrant.upsert_points(
                ids=[entry.id],
                vectors=[vector],
                payloads=[{
                    "entry_id": entry.id,
                    "trip_id": entry.trip_id,
                    "title": entry.title,
                    "source": entry.source,
                    "content": entry.content,
                }],
            )
    except Exception:
        logger.exception("kb_embedding_process_failed", extra={"entry_id": entry_id})
    finally:
        session.close()


async def remove_entry_vector(entry_id: int) -> None:
    qdrant = await get_qdrant_service()
    if qdrant is None:
        return
    try:
        await qdrant.delete_point(entry_id)
    except Exception:
        logger.exception("qdrant_delete_failed", extra={"entry_id": entry_id})


async def rerank_results(query: str, results: list[dict[str, Any]]) -> list[dict[str, Any]]:
    if not results:
        return results
    if not settings.OLLAMA_RERANK_ENABLED:
        return results
    try:
        reranker = RerankService()
    except RuntimeError:
        return results
    documents: list[str] = []
    for item in results:
        payload = item.get("payload")
        content = ""
        if isinstance(payload, dict):
            raw_content = payload.get("content")
            if raw_content is not None:
                content = str(raw_content)
        documents.append(content)
    scores = await reranker.rerank(query, documents)
    score_map = {res.index: res.score for res in scores}
    # 回退：若 reranker 无法产出分数，则使用嵌入相似度进行重排
    if not score_map:
        try:
            emb = EmbeddingService()
            qv = await emb.embed(query)
            dvs = await emb.embed_batch(documents)
            def _cos(a: list[float], b: list[float]) -> float:
                if not a or not b or len(a) != len(b):
                    return 0.0
                s = sum(x*y for x, y in zip(a, b))
                na = sum(x*x for x in a) ** 0.5
                nb = sum(y*y for y in b) ** 0.5
                if na == 0 or nb == 0:
                    return 0.0
                return s / (na * nb)
            score_map = {i: _cos(qv, vec) for i, vec in enumerate(dvs)}
        except Exception:
            score_map = {}
    if not score_map:
        return results
    indexed = list(enumerate(results))
    def _score(pair: tuple[int, dict[str, Any]]) -> float:
        fallback = pair[1].get("score", 0.0)
        if isinstance(fallback, (int, float)):
            fallback_score = float(fallback)
        else:
            try:
                fallback_score = float(fallback)
            except (TypeError, ValueError):
                fallback_score = 0.0
        return score_map.get(pair[0], fallback_score)

    ranked = sorted(indexed, key=_score, reverse=True)
    return [item for _, item in ranked]


__all__ = [
    "QdrantService",
    "get_qdrant_service",
    "create_kb_entry",
    "get_kb_entries",
    "get_kb_entry",
    "update_kb_entry",
    "delete_kb_entry",
    "process_entry_embedding",
    "remove_entry_vector",
    "rerank_results",
]
