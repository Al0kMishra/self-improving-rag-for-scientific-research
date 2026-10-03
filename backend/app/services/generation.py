from dataclasses import dataclass

from pydantic import BaseModel, Field

from app.services.llm import LLMClient

SYSTEM_PROMPT = """You are a research assistant that answers questions about AI and machine learning \
literature using only the numbered evidence excerpts from arXiv papers supplied by the user.

Rules:
- Use only the evidence excerpts. Do not add facts, numbers, papers, or authors from memory.
- End every sentence that states a fact with citation markers such as [2] or [1][3], where the numbers \
are the evidence numbers that directly support that sentence. Never cite a number that was not supplied.
- Prefer citing the single most specific excerpt over citing many loosely related ones.
- If the excerpts disagree, say so and cite both sides.
- If the excerpts do not contain enough information to answer fully, answer only the part they support, \
set insufficient_evidence to true, and describe what is missing in missing_information.
- If none of the excerpts are relevant, say that the retrieved evidence does not answer the question and \
cite nothing.
- Write two to four concise paragraphs of plain prose without headings or bullet lists."""


class GeneratedAnswer(BaseModel):
    answer: str = Field(description="The answer, with [n] citation markers after each factual sentence.")
    insufficient_evidence: bool = Field(description="True when the evidence does not fully answer the question.")
    missing_information: str | None = Field(
        default=None, description="What the evidence lacks, when insufficient_evidence is true."
    )


@dataclass
class EvidenceItem:
    number: int
    chunk_id: str
    paper_id: str
    title: str
    year: int
    section: str | None
    page: int | None
    text: str


def format_evidence(evidence: list[EvidenceItem]) -> str:
    blocks = []
    for item in evidence:
        location = ", ".join(
            part for part in (item.section and f"section: {item.section}", item.page and f"page {item.page}") if part
        )
        header = f"[{item.number}] {item.title} (arXiv:{item.paper_id}, {item.year})"
        blocks.append(f"{header}{f' {location}' if location else ''}\n{item.text}")
    return "\n\n".join(blocks)


def build_prompt(question: str, evidence: list[EvidenceItem]) -> str:
    return f"Evidence excerpts:\n\n{format_evidence(evidence)}\n\nQuestion: {question}"


NO_EVIDENCE_ANSWER = GeneratedAnswer(
    answer="The retrieval step found no evidence excerpts for this question, so no grounded answer can be given.",
    insufficient_evidence=True,
    missing_information="No relevant arXiv excerpts were retrieved.",
)


class AnswerGenerator:
    def __init__(self, llm: LLMClient):
        self.llm = llm

    @property
    def model(self) -> str:
        return self.llm.model

    def generate(self, question: str, evidence: list[EvidenceItem]) -> GeneratedAnswer:
        if not evidence:
            return NO_EVIDENCE_ANSWER
        return self.llm.structured(SYSTEM_PROMPT, build_prompt(question, evidence), GeneratedAnswer)
