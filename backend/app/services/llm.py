import json
import logging
from typing import Protocol, TypeVar

import httpx
from pydantic import BaseModel, ValidationError

from app.core.config import LLMEndpoint, Settings

logger = logging.getLogger(__name__)

T = TypeVar("T", bound=BaseModel)

FALLBACK_MODELS = {"claude-opus-5", "claude-opus-5-5", "claude-fable-5-1"}
FALLBACK_BETA = "server-side-fallback-2026-07-01"


class LLMError(RuntimeError):
    pass


class LLMRefusal(LLMError):
    pass


class LLMClient(Protocol):
    model: str

    def structured(self, system: str, prompt: str, schema: type[T]) -> T: ...


class AnthropicLLM:
    def __init__(self, settings: Settings, endpoint: LLMEndpoint | None = None, client=None):
        import anthropic

        endpoint = endpoint or settings.generator_endpoint
        self.settings = settings
        self.model = endpoint.model
        self.client = client or anthropic.Anthropic(
            api_key=endpoint.api_key or None,
            base_url=endpoint.base_url or None,
            timeout=settings.llm_timeout_seconds,
        )

    def structured(self, system: str, prompt: str, schema: type[T]) -> T:
        import anthropic

        request = {
            "model": self.model,
            "max_tokens": self.settings.llm_max_tokens,
            "system": system,
            "messages": [{"role": "user", "content": prompt}],
            "output_format": schema,
        }
        if self.settings.llm_effort:
            request["output_config"] = {"effort": self.settings.llm_effort}
        try:
            if self.settings.llm_fallbacks and self.model in FALLBACK_MODELS:
                response = self.client.beta.messages.parse(**request, betas=[FALLBACK_BETA], fallbacks="default")
            else:
                response = self.client.messages.parse(**request)
        except anthropic.APIConnectionError as exc:
            raise LLMError(f"cannot reach Anthropic API: {exc}") from exc
        except anthropic.APIStatusError as exc:
            raise LLMError(f"Anthropic API error {exc.status_code}: {exc.message}") from exc

        if response.stop_reason == "refusal":
            category = getattr(response.stop_details, "category", None) if response.stop_details else None
            raise LLMRefusal(f"model declined the request (category: {category})")
        if response.stop_reason == "max_tokens":
            raise LLMError("response truncated at max_tokens")
        if response.parsed_output is None:
            raise LLMError("model returned no structured output")
        return response.parsed_output


class OpenAICompatibleLLM:
    def __init__(self, settings: Settings, endpoint: LLMEndpoint | None = None, http: httpx.Client | None = None):
        endpoint = endpoint or settings.generator_endpoint
        self.settings = settings
        self.model = endpoint.model
        headers = {"Authorization": f"Bearer {endpoint.api_key}"} if endpoint.api_key else {}
        self.http = http or httpx.Client(timeout=settings.llm_timeout_seconds, headers=headers)
        self.url = f"{endpoint.base_url.rstrip('/')}/chat/completions"
        self.json_mode = True

    def _complete(self, messages: list[dict]) -> str:
        payload = {
            "model": self.model,
            "messages": messages,
            "temperature": self.settings.llm_temperature,
            "max_tokens": self.settings.llm_max_tokens,
        }
        if self.json_mode:
            payload["response_format"] = {"type": "json_object"}
        try:
            response = self.http.post(self.url, json=payload)
        except httpx.HTTPError as exc:
            raise LLMError(f"cannot reach {self.url}: {exc}") from exc
        if response.status_code == 400 and self.json_mode:
            logger.info("endpoint rejected JSON mode, retrying with the schema in the prompt only")
            self.json_mode = False
            return self._complete(messages)
        if response.status_code != 200:
            raise LLMError(f"LLM endpoint returned HTTP {response.status_code}: {response.text[:300]}")
        choice = response.json()["choices"][0]
        if choice.get("finish_reason") == "length":
            raise LLMError("response truncated at max_tokens")
        return choice["message"]["content"] or ""

    def structured(self, system: str, prompt: str, schema: type[T]) -> T:
        schema_text = json.dumps(schema.model_json_schema())
        messages = [
            {"role": "system", "content": f"{system}\n\nReply with one JSON object that matches this JSON schema:\n{schema_text}"},
            {"role": "user", "content": prompt},
        ]
        content = self._complete(messages)
        try:
            return schema.model_validate_json(content)
        except ValidationError as exc:
            logger.info("structured output invalid, asking the model to repair it: %s", exc.errors()[:3])
            messages += [
                {"role": "assistant", "content": content},
                {"role": "user", "content": f"That JSON did not match the schema: {exc}. Reply with corrected JSON only."},
            ]
            try:
                return schema.model_validate_json(self._complete(messages))
            except ValidationError as second:
                raise LLMError(f"model output did not match {schema.__name__}: {second}") from second


def build_llm(settings: Settings, endpoint: LLMEndpoint | None = None) -> LLMClient | None:
    endpoint = endpoint or settings.generator_endpoint
    if not endpoint.configured:
        return None
    if endpoint.provider == "anthropic":
        return AnthropicLLM(settings, endpoint)
    return OpenAICompatibleLLM(settings, endpoint)
