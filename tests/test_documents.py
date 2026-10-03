from datetime import datetime, timezone

import httpx
import pymupdf
import pytest

from app.core.config import Settings
from app.models import Paper
from app.services.chunking import chunk_blocks, split_long
from app.services.document_processor import DocumentProcessor
from app.services.pdf_extractor import (
    TextBlock,
    clean_text,
    detect_heading,
    extract_blocks,
    heading_title,
    looks_like_bibliography,
)
from app.services.pdf_fetcher import PdfFetcher, PdfFetchError, pdf_filename

PARAGRAPH = (
    "Transformers rely on self attention to model long range dependencies between tokens. "
    "The quadratic cost of attention limits the context length that can be processed efficiently. "
    "Sparse and linear variants reduce this cost while keeping most of the modelling power. "
)


def build_pdf(path, pages):
    document = pymupdf.open()
    for blocks in pages:
        page = document.new_page()
        y = 72
        for text in blocks:
            rect = pymupdf.Rect(72, y, 540, y + 140)
            page.insert_textbox(rect, text, fontsize=10)
            y += 150
    document.save(path)
    return path


@pytest.fixture
def sample_pdf(tmp_path):
    return build_pdf(
        tmp_path / "sample.pdf",
        [
            ["Abstract\nThis abstract text should be skipped by the processor because it duplicates metadata.",
             "1 Introduction\n" + PARAGRAPH, "2 Method\n" + PARAGRAPH],
            ["3 Results\n" + PARAGRAPH * 2, "References\n[1] Vaswani et al. Attention is all you need. 2017."],
        ],
    )


def test_heading_detection():
    assert heading_title("1 Introduction") == "1 Introduction"
    assert heading_title("3.2 Training Details") == "3.2 Training Details"
    assert heading_title("Related Work") == "Related Work"
    assert heading_title("References") == "References"
    assert heading_title("1 We show that attention is useful.") is None
    assert heading_title("Table 2 shows accuracy") is None


def test_detect_heading_handles_split_and_wrapped_lines():
    assert detect_heading(["2.1", "Draft Models"]) == ("2.1 Draft Models", 2)
    assert detect_heading(["3. A taxonomy of meth-", "ods"]) == ("3. A taxonomy of methods", 2)
    assert detect_heading(["1 Introduction", "Large language models are widely used today."]) == (
        "1 Introduction",
        1,
    )
    assert detect_heading(["We study attention in depth across many models and tasks."]) == (None, 0)


def test_bibliography_detection():
    reference = (
        "Chen, C., Borgeaud, S., Irving, G., Lespiau, J.-B., Sifre, L., and Jumper, J. Accelerating large "
        "language model decoding with speculative sampling. arXiv preprint arXiv:2302.01318, 2023. "
        "Leviathan, Y., Kalman, M., and Matias, Y. Fast inference from transformers via speculative decoding. "
        "In International Conference on Machine Learning, pp. 19274-19286. PMLR, 2023."
    )
    assert looks_like_bibliography(reference)
    assert not looks_like_bibliography(PARAGRAPH)
    assert not looks_like_bibliography(
        "Leviathan et al. (2023) introduced speculative decoding, which drafts several tokens with a small "
        "model and verifies them in parallel with the target model, preserving the output distribution."
    )


def test_clean_text_joins_hyphenation():
    assert clean_text("trans-\nformer  models\nwork") == "transformer models work"


def test_extract_blocks_tracks_sections_and_stops_at_references(sample_pdf):
    blocks = extract_blocks(sample_pdf, max_pages=10)
    sections = [b.section for b in blocks]
    assert sections == ["Abstract", "1 Introduction", "2 Method", "3 Results"]
    assert [b.page for b in blocks] == [1, 1, 1, 2]
    assert not any("Vaswani" in b.text for b in blocks)


def test_extract_respects_page_limit(sample_pdf):
    assert {b.page for b in extract_blocks(sample_pdf, max_pages=1)} == {1}


def test_split_long_respects_size():
    pieces = split_long(PARAGRAPH * 5, 300)
    assert all(len(p) <= 300 for p in pieces)
    assert " ".join(pieces).split() == (PARAGRAPH * 5).split()


