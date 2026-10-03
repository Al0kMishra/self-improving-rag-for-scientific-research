from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.api.deps import get_db, get_services
from app.models import Paper
from app.schemas.paper import ChunkOut, PaperDetail
from app.services.container import Services

router = APIRouter(prefix="/papers", tags=["papers"])


def paper_detail(paper: Paper, include_chunks: bool) -> PaperDetail:
    detail = PaperDetail.model_validate(
        {**{c.name: getattr(paper, c.name) for c in Paper.__table__.columns}, "chunk_count": len(paper.chunks)}
    )
    if include_chunks:
        detail.chunks = [ChunkOut.model_validate(chunk) for chunk in paper.chunks]
    return detail


def load_paper(db: Session, paper_id: str) -> Paper:
    paper = db.get(Paper, paper_id)
    if paper is None:
        raise HTTPException(status_code=404, detail=f"paper {paper_id} not found")
    return paper


@router.post("/{paper_id:path}/process", response_model=PaperDetail)
def process_paper(
    paper_id: str,
    db: Session = Depends(get_db),
    services: Services = Depends(get_services),
) -> PaperDetail:
    paper = load_paper(db, paper_id)
    services.document_processor.process(db, paper, want_full_text=True)
    return paper_detail(paper, include_chunks=True)


@router.get("/{paper_id:path}", response_model=PaperDetail)
def get_paper(paper_id: str, include_chunks: bool = False, db: Session = Depends(get_db)) -> PaperDetail:
    return paper_detail(load_paper(db, paper_id), include_chunks)
