import re
from dataclasses import dataclass, field

MARKER_GROUP = re.compile(r"\[(\d+(?:\s*[,;]\s*\d+)*)\]")
SENTENCE_BOUNDARY = re.compile(r"(?<=[.!?])\s+(?=[A-Z\[(\"'])")
LEADING_MARKERS = re.compile(r"^((?:\[\d+(?:\s*[,;]\s*\d+)*\]\s*)+)")
MIN_CLAIM_CHARS = 25
REMOVED = "[?]"


@dataclass
class CitationLink:
    marker: int
    claim_index: int
    claim: str


@dataclass
class CitationMap:
    answer: str
    claims: list[str]
    links: list[CitationLink] = field(default_factory=list)
    invalid_markers: list[int] = field(default_factory=list)
    uncited_claims: list[str] = field(default_factory=list)

    @property
    def cited_markers(self) -> list[int]:
        return sorted({link.marker for link in self.links})


def markers_in(text: str) -> list[int]:
    found = []
    for group in MARKER_GROUP.findall(text):
        found.extend(int(n) for n in re.split(r"\s*[,;]\s*", group))
    return found


def strip_markers(text: str) -> str:
    return " ".join(MARKER_GROUP.sub("", text).replace(REMOVED, "").split())


def remove_invalid(answer: str, valid: set[int]) -> tuple[str, list[int]]:
    invalid: list[int] = []

    def rewrite(match: re.Match) -> str:
        numbers = [int(n) for n in re.split(r"\s*[,;]\s*", match.group(1))]
        kept = [n for n in numbers if n in valid]
        invalid.extend(n for n in numbers if n not in valid)
        return "".join(f"[{n}]" for n in kept) or REMOVED

    return MARKER_GROUP.sub(rewrite, answer), invalid


def split_claims(answer: str) -> list[str]:
    claims: list[str] = []
    for paragraph in answer.split("\n"):
        for sentence in SENTENCE_BOUNDARY.split(paragraph.strip()):
            if not sentence:
                continue
            leading = LEADING_MARKERS.match(sentence)
            if leading and claims:
                claims[-1] = f"{claims[-1]} {leading.group(1).strip()}"
                sentence = sentence[leading.end():]
            if sentence.strip():
                claims.append(sentence.strip())
    return claims


def map_citations(answer: str, evidence_count: int) -> CitationMap:
    marked, invalid = remove_invalid(answer, set(range(1, evidence_count + 1)))
    claims = split_claims(marked)
    cleaned_answer = "\n".join(" ".join(line.replace(REMOVED, "").split()) for line in marked.split("\n"))
    result = CitationMap(
        answer=cleaned_answer,
        claims=[claim.replace(REMOVED, "").strip() for claim in claims],
        invalid_markers=sorted(set(invalid)),
    )
    for index, claim in enumerate(claims):
        numbers = list(dict.fromkeys(markers_in(claim)))
        if not numbers:
            if REMOVED in claim or len(strip_markers(claim)) >= MIN_CLAIM_CHARS:
                result.uncited_claims.append(strip_markers(claim))
            continue
        for number in numbers:
            result.links.append(CitationLink(marker=number, claim_index=index, claim=strip_markers(claim)))
    return result
