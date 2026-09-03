from __future__ import annotations

from dataclasses import dataclass
from datetime import date

from agent.rag.guard import DroppedChunk, filter_texts
from agent.rag.store import Collection, embed_texts, get_collection, published_ts


@dataclass(frozen=True)
class RetrievedChunk:
    chunk_id: str
    text: str
    source_org: str
    url: str
    published_at: str
    claim_type: str
    independence_group: str
    distance: float


@dataclass(frozen=True)
class RetrievalResult:
    chunks: tuple[RetrievedChunk, ...]
    dropped: tuple[DroppedChunk, ...]
    rejected_post_cutoff: int


def _rejected_count(collection_name: Collection, cutoff: int) -> int:
    collection = get_collection(collection_name)
    result = collection.get(where={"published_ts": {"$gt": cutoff}})
    return len(result.get("ids") or [])


def retrieve(
    collection_name: Collection, query: str, *, as_of: date, k: int = 5
) -> RetrievalResult:
    cutoff = published_ts(as_of)
    collection = get_collection(collection_name)
    if collection.count() == 0:
        return RetrievalResult(chunks=(), dropped=(), rejected_post_cutoff=0)
    query_embedding = embed_texts([query])[0]
    raw = collection.query(
        query_embeddings=[query_embedding],
        n_results=min(max(k * 3, k), collection.count()),
        where={"published_ts": {"$lte": cutoff}},
    )
    ids = raw["ids"][0]
    docs = raw["documents"][0]
    metas = raw["metadatas"][0]
    dists = raw["distances"][0]
    kept_indices, dropped = filter_texts(list(ids), list(docs))
    chunks = tuple(
        RetrievedChunk(
            chunk_id=ids[i],
            text=docs[i],
            source_org=str(metas[i]["source_org"]),
            url=str(metas[i]["url"]),
            published_at=str(metas[i]["published_at"]),
            claim_type=str(metas[i]["claim_type"]),
            independence_group=str(metas[i]["independence_group"]),
            distance=dists[i],
        )
        for i in kept_indices[:k]
    )
    return RetrievalResult(
        chunks=chunks,
        dropped=tuple(dropped),
        rejected_post_cutoff=_rejected_count(collection_name, cutoff),
    )
