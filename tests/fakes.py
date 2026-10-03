import hashlib
import math
import re


class HashEmbedder:
    model_name = "test-hash-embedder"
    loaded = True
    dimensions = 64

    def embed(self, texts):
        return [self._vector(text) for text in texts]

    def _vector(self, text):
        vector = [0.0] * self.dimensions
        for word in re.findall(r"[a-z0-9]+", text.lower()):
            index = int(hashlib.md5(word.encode()).hexdigest(), 16) % self.dimensions
            vector[index] += 1.0
        norm = math.sqrt(sum(v * v for v in vector)) or 1.0
        return [v / norm for v in vector]


class FakeArxivClient:
    def __init__(self, papers):
        self.papers = papers
        self.calls = 0

    def search(self, search_query, max_results):
        from app.services.arxiv_client import ArxivSearchResult

        self.calls += 1
        return ArxivSearchResult(total_results=len(self.papers), papers=list(self.papers[:max_results]))


def arxiv_paper(paper_id, title, abstract, published_at, pdf_url=None):
    from app.services.arxiv_client import ArxivPaper

    return ArxivPaper(
        id=paper_id,
        version="v1",
        title=title,
        authors=["Test Author"],
        abstract=abstract,
        categories=["cs.LG"],
        primary_category="cs.LG",
        published_at=published_at,
        updated_at=None,
        abs_url=f"https://arxiv.org/abs/{paper_id}",
        pdf_url=pdf_url,
    )


class ScriptedLLM:
    model = "scripted-llm"

    def __init__(self, *responses):
        self.responses = list(responses)
        self.prompts = []

    def structured(self, system, prompt, schema):
        self.prompts.append((system, prompt, schema))
        response = self.responses.pop(0) if len(self.responses) > 1 else self.responses[0]
        if isinstance(response, Exception):
            raise response
        if callable(response):
            response = response(prompt)
        return schema.model_validate(response)
