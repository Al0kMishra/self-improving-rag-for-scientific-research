import json
from datetime import timedelta
from types import SimpleNamespace

import httpx
from pydantic import SecretStr
import pytest
from fastapi.testclient import TestClient

from app.main import create_app
from app.models import QueryRecord
from app.services.citations import map_citations, split_claims
from app.services.container import build_services
from app.services.generation import EvidenceItem, GeneratedAnswer, build_prompt
from app.services.llm import AnthropicLLM, LLMError, LLMRefusal, OpenAICompatibleLLM
from app.services.paper_retrieval import PaperRetriever
from tests.fakes import FakeArxivClient, HashEmbedder, ScriptedLLM, arxiv_paper
from tests.test_evaluation import judge_everything_supported
from tests.test_ranking import NOW


def test_split_claims_attaches_trailing_markers():
    claims = split_claims("Drafts propose tokens. [1] The target verifies them [2][3]. Speedups reach 3x [2].")
    assert claims == ["Drafts propose tokens. [1]", "The target verifies them [2][3].", "Speedups reach 3x [2]."]


def test_map_citations():
    answer = (
        "Speculative decoding uses a small draft model [1]. It preserves the output distribution [1, 2]. "
        "Some claim 10x gains [7]. This sentence has no citation at all and is long."
    )
    mapped = map_citations(answer, evidence_count=3)
    assert mapped.invalid_markers == [7]
    assert "[7]" not in mapped.answer
    assert [(l.marker, l.claim_index) for l in mapped.links] == [(1, 0), (1, 1), (2, 1)]
    assert mapped.links[0].claim == "Speculative decoding uses a small draft model ."
    assert mapped.uncited_claims == ["Some claim 10x gains .", "This sentence has no citation at all and is long."]
    assert len(mapped.claims) == 4
    assert mapped.cited_markers == [1, 2]


def test_uncited_claims_include_stripped_invalid_citations():
    mapped = map_citations("Some claim of tenfold gains appears here [7].", evidence_count=2)
    assert mapped.links == []
    assert len(mapped.uncited_claims) == 1


def test_prompt_numbers_evidence():
    evidence = [EvidenceItem(1, "p#0", "2501.00001", "A Paper", 2025, "1 Introduction", 2, "Body text.")]
    prompt = build_prompt("What?", evidence)
    assert "[1] A Paper (arXiv:2501.00001, 2025) section: 1 Introduction, page 2\nBody text." in prompt
    assert prompt.endswith("Question: What?")


class FakeMessages:
    def __init__(self, response):
        self.response = response
        self.calls = []

    def parse(self, **kwargs):
        self.calls.append(kwargs)
        return self.response


def fake_anthropic(response):
    messages = FakeMessages(response)
    beta = SimpleNamespace(messages=FakeMessages(response))
    return SimpleNamespace(messages=messages, beta=beta)


def parsed_response(stop_reason="end_turn", parsed=None, stop_details=None):
    return SimpleNamespace(stop_reason=stop_reason, parsed_output=parsed, stop_details=stop_details)


def test_anthropic_uses_fallbacks_for_opus(settings):
    answer = GeneratedAnswer(answer="x [1].", insufficient_evidence=False)
    client = fake_anthropic(parsed_response(parsed=answer))
    llm = AnthropicLLM(settings.model_copy(update={"llm_effort": "medium"}), client=client)
    assert llm.structured("sys", "prompt", GeneratedAnswer) == answer
    call = client.beta.messages.calls[0]
    assert call["model"] == "claude-opus-5"
    assert call["fallbacks"] == "default" and call["betas"] == ["server-side-fallback-2026-07-01"]
    assert call["output_format"] is GeneratedAnswer
    assert call["output_config"] == {"effort": "medium"}
    assert "temperature" not in call


