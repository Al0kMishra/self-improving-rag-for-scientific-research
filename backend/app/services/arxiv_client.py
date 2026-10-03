import logging
import threading
import time
import xml.etree.ElementTree as ET
from dataclasses import dataclass, field
from datetime import datetime, timedelta, timezone

import httpx

from app.core.config import Settings

logger = logging.getLogger(__name__)

NS = {
    "atom": "http://www.w3.org/2005/Atom",
    "arxiv": "http://arxiv.org/schemas/atom",
    "opensearch": "http://a9.com/-/spec/opensearch/1.1/",
}
RETRY_STATUSES = {429, 500, 502, 503, 504}


class ArxivError(RuntimeError):
    pass


@dataclass
class ArxivPaper:
    id: str
    version: str | None
    title: str
    authors: list[str]
    abstract: str
    categories: list[str]
    primary_category: str | None
    published_at: datetime
    updated_at: datetime | None
    abs_url: str
    pdf_url: str | None


@dataclass
class ArxivSearchResult:
    total_results: int
    papers: list[ArxivPaper] = field(default_factory=list)


def _clean(text: str | None) -> str:
    return " ".join((text or "").split())


def _parse_time(text: str | None) -> datetime | None:
    if not text:
        return None
    return datetime.fromisoformat(text.replace("Z", "+00:00"))


def split_arxiv_id(raw: str) -> tuple[str, str | None]:
    identifier = raw.rsplit("/abs/", 1)[-1]
    head, sep, version = identifier.rpartition("v")
    if sep and version.isdigit() and head:
        return head, f"v{version}"
    return identifier, None


def parse_feed(xml_text: str) -> ArxivSearchResult:
    try:
        root = ET.fromstring(xml_text)
    except ET.ParseError as exc:
        raise ArxivError(f"invalid arXiv response: {exc}") from exc

    total = int(root.findtext("opensearch:totalResults", "0", NS))
    papers = []
    for entry in root.findall("atom:entry", NS):
        raw_id = entry.findtext("atom:id", "", NS)
        if "/abs/" not in raw_id:
            continue
        paper_id, version = split_arxiv_id(raw_id)
        pdf_url = None
        abs_url = f"https://arxiv.org/abs/{paper_id}"
        for link in entry.findall("atom:link", NS):
            if link.get("title") == "pdf":
                pdf_url = link.get("href")
            elif link.get("rel") == "alternate":
                abs_url = link.get("href", abs_url)
        primary = entry.find("arxiv:primary_category", NS)
        papers.append(
            ArxivPaper(
                id=paper_id,
                version=version,
                title=_clean(entry.findtext("atom:title", "", NS)),
                authors=[_clean(a.findtext("atom:name", "", NS)) for a in entry.findall("atom:author", NS)],
                abstract=_clean(entry.findtext("atom:summary", "", NS)),
                categories=[c.get("term") for c in entry.findall("atom:category", NS) if c.get("term")],
                primary_category=primary.get("term") if primary is not None else None,
                published_at=_parse_time(entry.findtext("atom:published", None, NS)),
                updated_at=_parse_time(entry.findtext("atom:updated", None, NS)),
                abs_url=abs_url,
                pdf_url=pdf_url,
            )
        )
    return ArxivSearchResult(total_results=total, papers=papers)


def _term(keyword: str) -> str:
    words = keyword.replace("-", " ").split()
    return f'all:"{" ".join(words)}"' if len(words) > 1 else f"all:{words[0]}"


def build_search_query(
    keywords: list[str],
    categories: list[str],
    recency_days: int | None,
    operator: str = "AND",
    now: datetime | None = None,
) -> str:
    if not keywords:
        raise ValueError("at least one keyword is required")
    parts = [f"({f' {operator} '.join(_term(k) for k in keywords)})"]
    parts.append(f"({' OR '.join(f'cat:{c}' for c in categories)})")
    if recency_days is not None:
        end = now or datetime.now(timezone.utc)
        start = end - timedelta(days=recency_days)
        parts.append(f"submittedDate:[{start:%Y%m%d%H%M} TO {end:%Y%m%d%H%M}]")
    return " AND ".join(parts)


class ArxivClient:
    _lock = threading.Lock()
    _last_request = 0.0

    def __init__(self, settings: Settings, http: httpx.Client | None = None):
        self.settings = settings
        self.http = http or httpx.Client(timeout=settings.arxiv_timeout_seconds, follow_redirects=True)
        self.max_attempts = settings.arxiv_max_attempts

    def _backoff(self, attempt: int, response: httpx.Response | None) -> float:
        retry_after = response.headers.get("retry-after") if response is not None else None
        if retry_after and retry_after.isdigit():
            return min(float(retry_after), 300.0)
        return self.settings.arxiv_backoff_seconds * 2 ** (attempt - 1)

    def _wait_for_slot(self) -> None:
        with ArxivClient._lock:
            elapsed = time.monotonic() - ArxivClient._last_request
            delay = self.settings.arxiv_request_delay_seconds - elapsed
            if delay > 0:
                time.sleep(delay)
            ArxivClient._last_request = time.monotonic()

    def search(self, search_query: str, max_results: int) -> ArxivSearchResult:
        params = {
            "search_query": search_query,
            "start": 0,
            "max_results": max_results,
            "sortBy": "relevance",
            "sortOrder": "descending",
        }
        last_error: Exception | None = None
        for attempt in range(1, self.max_attempts + 1):
            self._wait_for_slot()
            response = None
            try:
                response = self.http.get(self.settings.arxiv_api_url, params=params)
            except httpx.HTTPError as exc:
                last_error = exc
            else:
                if response.status_code == 200:
                    return parse_feed(response.text)
                last_error = ArxivError(f"arXiv returned HTTP {response.status_code}")
                if response.status_code not in RETRY_STATUSES:
                    break
            if attempt == self.max_attempts:
                break
            wait = self._backoff(attempt, response)
            logger.warning(
                "arXiv request failed (attempt %d/%d): %s, retrying in %.0fs",
                attempt, self.max_attempts, last_error, wait,
            )
            time.sleep(wait)
        raise ArxivError(str(last_error))
