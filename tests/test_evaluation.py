import re

import pytest

from app.services.evaluation import (
    AspectJudgement,
    ChunkJudgement,
    CitationVerdict,
    ClaimJudgement,
    EvaluationJudgement,
    answer_claims,
    build_prompt,
    score_judgement,
)
from app.services.generation import EvidenceItem


def judgement(chunks, claims, aspects, relevance=4):
    return EvaluationJudgement(
        chunks=[ChunkJudgement(evidence=n, relevance=r, reason="r") for n, r in chunks],
        claims=claims,
        aspects=[AspectJudgement(aspect=f"a{i}", covered=c) for i, c in enumerate(aspects)],
        answer_relevance=relevance,
        answer_relevance_reason="direct",
        summary="ok",
    )


def test_answer_claims():
    claims = answer_claims("Drafts propose tokens [1][2]. The evidence does not cover energy use.")
    assert [(c.number, c.citations) for c in claims] == [(1, [1, 2]), (2, [])]
    assert claims[0].text == "Drafts propose tokens ."


def test_scores_are_computed_from_judgements():
    claims = answer_claims("A is true [1]. B is true [2][3]. C is uncited but factual. Caveat sentence here.")
    result = score_judgement(
        judgement(
            chunks=[(1, "relevant"), (2, "partial"), (3, "irrelevant"), (4, "relevant")],
            claims=[
                ClaimJudgement(claim=1, factual=True, citations=[CitationVerdict(evidence=1, verdict="supported", reason="")]),
                ClaimJudgement(claim=2, factual=True, citations=[
                    CitationVerdict(evidence=2, verdict="partial", reason=""),
                    CitationVerdict(evidence=3, verdict="unsupported", reason=""),
                ]),
                ClaimJudgement(claim=3, factual=True),
                ClaimJudgement(claim=4, factual=False),
            ],
            aspects=[True, True, False],
            relevance=3,
        ),
        evidence_count=4,
        claims=claims,
        invalid_citations=1,
    )
    assert result.retrieval_precision == 0.5
    assert result.retrieval_relevance == pytest.approx((1 + 0.5 + 0 + 1) / 4)
    assert result.groundedness == pytest.approx((1 + 0.5 + 0) / 3)
    assert result.citation_accuracy == pytest.approx((1 + 0.5 + 0 + 0) / 4)
    assert result.answer_relevance == 0.75
    assert result.evidence_coverage == pytest.approx(2 / 3)
    assert result.citation_support[(2, 2)] == (0.5, "")
    assert 0 <= result.overall <= 1


def test_missing_judgements_count_against_the_answer():
    claims = answer_claims("A is true [1].")
    result = score_judgement(judgement(chunks=[], claims=[], aspects=[]), 2, claims, 0)
    assert result.retrieval_relevance == 0.0
    assert result.citation_support[(1, 1)][0] == 0.0
    assert result.groundedness == 0.0
    assert result.evidence_coverage == 0.0


def test_no_factual_claims_is_fully_grounded():
    claims = answer_claims("The retrieved evidence does not answer this question.")
    result = score_judgement(
        judgement([(1, "irrelevant")], [ClaimJudgement(claim=1, factual=False)], [False], relevance=1), 1, claims, 0
    )
    assert result.groundedness == 1.0
    assert result.citation_accuracy == 0.0


def test_prompt_lists_claims_with_citations():
    evidence = [EvidenceItem(1, "p#0", "2501.00001", "T", 2025, None, None, "text")]
    prompt = build_prompt("Q?", evidence, answer_claims("A [1]. B."))
    assert "(1) A .  cites: [1]" in prompt
    assert "(2) B.  cites: nothing" in prompt


def judge_everything_supported(prompt):
    evidence_numbers = sorted({int(n) for n in re.findall(r"^\[(\d+)\] ", prompt, re.M)})
    claims = re.findall(r"^\((\d+)\) .*cites: (.*)$", prompt, re.M)
    return {
        "chunks": [{"evidence": n, "relevance": "relevant" if n == 1 else "partial", "reason": "r"}
                   for n in evidence_numbers],
        "claims": [
            {"claim": int(number), "factual": True,
             "citations": [{"evidence": int(c), "verdict": "supported", "reason": "states it"}
                           for c in re.findall(r"\[(\d+)\]", cites)]}
            for number, cites in claims
        ],
        "aspects": [{"aspect": "mechanism", "covered": True}, {"aspect": "speedup", "covered": False}],
        "answer_relevance": 3,
        "answer_relevance_reason": "mostly answers",
        "summary": "fine",
    }
