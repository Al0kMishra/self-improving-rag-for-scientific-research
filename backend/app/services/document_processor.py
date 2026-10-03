import logging
from dataclasses import dataclass

from sqlalchemy.orm import Session

from app.core.config import Settings
from app.models import Chunk, Paper
from app.services.chunking import ChunkDraft, chunk_blocks
from app.services.pdf_extractor import PdfExtractionError, TextBlock, extract_blocks
from app.services.pdf_fetcher import PdfFetcher, PdfFetchError

logger = logging.getLogger(__name__)


@dataclass
class ProcessingReport:
    processed: list[str]
    full_text: list[str]
    abstract_only: list[str]
    skipped: list[str]


class DocumentProcessor:
    def __init__(self, settings: Settings, fetcher: PdfFetcher | None = None):
        self.settings = settings
        self.fetcher = fetcher or PdfFetcher(settings)

    def needs_processing(self, paper: Paper, want_full_text: bool) -> bool:
        if paper.text_status == "pending":
            return True
        return want_full_text and paper.text_status == "abstract_only" and paper.pdf_error is None

    def _full_text_drafts(self, paper: Paper) -> list[ChunkDraft]:
        path = self.fetcher.fetch(paper.id, paper.version, paper.pdf_url)
        blocks = [
            block
            for block in extract_blocks(path, self.settings.max_pdf_pages)
            if not (block.section or "").lower().endswith("abstract")
        ]
        if sum(len(block.text) for block in blocks) < self.settings.min_extracted_chars:
            raise PdfExtractionError("too little text extracted, likely a scanned or image-only PDF")
        return chunk_blocks(blocks, self.settings.chunk_size_chars, self.settings.chunk_overlap_chars)

    def _abstract_drafts(self, paper: Paper) -> list[ChunkDraft]:
        block = TextBlock(page=None, section="Abstract", text=paper.abstract)
        return chunk_blocks([block], self.settings.chunk_size_chars, self.settings.chunk_overlap_chars)

    def process(self, session: Session, paper: Paper, want_full_text: bool) -> bool:
        abstract = self._abstract_drafts(paper)
        body: list[ChunkDraft] = []
        paper.pdf_error = None
        if want_full_text and paper.pdf_url:
            try:
                body = self._full_text_drafts(paper)
            except (PdfFetchError, PdfExtractionError) as exc:
                paper.pdf_error = str(exc)[:500]
                logger.warning("full text unavailable for %s: %s", paper.id, exc)
        elif want_full_text:
            paper.pdf_error = "no PDF link"

        paper.chunks.clear()
        paper.indexed_model = None
        session.flush()
        for index, draft in enumerate(abstract + body):
            paper.chunks.append(
                Chunk(
                    id=Chunk.make_id(paper.id, index),
                    chunk_index=index,
                    section=draft.section,
                    page=draft.page,
                    text=draft.text,
                    source="abstract" if index < len(abstract) else "pdf",
                )
            )
        paper.text_status = "extracted" if body else "abstract_only"
        session.commit()
        return bool(body)

    def process_papers(self, session: Session, papers: list[Paper]) -> ProcessingReport:
        report = ProcessingReport([], [], [], [])
        for position, paper in enumerate(papers):
            want_full_text = position < self.settings.pdf_max_papers_per_query
            if not self.needs_processing(paper, want_full_text):
                report.skipped.append(paper.id)
                continue
            got_full_text = self.process(session, paper, want_full_text)
            report.processed.append(paper.id)
            (report.full_text if got_full_text else report.abstract_only).append(paper.id)
        return report