def test_anthropic_without_fallbacks_for_other_models(settings):
    client = fake_anthropic(parsed_response(parsed=GeneratedAnswer(answer="a", insufficient_evidence=True)))
    sonnet = settings.model_copy(update={"llm_model": "claude-sonnet-5"})
    AnthropicLLM(sonnet, client=client).structured("s", "p", GeneratedAnswer)
    assert client.messages.calls and not client.beta.messages.calls


@pytest.mark.parametrize(
    ("response", "error"),
    [
        (parsed_response("refusal", stop_details=SimpleNamespace(category="cyber")), LLMRefusal),
        (parsed_response("max_tokens"), LLMError),
        (parsed_response("end_turn", parsed=None), LLMError),
    ],
)
def test_anthropic_errors(settings, response, error):
    with pytest.raises(error):
        AnthropicLLM(settings, client=fake_anthropic(response)).structured("s", "p", GeneratedAnswer)


def openai_settings(settings):
    return settings.model_copy(update={"llm_provider": "openai_compatible", "llm_base_url": "http://llm/v1",
                                       "llm_model": "local"})


def test_openai_compatible_repairs_invalid_json(settings):
    replies = iter(['{"answer": 5}', json.dumps({"answer": "ok [1].", "insufficient_evidence": False})])
    requests = []

    def handler(request):
        requests.append(json.loads(request.content))
        content = next(replies)
        return httpx.Response(200, json={"choices": [{"message": {"content": content}, "finish_reason": "stop"}]})

    llm = OpenAICompatibleLLM(openai_settings(settings), http=httpx.Client(transport=httpx.MockTransport(handler)))
    result = llm.structured("sys", "prompt", GeneratedAnswer)
    assert result.answer == "ok [1]."
    assert requests[0]["response_format"] == {"type": "json_object"}
    assert "JSON schema" in requests[0]["messages"][0]["content"]
    assert len(requests[1]["messages"]) == 4


def test_openai_compatible_http_error(settings):
    llm = OpenAICompatibleLLM(
        openai_settings(settings), http=httpx.Client(transport=httpx.MockTransport(lambda r: httpx.Response(500)))
    )
    with pytest.raises(LLMError):
        llm.structured("s", "p", GeneratedAnswer)


def cite_first_two(prompt):
    return {"answer": "Speculative decoding drafts tokens with a small model [1]. "
                      "Verification keeps quality [2]. A made up result [9].",
            "insufficient_evidence": False}


@pytest.fixture
def rag_client(settings):
    papers = [
        arxiv_paper("2001.00001", "Speculative decoding", "Speculative decoding drafts tokens with a small model.",
                    NOW - timedelta(days=900)),
        arxiv_paper("2601.00002", "Verification in speculative decoding",
                    "Speculative decoding verification keeps the target distribution.", NOW - timedelta(days=30)),
        arxiv_paper("2401.00003", "Draft model design", "Draft models for speculative decoding trade depth for width.",
                    NOW - timedelta(days=300)),
    ]
    llm = ScriptedLLM(cite_first_two)
    judge = ScriptedLLM(judge_everything_supported)
    services = build_services(settings, embedder=HashEmbedder(), llm=llm, evaluator_llm=judge)
    services.retrieval.paper_retriever = PaperRetriever(settings, FakeArxivClient(papers))
    with TestClient(create_app(settings, services)) as client:
        client.llm = llm
        client.judge = judge
        yield client


def test_query_endpoint_generates_grounded_answer(rag_client):
    response = rag_client.post("/api/query", json={"query": "How does speculative decoding work?"})
    assert response.status_code == 200
    body = response.json()
    assert body["status"] == "completed"
    assert body["invalid_citations"] == [9]
    assert "[9]" not in body["answer"]
    assert body["total_claims"] == 3 and body["uncited_claims"] == 1
    assert [c["marker"] for c in body["citations"]] == [1, 2]
    retrieved_ids = [r["chunk_id"] for r in body["retrieved"]]
    assert [c["chunk_id"] for c in body["citations"]] == retrieved_ids[:2]
    assert sum(r["cited"] for r in body["retrieved"]) == 2
    assert body["latency"]["total_ms"] >= body["latency"]["generation_ms"]
    system, prompt, _ = rag_client.llm.prompts[0]
    assert "Use only the evidence excerpts" in system
    assert prompt.count("(arXiv:") == len(body["retrieved"])


