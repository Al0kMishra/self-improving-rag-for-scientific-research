import re
import threading
import time
from pathlib import Path

import httpx

from app.core.config import Settings


class PdfFetchError(RuntimeError):
    pass


def pdf_filename(paper_id: str, version: str | None) -> str:
    return re.sub(r"[^A-Za-z0-9.\-]", "_", f"{paper_id}{version or ''}") + ".pdf"


class PdfFetcher:
    _lock = threading.Lock()
    _last_request = 0.0

    def __init__(self, settings: Settings, http: httpx.Client | None = None):
        self.settings = settings
        self.http = http or httpx.Client(timeout=60, follow_redirects=True)

    def _wait_for_slot(self) -> None:
        with PdfFetcher._lock:
            delay = self.settings.pdf_download_delay_seconds - (time.monotonic() - PdfFetcher._last_request)
            if delay > 0:
                time.sleep(delay)
            PdfFetcher._last_request = time.monotonic()

    def fetch(self, paper_id: str, version: str | None, url: str) -> Path:
        path = self.settings.pdf_dir / pdf_filename(paper_id, version)
        if path.exists() and path.stat().st_size > 0:
            return path

        self._wait_for_slot()
        try:
            with self.http.stream("GET", url) as response:
                if response.status_code != 200:
                    raise PdfFetchError(f"HTTP {response.status_code} for {url}")
                content = bytearray()
                for block in response.iter_bytes():
                    content.extend(block)
                    if len(content) > self.settings.pdf_max_bytes:
                        raise PdfFetchError(f"PDF exceeds {self.settings.pdf_max_bytes} bytes")
        except httpx.HTTPError as exc:
            raise PdfFetchError(str(exc)) from exc

        if not content.startswith(b"%PDF"):
            raise PdfFetchError("response is not a PDF")
        path.parent.mkdir(parents=True, exist_ok=True)
        temporary = path.with_suffix(".part")
        temporary.write_bytes(bytes(content))
        temporary.replace(path)
        return path
