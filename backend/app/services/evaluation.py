import logging
import time
from dataclasses import dataclass
from statistics import mean
from typing import Literal

from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from app.models import Evaluation, QueryRecord
from app.services.citations import markers_in, split_claims, strip_markers
from app.services.generation import EvidenceItem, format_evidence
from app.services.llm import LLMClient

logger = logging.getLogger(__name__)

SYSTEM_PROMPT = """You are a strict evaluator of a retrieval-augmented research assistant. You receive a \
research question, the numbered evidence excerpts that were retrieved for it, and the assistant's answer \
split into numbered claims with the evidence numbers each claim cites.

Judge only from the text supplied. Do not use outside knowledge to decide whether a claim is true; decide \
whether the cited excerpt states or directly implies it.

1. For every evidence excerpt, rate its relevance to the question itself, regardless of whether the answer \
used it: "relevant" if it contains information that directly helps answer the question, "partial" if it is \
on topic but only tangentially useful, "irrelevant" otherwise.
2. For every claim, say whether it is factual (asserts something about methods, results or findings) or \
not (a transition, a caveat about missing evidence, or a restatement of the question). For every \
citation attached to a claim, judge whether that excerpt "supported" the claim fully, "partial"ly, or \
"unsupported".
3. List the distinct aspects a complete answer to the question must cover (two to five), and for each \
say whether the retrieved evidence, taken together, covers it.
4. Rate how well the answer addresses the question on a 0 to 4 scale: 0 off topic, 1 barely, 2 partly, \
3 mostly, 4 fully and directly.
Give short, specific reasons."""

RELEVANCE = {"relevant": 1.0, "partial": 0.5, "irrelevant": 0.0}
SUPPORT = {"supported": 1.0, "partial": 0.5, "unsupported": 0.0}


class ChunkJudgement(BaseModel):
    evidence: int
    relevance: Literal["relevant", "partial", "irrelevant"]
    reason: str


class CitationVerdict(BaseModel):
    evidence: int
    verdict: Literal["supported", "partial", "unsupported"]
    reason: str


class ClaimJudgement(BaseModel):
    claim: int
    factual: bool
    citations: list[CitationVerdict] = Field(default_factory=list)


class AspectJudgement(BaseModel):
    aspect: str
    covered: bool


class EvaluationJudgement(BaseModel):
    chunks: list[ChunkJudgement]
    claims: list[ClaimJudgement]
    aspects: list[AspectJudgement]
    answer_relevance: int = Field(ge=0, le=4)
    answer_relevance_reason: str
    summary: str


@dataclass
class Claim:
    number: int
    text: str
    citations: list[int]


@dataclass
class Scores:
    retrieval_precision: float
    retrieval_relevance: float
    groundedness: float
    citation_accuracy: float
    answer_relevance: float
    evidence_coverage: float
    chunk_relevance: dict[int, float]
    citation_support: dict[tuple[int, int], tuple[float, str]]
    reasoning: dict[str, str]

    @property
    def overall(self) -> float:
        return mean(
            [
                self.retrieval_precision,
                self.retrieval_relevance,
                self.groundedness,
                self.citation_accuracy,
                self.answer_relevance,
                self.evidence_coverage,
            ]
        )


def answer_claims(answer: str) -> list[Claim]:
    return [
        Claim(number=index + 1, text=strip_markers(text), citations=list(dict.fromkeys(markers_in(text))))
        for index, text in enumerate(split_claims(answer))
    ]


def build_prompt(question: str, evidence: list[EvidenceItem], claims: list[Claim]) -> str:
    claim_lines = "\n".join(
        f"({c.number}) {c.text}  cites: {', '.join(f'[{n}]' for n in c.citations) or 'nothing'}" for c in claims
    )
    return (
        f"Question: {question}\n\nEvidence excerpts:\n\n{format_evidence(evidence)}\n\n"
        f"Answer claims:\n{claim_lines or '(the answer is empty)'}"
    )


