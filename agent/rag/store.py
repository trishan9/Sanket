from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, date, datetime
from typing import Literal

import chromadb
from sentence_transformers import SentenceTransformer

from core.config import paths

EMBEDDING_MODEL_NAME = "paraphrase-multilingual-MiniLM-L12-v2"
EMBEDDING_DIMENSION = 384
Collection = Literal["science", "events"]
CollectionClaimType = Literal["reported", "official", "analysis", "retracted"]

_model: SentenceTransformer | None = None
_client: chromadb.ClientAPI | None = None


def embedding_model() -> SentenceTransformer:
    global _model
    if _model is None:
        _model = SentenceTransformer(EMBEDDING_MODEL_NAME, device="cpu")
    return _model


def client() -> chromadb.ClientAPI:
    global _client
    if _client is None:
        paths.chroma.mkdir(parents=True, exist_ok=True)
        _client = chromadb.PersistentClient(path=str(paths.chroma))
    return _client


def get_collection(name: Collection) -> chromadb.Collection:
    return client().get_or_create_collection(name)


@dataclass(frozen=True)
class Chunk:
    id: str
    text: str
    source_org: str
    url: str
    published_at: date
    claim_type: CollectionClaimType
    independence_group: str
    geo: str
    lang: str = "en"


def published_ts(published_at: date) -> int:
    return int(
        datetime(published_at.year, published_at.month, published_at.day, tzinfo=UTC).timestamp()
    )


def embed_texts(texts: list[str]) -> list[list[float]]:
    vectors = embedding_model().encode(texts, show_progress_bar=False)
    return [list(map(float, v)) for v in vectors]


def upsert(collection_name: Collection, chunks: list[Chunk]) -> int:
    if not chunks:
        return 0
    collection = get_collection(collection_name)
    embeddings = embed_texts([c.text for c in chunks])
    collection.upsert(
        ids=[c.id for c in chunks],
        documents=[c.text for c in chunks],
        embeddings=embeddings,
        metadatas=[
            {
                "source_org": c.source_org,
                "url": c.url,
                "published_at": c.published_at.isoformat(),
                "published_ts": published_ts(c.published_at),
                "claim_type": c.claim_type,
                "independence_group": c.independence_group,
                "geo": c.geo,
                "lang": c.lang,
            }
            for c in chunks
        ],
    )
    return len(chunks)