def test_query_failure_is_recorded(rag_client):
    rag_client.llm.responses = [LLMError("boom")]
    response = rag_client.post("/api/query", json={"query": "How does speculative decoding work?"})
    assert response.status_code == 502
    assert response.json()["status"] == "failed"
    assert "LLMError: boom" in response.json()["error"]
    with rag_client.app.state.session_factory() as db:
        assert db.get(QueryRecord, response.json()["id"]).status == "failed"


def test_query_requires_llm(client):
    assert client.post("/api/query", json={"query": "speculative decoding"}).status_code == 503


def test_list_queries(rag_client):
    rag_client.post("/api/query", json={"query": "speculative decoding", "experiment_run": "exp1", "cycle": 0})
    rag_client.post("/api/query", json={"query": "speculative decoding"})
    assert len(rag_client.get("/api/query").json()) == 2
    scoped = rag_client.get("/api/query", params={"experiment_run": "exp1"}).json()
    assert [(q["experiment_run"], q["cycle"]) for q in scoped] == [("exp1", 0)]


def test_query_is_self_evaluated(rag_client):
    body = rag_client.post("/api/query", json={"query": "How does speculative decoding work?"}).json()
    evaluation = body["evaluation"]
    assert evaluation["evaluator_model"] == "scripted-llm"
    assert evaluation["citation_accuracy"] == pytest.approx(2 / 3)
    assert evaluation["groundedness"] == pytest.approx(2 / 3)
    assert evaluation["evidence_coverage"] == 0.5
    assert evaluation["answer_relevance"] == 0.75
    assert body["retrieved"][0]["judged_relevance"] == 1.0
    assert all(r["judged_relevance"] == 0.5 for r in body["retrieved"][1:])
    assert [c["support"] for c in body["citations"]] == [1.0, 1.0]
    assert body["latency"]["evaluation_ms"] is not None
    assert "speedup: missing" in evaluation["reasoning"]["evidence_coverage"]


def test_evaluation_failure_keeps_answer(rag_client):
    rag_client.judge.responses = [LLMError("judge down")]
    body = rag_client.post("/api/query", json={"query": "How does speculative decoding work?"}).json()
    assert body["status"] == "completed"
    assert body["evaluation"] is None
    assert "evaluation failed" in body["error"]


def test_proposed_queries_adapt_weights_unless_frozen(rag_client):
    def snapshots():
        return rag_client.get("/api/improvement/history").json()["snapshots"]

    rag_client.post("/api/query", json={"query": "How does speculative decoding work?", "learn": False})
    assert len(snapshots()) == 1
    rag_client.post("/api/query", json={"query": "How does speculative decoding work?", "mode": "baseline"})
    assert len(snapshots()) == 1
    rag_client.post("/api/query", json={"query": "How does speculative decoding work?"})
    assert [s["trigger"] for s in snapshots()] == ["init", "evaluation"]


def grok_and_gemini(settings):
    return settings.model_copy(update={
        "llm_provider": "openai_compatible", "llm_base_url": "https://api.x.ai/v1", "llm_model": "grok-model",
        "llm_api_key": SecretStr("xai-key"),
        "evaluator_provider": "openai_compatible", "evaluator_model": "gemini-model",
        "evaluator_base_url": "https://generativelanguage.googleapis.com/v1beta/openai",
        "evaluator_api_key": SecretStr("gemini-key"),
    })