def score_judgement(
    judgement: EvaluationJudgement,
    evidence_count: int,
    claims: list[Claim],
    invalid_citations: int,
) -> Scores:
    chunk_relevance = {n: 0.0 for n in range(1, evidence_count + 1)}
    chunk_reasons = []
    for item in judgement.chunks:
        if item.evidence in chunk_relevance:
            chunk_relevance[item.evidence] = RELEVANCE[item.relevance]
            chunk_reasons.append(f"[{item.evidence}] {item.relevance}: {item.reason}")
    relevance_values = list(chunk_relevance.values())

    judged_claims = {c.claim: c for c in judgement.claims}
    citation_support: dict[tuple[int, int], tuple[float, str]] = {}
    claim_scores = []
    for claim in claims:
        verdicts = {v.evidence: v for v in judged_claims[claim.number].citations} if claim.number in judged_claims else {}
        for number in claim.citations:
            verdict = verdicts.get(number)
            citation_support[(claim.number, number)] = (
                (SUPPORT[verdict.verdict], verdict.reason) if verdict else (0.0, "evaluator gave no verdict")
            )
        factual = judged_claims[claim.number].factual if claim.number in judged_claims else True
        if factual:
            supports = [citation_support[(claim.number, n)][0] for n in claim.citations]
            claim_scores.append(max(supports, default=0.0))

    citation_values = [score for score, _ in citation_support.values()] + [0.0] * invalid_citations
    covered = [a.covered for a in judgement.aspects]
    return Scores(
        retrieval_precision=mean(1.0 if v == 1.0 else 0.0 for v in relevance_values) if relevance_values else 0.0,
        retrieval_relevance=mean(relevance_values) if relevance_values else 0.0,
        groundedness=mean(claim_scores) if claim_scores else 1.0,
        citation_accuracy=mean(citation_values) if citation_values else 0.0,
        answer_relevance=judgement.answer_relevance / 4,
        evidence_coverage=sum(covered) / len(covered) if covered else 0.0,
        chunk_relevance=chunk_relevance,
        citation_support=citation_support,
        reasoning={
            "retrieval": " | ".join(chunk_reasons),
            "groundedness": f"{sum(s == 1.0 for s in claim_scores)} of {len(claim_scores)} factual claims fully "
                            f"supported by a cited excerpt",
            "citation_accuracy": f"{len(citation_support)} citations judged, {invalid_citations} pointed at "
                                 f"evidence numbers that do not exist",
            "answer_relevance": judgement.answer_relevance_reason,
            "evidence_coverage": "; ".join(
                f"{a.aspect}: {'covered' if a.covered else 'missing'}" for a in judgement.aspects
            ),
            "summary": judgement.summary,
        },
    )


class SelfEvaluator:
    def __init__(self, llm: LLMClient):
        self.llm = llm

    def evaluate(self, question: str, answer: str, evidence: list[EvidenceItem], invalid_citations: int) -> Scores:
        claims = answer_claims(answer)
        judgement = self.llm.structured(SYSTEM_PROMPT, build_prompt(question, evidence, claims), EvaluationJudgement)
        return score_judgement(judgement, len(evidence), claims, invalid_citations)

    def __call__(self, session: Session, record: QueryRecord, evidence: list[EvidenceItem]) -> None:
        started = time.perf_counter()
        try:
            scores = self.evaluate(record.text, record.answer or "", evidence, len(record.invalid_citations or []))
        except Exception as exc:
            logger.warning("self-evaluation failed for query %s: %s", record.id, exc)
            record.error = f"evaluation failed: {type(exc).__name__}: {exc}"[:2000]
            record.evaluation_ms = (time.perf_counter() - started) * 1000
            return

        number_to_chunk = {item.number: item.chunk_id for item in evidence}
        for retrieved in record.retrieved:
            number = retrieved.rank
            retrieved.judged_relevance = scores.chunk_relevance.get(number)
        claims = answer_claims(record.answer or "")
        claim_index = {c.number - 1: c.number for c in claims}
        for citation in record.citations:
            key = (claim_index.get(citation.claim_index, -1), citation.marker)
            if key in scores.citation_support and number_to_chunk.get(citation.marker) == citation.chunk_id:
                citation.support, citation.verdict_reason = scores.citation_support[key]
        record.evaluation = Evaluation(
            retrieval_precision=scores.retrieval_precision,
            retrieval_relevance=scores.retrieval_relevance,
            groundedness=scores.groundedness,
            citation_accuracy=scores.citation_accuracy,
            answer_relevance=scores.answer_relevance,
            evidence_coverage=scores.evidence_coverage,
            overall=scores.overall,
            reasoning=scores.reasoning,
            evaluator_model=self.llm.model,
        )
        record.evaluation_ms = (time.perf_counter() - started) * 1000
