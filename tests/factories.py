from datetime import datetime, timezone

from app.models import Chunk, Citation, Evaluation, Paper, QueryRecord, RetrievedChunk


def make_paper(session, paper_id="2401.00001", chunk_texts=("Intro text.", "Method text.")):
    paper = Paper(
        id=paper_id,
        version="v1",
        title=f"Paper {paper_id}",
        authors=["A. Author", "B. Author"],
        abstract="An abstract.",
        categories=["cs.LG"],
        primary_category="cs.LG",
        published_at=datetime(2024, 1, 2, tzinfo=timezone.utc),
        abs_url=f"https://arxiv.org/abs/{paper_id}",
        pdf_url=f"https://arxiv.org/pdf/{paper_id}",
        text_status="extracted",
    )
    paper.chunks = [
        Chunk(
            id=Chunk.make_id(paper_id, index),
            chunk_index=index,
            section="Introduction" if index == 0 else "Method",
            page=index + 1,
            text=text,
            source="pdf",
        )
        for index, text in enumerate(chunk_texts)
    ]
    session.add(paper)
    session.commit()
    return paper


def make_query(session, paper, mode="proposed", status="completed", scores=None, total_ms=1000.0, cited=(0,)):
    record = QueryRecord(
        text="What is attention?",
        mode=mode,
        status=status,
        answer="Attention weighs tokens [1]." if status == "completed" else None,
        alpha=0.7,
        beta=0.15,
        gamma=0.15,
        retrieval_ms=100.0,
        generation_ms=800.0,
        evaluation_ms=100.0,
        total_ms=total_ms,
    )
    record.retrieved = [
        RetrievedChunk(
            chunk_id=chunk.id,
            rank=rank,
            similarity=0.9 - rank * 0.1,
            semantic_score=0.9 - rank * 0.1,
            recency_score=0.5,
            feedback_score=0.5,
            final_score=0.8 - rank * 0.1,
        )
        for rank, chunk in enumerate(paper.chunks, start=1)
    ]
    record.citations = [
        Citation(marker=marker, chunk_id=paper.chunks[index].id, claim="Attention weighs tokens.")
        for marker, index in enumerate(cited, start=1)
    ]
    if scores is not None:
        record.evaluation = Evaluation(
            **scores,
            overall=sum(scores.values()) / len(scores),
            reasoning={name: "fixture" for name in scores},
            evaluator_model="test",
        )
    session.add(record)
    session.commit()
    return record


def uniform_scores(value):
    return {
        "retrieval_precision": value,
        "retrieval_relevance": value,
        "groundedness": value,
        "citation_accuracy": value,
        "answer_relevance": value,
        "evidence_coverage": value,
    }