def test_separate_evaluator_endpoint(settings):
    configured = grok_and_gemini(settings)
    generator, evaluator = configured.generator_endpoint, configured.evaluator_endpoint
    assert (generator.model, generator.api_key, generator.base_url) == ("grok-model", "xai-key", "https://api.x.ai/v1")
    assert (evaluator.model, evaluator.api_key) == ("gemini-model", "gemini-key")
    assert evaluator.base_url.startswith("https://generativelanguage")
    services = build_services(configured, embedder=HashEmbedder())
    assert services.query_pipeline.generator.model == "grok-model"
    assert services.query_pipeline.evaluator.llm.model == "gemini-model"
    assert services.query_pipeline.evaluator.llm.url.endswith("/openai/chat/completions")
    assert services.query_pipeline.evaluator.llm.http.headers["authorization"] == "Bearer gemini-key"


def test_evaluator_inherits_generator_settings(settings):
    configured = settings.model_copy(update={"llm_api_key": SecretStr("k"), "evaluator_model": "claude-sonnet-5"})
    evaluator = configured.evaluator_endpoint
    assert (evaluator.provider, evaluator.model, evaluator.api_key) == ("anthropic", "claude-sonnet-5", "k")
    other_provider = settings.model_copy(update={"llm_api_key": SecretStr("k"), "evaluator_provider": "openai_compatible",
                                                 "evaluator_base_url": "http://judge/v1"})
    assert other_provider.evaluator_endpoint.api_key is None


def test_status_reports_evaluator(settings):
    with TestClient(create_app(grok_and_gemini(settings), build_services(grok_and_gemini(settings),
                                                                         embedder=HashEmbedder()))) as client:
        components = client.get("/api/system/status").json()["components"]
    assert components["llm"]["detail"] == "openai_compatible:grok-model"
    assert components["evaluator"]["detail"] == "openai_compatible:gemini-model"
    assert "gemini-key" not in str(components) and "xai-key" not in str(components)


def test_openai_compatible_falls_back_without_json_mode(settings):
    seen = []

    def handler(request):
        body = json.loads(request.content)
        seen.append("response_format" in body)
        if "response_format" in body:
            return httpx.Response(400, json={"error": "response_format not supported"})
        content = json.dumps({"answer": "ok", "insufficient_evidence": True})
        return httpx.Response(200, json={"choices": [{"message": {"content": content}, "finish_reason": "stop"}]})

    llm = OpenAICompatibleLLM(openai_settings(settings), http=httpx.Client(transport=httpx.MockTransport(handler)))
    assert llm.structured("s", "p", GeneratedAnswer).answer == "ok"
    llm.structured("s", "p", GeneratedAnswer)
    assert seen == [True, False, False]


def test_single_model_is_shared_by_writer_and_judge(settings):
    single = settings.model_copy(update={"llm_api_key": SecretStr("k")})
    assert not single.separate_evaluator
    pipeline = build_services(single, embedder=HashEmbedder()).query_pipeline
    assert pipeline.evaluator.llm is pipeline.generator.llm


def test_same_provider_different_judge_model(settings):
    configured = settings.model_copy(update={
        "llm_provider": "openai_compatible", "llm_base_url": "https://gemini/openai", "llm_model": "light",
        "llm_api_key": SecretStr("g"), "evaluator_model": "strong",
    })
    pipeline = build_services(configured, embedder=HashEmbedder()).query_pipeline
    assert (pipeline.generator.model, pipeline.evaluator.llm.model) == ("light", "strong")
    assert pipeline.evaluator.llm.url == "https://gemini/openai/chat/completions"
    assert pipeline.evaluator.llm.http.headers["authorization"] == "Bearer g"


def test_separate_judge_without_key_is_rejected():
    from pydantic import ValidationError
    from app.core.config import Settings

    with pytest.raises(ValidationError, match="EVALUATOR_API_KEY"):
        Settings(_env_file=None, llm_provider="openai_compatible", llm_base_url="https://api.x.ai/v1",
                 llm_api_key="x", evaluator_provider="anthropic", evaluator_model="claude-opus-5")
