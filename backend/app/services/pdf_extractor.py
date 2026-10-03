import re
from dataclasses import dataclass
from pathlib import Path

import pymupdf

NUMBERED_HEADING = re.compile(r"^(?:\d{1,2}(?:\.\d{1,2}){0,2}\.?|[IVX]{1,5}\.|[A-H]\.?)\s+([A-Z][^.!?]{2,80})$")
NAMED_HEADINGS = {
    "abstract", "introduction", "background", "related work", "related works", "preliminaries",
    "method", "methods", "methodology", "approach", "model", "experiments", "experimental setup",
    "experimental results", "results", "evaluation", "analysis", "discussion", "limitations",
    "conclusion", "conclusions", "conclusion and future work", "future work",
}
STOP_HEADINGS = {"references", "bibliography", "acknowledgments", "acknowledgements"}
SECTION_NUMBER = re.compile(r"^(?:\d{1,2}(?:\.\d{1,2}){0,2}\.?|[IVX]{1,5}\.?)$")
MAX_HEADING_CHARS = 90
BIBLIOGRAPHY_MARKERS = re.compile(
    r"\b(?:19|20)\d{2}[a-z]?\b|et al\.|arXiv preprint|Proceedings|Conference on|In Advances|"
    r"\bpp\.|\bvol\.|doi:|https?://|\b[A-Z]\.,"
)
BIBLIOGRAPHY_DENSITY = 1 / 60
BIBLIOGRAPHY_RUN_TO_STOP = 3
MIN_BLOCK_CHARS = 40
MIN_ALPHA_RATIO = 0.55


class PdfExtractionError(RuntimeError):
    pass


@dataclass
class TextBlock:
    page: int
    section: str | None
    text: str


def clean_text(text: str) -> str:
    text = re.sub(r"(\w)-\n(\w)", r"\1\2", text)
    text = text.replace("ﬁ", "fi").replace("ﬂ", "fl")
    return " ".join(text.split())


def heading_title(line: str) -> str | None:
    candidate = " ".join(line.split())
    if not candidate or len(candidate) > MAX_HEADING_CHARS:
        return None
    lowered = candidate.lower().rstrip(":")
    bare = re.sub(r"^[\dIVX.\s]+", "", lowered).strip()
    if lowered in STOP_HEADINGS or bare in STOP_HEADINGS:
        return candidate.rstrip(":")
    if lowered in NAMED_HEADINGS or bare in NAMED_HEADINGS:
        return candidate.rstrip(":")
    match = NUMBERED_HEADING.match(candidate)
    if match and not candidate.endswith(","):
        return candidate
    return None


def detect_heading(lines: list[str]) -> tuple[str | None, int]:
    whole = clean_text("\n".join(lines))
    if len(whole) <= MAX_HEADING_CHARS and (title := heading_title(whole)):
        return title, len(lines)
    if len(lines) > 1 and SECTION_NUMBER.match(lines[0].strip()):
        if title := heading_title(f"{lines[0].strip()} {lines[1].strip()}"):
            return title, 2
    if title := heading_title(lines[0]):
        return title, 1
    return None, 0


def is_stop_heading(title: str) -> bool:
    return re.sub(r"^[\dIVX.\s]+", "", title.lower()).strip() in STOP_HEADINGS


def is_prose(text: str) -> bool:
    if len(text) < MIN_BLOCK_CHARS:
        return False
    letters = sum(ch.isalpha() or ch.isspace() for ch in text)
    return letters / len(text) >= MIN_ALPHA_RATIO


def looks_like_bibliography(text: str) -> bool:
    return len(BIBLIOGRAPHY_MARKERS.findall(text)) >= max(3, len(text) * BIBLIOGRAPHY_DENSITY)


def extract_blocks(path: Path, max_pages: int) -> list[TextBlock]:
    try:
        document = pymupdf.open(path)
    except (pymupdf.FileDataError, RuntimeError) as exc:
        raise PdfExtractionError(f"cannot open PDF: {exc}") from exc

    blocks: list[TextBlock] = []
    section: str | None = None
    bibliography_run = 0
    with document:
        for page_index in range(min(max_pages, document.page_count)):
            page = document[page_index]
            for *_, raw, _block_no, block_type in page.get_text("blocks", sort=True):
                if block_type != 0:
                    continue
                lines = [line for line in raw.splitlines() if line.strip()]
                if not lines:
                    continue
                title, consumed = detect_heading(lines)
                if title is not None:
                    if is_stop_heading(title):
                        return blocks
                    section = title
                    lines = lines[consumed:]
                text = clean_text("\n".join(lines))
                if looks_like_bibliography(text):
                    bibliography_run += 1
                    if bibliography_run >= BIBLIOGRAPHY_RUN_TO_STOP:
                        return blocks
                    continue
                bibliography_run = 0
                if is_prose(text):
                    blocks.append(TextBlock(page=page_index + 1, section=section, text=text))
    return blocks
