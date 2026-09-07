from __future__ import annotations

from copy import deepcopy
import re
from typing import Any

import httpx
from openai import OpenAI

from config import settings


class EmptyModelResponseError(RuntimeError):
    """Raised when every LM Studio generation strategy returns no final text."""


class LMStudioClient:
    """LM Studio client for the configured local model."""

    def __init__(self, base_url: str | None = None, api_key: str | None = None) -> None:
        self.base_url = (base_url or settings.lmstudio_base_url).rstrip("/")
        self.api_key = api_key or settings.lmstudio_api_key
        self.client = OpenAI(
            base_url=self.base_url,
            api_key=self.api_key,
            timeout=settings.lmstudio_request_timeout,
        )

    def list_models(self) -> list[str]:
        result = self.client.models.list()
        return sorted([m.id for m in result.data])

    @staticmethod
    def _model_key(value: str) -> str:
        return re.sub(r"[^a-z0-9]+", "", value.lower())

    def model_id(self) -> str:
        expected = self._model_key(settings.model_name)
        for model_id in self.list_models():
            candidate = self._model_key(model_id)
            if candidate == expected or expected in candidate:
                return model_id
        raise RuntimeError(
            f"{settings.model_name} is not loaded in LM Studio."
        )

    @staticmethod
    def _text_from_content(content: Any) -> str:
        """Normalize OpenAI-compatible message content into plain text."""
        if content is None:
            return ""
        if isinstance(content, str):
            return content.strip()
        if isinstance(content, list):
            parts: list[str] = []
            for part in content:
                if isinstance(part, str):
                    parts.append(part)
                    continue
                if isinstance(part, dict):
                    text = part.get("text") or part.get("content") or part.get("output_text")
                    if isinstance(text, str):
                        parts.append(text)
                    continue
                for attr in ("text", "content", "output_text"):
                    text = getattr(part, attr, None)
                    if isinstance(text, str):
                        parts.append(text)
                        break
            return "\n".join(p for p in parts if p).strip()
        return str(content).strip()

    @staticmethod
    def _visible_final_text(text: str) -> str:
        """Remove Qwen-style thinking blocks and return only visible final text."""
        if not text:
            return ""
        cleaned = text.strip()

        # Remove complete hidden-thought blocks if a model serialized them into content.
        cleaned = re.sub(r"<think>.*?</think>", "", cleaned, flags=re.IGNORECASE | re.DOTALL).strip()

        # If an unclosed <think> remains, there is no trustworthy final answer to expose.
        if re.search(r"<think>", cleaned, flags=re.IGNORECASE):
            return ""

        # Some templates use explicit final tags.
        final_match = re.search(r"<final>(.*?)</final>", cleaned, flags=re.IGNORECASE | re.DOTALL)
        if final_match:
            cleaned = final_match.group(1).strip()

        return cleaned

    @staticmethod
    def _is_qwen(model: str) -> bool:
        return "qwen" in model.lower()

    @staticmethod
    def _is_thinking_only_model(model: str) -> bool:
        name = model.lower()
        return "thinking" in name and "instruct" not in name

    @classmethod
    def _prepare_messages(cls, model: str, messages: list[dict[str, str]]) -> list[dict[str, str]]:
        """Prepare messages for Qwen instruct generation."""
        prepared = deepcopy(messages)

        if settings.disable_qwen_thinking and cls._is_qwen(model) and not cls._is_thinking_only_model(model):
            for message in reversed(prepared):
                if message.get("role") == "user":
                    content = message.get("content", "")
                    if "/no_think" not in content:
                        message["content"] = (
                            f"{content}\n\n/no_think\n"
                            "Return only the visible final grounded answer. Do not output a thinking block."
                        )
                    break

        return prepared

    @staticmethod
    def _compact_messages(messages: list[dict[str, str]], char_limit: int) -> list[dict[str, str]]:
        """Compact a long RAG prompt."""
        if char_limit <= 0:
            return deepcopy(messages)

        compact = deepcopy(messages)
        total = sum(len(str(m.get("content", ""))) for m in compact)
        if total <= char_limit:
            return compact

        for message in reversed(compact):
            if message.get("role") != "user":
                continue
            content = str(message.get("content", ""))
            if len(content) <= char_limit:
                return compact

            head_len = int(char_limit * 0.72)
            tail_len = max(400, char_limit - head_len)
            message["content"] = (
                content[:head_len]
                + "\n\n[Context compacted for generation stability]\n\n"
                + content[-tail_len:]
            )
            break
        return compact

    def _request_chat(
        self,
        *,
        model: str,
        messages: list[dict[str, str]],
        temperature: float,
        max_tokens: int,
    ):
        return self.client.chat.completions.create(
            model=model,
            messages=messages,
            temperature=temperature,
            max_tokens=max_tokens,
        )

    def _request_chat_stream(
        self,
        *,
        model: str,
        messages: list[dict[str, str]],
        temperature: float,
        max_tokens: int,
    ) -> str:
        """Generate a streamed chat response."""
        chunks: list[str] = []
        stream = self.client.chat.completions.create(
            model=model,
            messages=messages,
            temperature=temperature,
            max_tokens=max_tokens,
            stream=True,
        )
        for event in stream:
            if not event.choices:
                continue
            delta = event.choices[0].delta
            piece = self._text_from_content(getattr(delta, "content", None))
            if piece:
                chunks.append(piece)
        return self._visible_final_text("".join(chunks))

    @classmethod
    def _text_from_responses_json(cls, payload: dict[str, Any]) -> str:
        """Extract visible text from a Responses payload."""
        direct = payload.get("output_text")
        if isinstance(direct, str) and direct.strip():
            return cls._visible_final_text(direct)

        parts: list[str] = []
        for item in payload.get("output", []) or []:
            if not isinstance(item, dict):
                continue
            if item.get("type") not in {None, "message"}:
                continue
            for content in item.get("content", []) or []:
                if isinstance(content, str):
                    parts.append(content)
                    continue
                if not isinstance(content, dict):
                    continue
                if content.get("type") in {"output_text", "text", None}:
                    text = content.get("text") or content.get("output_text")
                    if isinstance(text, str):
                        parts.append(text)
        return cls._visible_final_text("\n".join(parts))

    def _request_responses_api(
        self,
        *,
        model: str,
        messages: list[dict[str, str]],
        temperature: float,
        max_tokens: int,
    ) -> str:
        """Call LM Studio's Responses endpoint."""
        if not settings.use_responses_fallback:
            return ""

        url = f"{self.base_url}/responses"
        headers = {"Content-Type": "application/json"}
        if self.api_key:
            headers["Authorization"] = f"Bearer {self.api_key}"

        body: dict[str, Any] = {
            "model": model,
            "input": messages,
            "temperature": temperature,
            "max_output_tokens": max_tokens,
        }

        with httpx.Client(timeout=settings.lmstudio_request_timeout) as client:
            response = client.post(url, headers=headers, json=body)
            response.raise_for_status()
            data = response.json()
        return self._text_from_responses_json(data)

    def chat(
        self,
        messages: list[dict[str, str]],
        temperature: float | None = None,
        max_tokens: int | None = None,
    ) -> str:
        model = self.model_id()
        temp = settings.temperature if temperature is None else temperature
        token_limit = settings.max_tokens if max_tokens is None else max_tokens
        prepared = self._prepare_messages(model, messages)

        diagnostics: list[str] = []

        try:
            completion = self._request_chat(
                model=model,
                messages=prepared,
                temperature=temp,
                max_tokens=token_limit,
            )
            if completion.choices:
                raw = self._text_from_content(completion.choices[0].message.content)
                answer = self._visible_final_text(raw)
                if answer:
                    return answer
            diagnostics.append("chat-completions returned no final content")
        except Exception as exc:
            diagnostics.append(f"chat-completions error: {type(exc).__name__}: {exc}")

        retry_messages = self._compact_messages(prepared, settings.retry_context_chars)
        retry_messages.append(
            {
                "role": "user",
                "content": (
                    "/no_think\n"
                    "Return the final answer now using only the evidence already provided. "
                    "Do not output analysis or a thinking block. Keep the answer concise and cite [S#] labels."
                ),
            }
        )
        retry_limit = max(token_limit, settings.empty_response_retry_tokens)
        try:
            answer = self._request_chat_stream(
                model=model,
                messages=retry_messages,
                temperature=min(temp, 0.2),
                max_tokens=retry_limit,
            )
            if answer:
                return answer
            diagnostics.append("streaming retry returned no final content")
        except Exception as exc:
            diagnostics.append(f"streaming retry error: {type(exc).__name__}: {exc}")

        try:
            answer = self._request_responses_api(
                model=model,
                messages=retry_messages,
                temperature=min(temp, 0.2),
                max_tokens=retry_limit,
            )
            if answer:
                return answer
            diagnostics.append("responses endpoint returned no final content")
        except Exception as exc:
            diagnostics.append(f"responses endpoint error: {type(exc).__name__}: {exc}")

        hint = (
            "The configured model appears to be thinking-only. "
            if self._is_thinking_only_model(model)
            else ""
        )
        raise EmptyModelResponseError(
            hint
            + "LM Studio did not return visible final answer text after all generation fallbacks. "
            + " | ".join(diagnostics)
        )

    def quick_test(self) -> tuple[bool, str]:
        try:
            answer = self.chat(
                messages=[
                    {"role": "system", "content": "Return a short visible final answer."},
                    {"role": "user", "content": "Reply with exactly: MODEL_OK"},
                ],
                temperature=0.0,
                max_tokens=64,
            )
            if answer:
                return True, f"Model generation works: {answer[:120]}"
            return False, "Model returned no visible final text."
        except Exception as exc:
            return False, str(exc)

    def ping(self) -> tuple[bool, str]:
        try:
            model_id = self.model_id()
            return True, f"{settings.model_name} is ready ({model_id})."
        except Exception as exc:
            return False, str(exc)