def test_chunks_never_cross_sections():
    blocks = [
        TextBlock(page=1, section="Intro", text=PARAGRAPH),
        TextBlock(page=2, section="Method", text=PARAGRAPH * 4),
    ]
    chunks = chunk_blocks(blocks, size=400, overlap=120)
    assert chunks[0].section == "Intro" and chunks[0].text == PARAGRAPH.strip()
    method = [c for c in chunks if c.section == "Method"]
    assert len(method) >= 3
    assert all(len(c.text) <= 400 + 120 for c in chunks)
    first_sentence_of_next = method[1].text.split(". ")[0]
    assert first_sentence_of_next in method[0].text


def test_chunk_without_overlap_has_no_duplicates():
    chunks = chunk_blocks([TextBlock(page=1, section=None, text=PARAGRAPH * 4)], size=300, overlap=0)
    assert " ".join(c.text for c in chunks).split() == (PARAGRAPH * 4).split()
    assert chunks[0].page == 1


def make_paper(paper_id="2501.00001", pdf_url="https://arxiv.org/pdf/2501.00001v1"):
    return Paper(
        id=paper_id, version="v1", title="T", authors=[], abstract="A short abstract about attention.",
        categories=["cs.LG"], published_at=datetime(2025, 1, 1, tzinfo=timezone.utc),
        abs_url="https://arxiv.org/abs/x", pdf_url=pdf_url, text_status="pending",
    )


def processor(tmp_path, handler, **overrides):
    settings = Settings(
        _env_file=None, data_dir=tmp_path, pdf_download_delay_seconds=0, min_extracted_chars=100,
        chunk_size_chars=400, chunk_overlap_chars=100, **overrides,
    )
    settings.ensure_dirs()
    fetcher = PdfFetcher(settings, httpx.Client(transport=httpx.MockTransport(handler)))
    return DocumentProcessor(settings, fetcher), settings


def test_processor_extracts_full_text(db, tmp_path, sample_pdf):
    pdf_bytes = sample_pdf.read_bytes()
    calls = []

    def handler(request):
        calls.append(request)
        return httpx.Response(200, content=pdf_bytes)

    doc_processor, settings = processor(tmp_path, handler)
    paper = make_paper()
    db.add(paper)
    db.commit()
    assert doc_processor.process(db, paper, want_full_text=True) is True
    assert paper.text_status == "extracted"
    assert paper.chunks[0].source == "abstract"
    assert {c.section for c in paper.chunks if c.source == "pdf"} == {"1 Introduction", "2 Method", "3 Results"}
    assert [c.id for c in paper.chunks][:2] == ["2501.00001#0", "2501.00001#1"]
    assert (settings.pdf_dir / pdf_filename("2501.00001", "v1")).exists()
    doc_processor.process(db, paper, want_full_text=True)
    assert len(calls) == 1


def test_processor_falls_back_to_abstract(db, tmp_path):
    doc_processor, _ = processor(tmp_path, lambda r: httpx.Response(200, content=b"<html>captcha</html>"))
    paper = make_paper()
    db.add(paper)
    db.commit()
    assert doc_processor.process(db, paper, want_full_text=True) is False
    assert paper.text_status == "abstract_only"
    assert paper.pdf_error == "response is not a PDF"
    assert [c.source for c in paper.chunks] == ["abstract"]
    assert not doc_processor.needs_processing(paper, want_full_text=True)


def test_process_papers_limits_full_text(db, tmp_path, sample_pdf):
    pdf_bytes = sample_pdf.read_bytes()
    doc_processor, _ = processor(
        tmp_path, lambda r: httpx.Response(200, content=pdf_bytes), pdf_max_papers_per_query=1
    )
    papers = [make_paper("2501.00001"), make_paper("2501.00002", "https://arxiv.org/pdf/2501.00002v1")]
    db.add_all(papers)
    db.commit()
    report = doc_processor.process_papers(db, papers)
    assert report.full_text == ["2501.00001"] and report.abstract_only == ["2501.00002"]
    assert papers[1].pdf_error is None
    assert doc_processor.needs_processing(papers[1], want_full_text=True)
    assert doc_processor.process_papers(db, papers).skipped == ["2501.00001", "2501.00002"]


def test_fetcher_rejects_oversized(tmp_path):
    settings = Settings(_env_file=None, data_dir=tmp_path, pdf_download_delay_seconds=0, pdf_max_bytes=100_000)
    fetcher = PdfFetcher(settings, httpx.Client(transport=httpx.MockTransport(
        lambda r: httpx.Response(200, content=b"%PDF" + b"0" * 200_000)
    )))
    with pytest.raises(PdfFetchError):
        fetcher.fetch("2501.00001", "v1", "https://arxiv.org/pdf/2501.00001v1")
