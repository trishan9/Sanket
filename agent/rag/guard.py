from __future__ import annotations

import re
from dataclasses import dataclass

INJECTION_PATTERNS: tuple[re.Pattern[str], ...] = (
    re.compile(r"ignore (all |any |previous |prior )*instructions", re.IGNORECASE),
    re.compile(r"disregard (the |your |all )*(system|previous) prompt", re.IGNORECASE),
    re.compile(r"you (are|must) now (act|behave|respond) as", re.IGNORECASE),
    re.compile(r"\bsystem\s*:\s*", re.IGNORECASE),
    re.compile(r"\bnew instructions\b", re.IGNORECASE),
    re.compile(r"reveal (your|the) (system prompt|instructions)", re.IGNORECASE),
    re.compile(r"do not (mention|tell|report) (this|that) to", re.IGNORECASE),
)


@dataclass(frozen=True)
class DroppedChunk:
    chunk_id: str
    reason: str


def suspicious_reason(text: str) -> str | None:
    for pattern in INJECTION_PATTERNS:
        if pattern.search(text):
            return f"matched injection pattern: {pattern.pattern}"
    return None


def filter_texts(
    ids: list[str], texts: list[str]
) -> tuple[list[int], list[DroppedChunk]]:
    kept_indices: list[int] = []
    dropped: list[DroppedChunk] = []
    for index, (chunk_id, text) in enumerate(zip(ids, texts, strict=True)):
        reason = suspicious_reason(text)
        if reason is None:
            kept_indices.append(index)
        else:
            dropped.append(DroppedChunk(chunk_id=chunk_id, reason=reason))
    return kept_indices, dropped
