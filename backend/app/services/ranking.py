import math
from dataclasses import dataclass
from datetime import datetime

from app.services.weights import RankingWeights

BASELINE_WEIGHTS = RankingWeights(alpha=1.0, beta=0.0, gamma=0.0)


@dataclass
class Candidate:
    chunk_id: str
    paper_id: str
    similarity: float
    published_at: datetime


@dataclass
class ScoredChunk:
    chunk_id: str
    paper_id: str
    similarity: float
    semantic: float
    recency: float
    feedback: float
    final: float


def recency_score(published_at: datetime, now: datetime, half_life_days: float) -> float:
    age_days = max(0.0, (now - published_at).total_seconds() / 86400)
    return math.pow(0.5, age_days / half_life_days)


def min_max(values: list[float]) -> list[float]:
    if not values:
        return []
    low, high = min(values), max(values)
    if high - low < 1e-9:
        return [1.0 for _ in values]
    return [(value - low) / (high - low) for value in values]


def score_candidates(
    candidates: list[Candidate],
    weights: RankingWeights,
    feedback: dict[str, float],
    now: datetime,
    half_life_days: float,
) -> list[ScoredChunk]:
    semantic = min_max([c.similarity for c in candidates])
    scored = []
    for candidate, semantic_score in zip(candidates, semantic):
        recency = recency_score(candidate.published_at, now, half_life_days)
        feedback_score = feedback.get(candidate.chunk_id, 0.5)
        final = weights.alpha * semantic_score + weights.beta * recency + weights.gamma * feedback_score
        scored.append(
            ScoredChunk(
                chunk_id=candidate.chunk_id,
                paper_id=candidate.paper_id,
                similarity=candidate.similarity,
                semantic=semantic_score,
                recency=recency,
                feedback=feedback_score,
                final=final,
            )
        )
    return scored


def select_top(scored: list[ScoredChunk], top_k: int, max_per_paper: int) -> list[ScoredChunk]:
    ordered = sorted(scored, key=lambda s: (-s.final, -s.similarity, s.chunk_id))
    selected: list[ScoredChunk] = []
    per_paper: dict[str, int] = {}
    for item in ordered:
        if per_paper.get(item.paper_id, 0) >= max_per_paper:
            continue
        selected.append(item)
        per_paper[item.paper_id] = per_paper.get(item.paper_id, 0) + 1
        if len(selected) == top_k:
            break
    return selected
