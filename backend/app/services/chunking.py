import re
from dataclasses import dataclass

from app.services.pdf_extractor import TextBlock

SENTENCE_END = re.compile(r"(?<=[.!?])\s+(?=[A-Z(\[])")


@dataclass
class ChunkDraft:
    section: str | None
    page: int | None
    text: str


def split_sentences(text: str) -> list[str]:
    return [s for s in SENTENCE_END.split(text) if s]


def split_long(text: str, size: int) -> list[str]:
    pieces, current = [], ""
    for sentence in split_sentences(text):
        while len(sentence) > size:
            if current:
                pieces.append(current)
                current = ""
            pieces.append(sentence[:size])
            sentence = sentence[size:]
        if current and len(current) + 1 + len(sentence) > size:
            pieces.append(current)
            current = sentence
        else:
            current = f"{current} {sentence}".strip()
    if current:
        pieces.append(current)
    return pieces


def overlap_tail(text: str, overlap: int) -> str:
    if overlap <= 0:
        return ""
    tail = ""
    for sentence in reversed(split_sentences(text)):
        if len(tail) + len(sentence) + 1 > overlap:
            break
        tail = f"{sentence} {tail}".strip()
    return tail


def chunk_blocks(blocks: list[TextBlock], size: int, overlap: int) -> list[ChunkDraft]:
    chunks: list[ChunkDraft] = []
    buffer = carried = ""
    section: str | None = None
    page: int | None = None

    def emit() -> None:
        if buffer and buffer != carried:
            chunks.append(ChunkDraft(section=section, page=page, text=buffer))

    for block in blocks:
        if block.section != section:
            emit()
            buffer = carried = ""
            section, page = block.section, block.page
        for piece in split_long(block.text, size):
            if not buffer:
                page = block.page
            if buffer != carried and len(buffer) + 1 + len(piece) > size:
                emit()
                buffer = carried = overlap_tail(buffer, overlap)
                page = block.page
            buffer = f"{buffer} {piece}".strip()
    emit()
    return chunks
