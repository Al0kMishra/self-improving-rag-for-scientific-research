import re
from dataclasses import dataclass

STOPWORDS = frozenset(
    """
    a about above after again against all am an and any are as at be because been before being below
    between both but by can could did do does doing down during each few for from further had has have
    having how i if in into is it its itself just me more most my no nor not now of off on once only or
    other our out over own same should so some such than that the their them then there these they this
    those through to too under until up very was we were what when where which while who whom why will
    with would you your
    approach approaches compare compared comparison current effective effectiveness explain exist exists
    affect affects recent recently method methods technique techniques use used using way ways work
    works paper papers research art latest new advance advances role impact much many like
    """.split()
)

TOKEN = re.compile(r"[A-Za-z0-9][A-Za-z0-9\-\+]*")


@dataclass(frozen=True)
class AnalyzedQuery:
    original: str
    keywords: list[str]

    @property
    def normalized(self) -> str:
        return " ".join(self.keywords)


def extract_keywords(text: str, limit: int) -> list[str]:
    keywords: list[str] = []
    for token in TOKEN.findall(text):
        word = token.lower().strip("-")
        if len(word) < 2 or word in STOPWORDS or word in keywords:
            continue
        keywords.append(word)
        if len(keywords) == limit:
            break
    return keywords


def analyze_query(text: str, max_keywords: int) -> AnalyzedQuery:
    return AnalyzedQuery(original=text.strip(), keywords=extract_keywords(text, max_keywords))
