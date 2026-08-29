"""LLM access for the AI Copilot — provider-agnostic.

The chatbot previously spoke Gemini's REST shape inline. That made switching models a
code edit rather than a config change, which is the wrong shape for something a
deployment might need to choose per environment (or per data-residency policy).

Everything now goes through `get_llm().complete(prompt)`. Providers differ only in three
places — endpoint, auth, and where the text sits in the response JSON — so each is a
small class and the caller sees none of it.

    Selection order
      1. LLM_PROVIDER if set explicitly
      2. otherwise, whichever key is present (Groq preferred — it is the faster of the two)
      3. otherwise NullProvider, and the Copilot falls back to its local SQL compiler

A provider NEVER raises into the request. A failure returns None and the caller degrades
to the local answer path, because a chat panel erroring out is worse than a plainer answer.

No SDKs: Groq is OpenAI-compatible and Gemini is plain REST, so `requests` (already a
dependency) covers both. Nothing new to install.
"""
import logging
import os
import re
import sys
from typing import Protocol

import requests

sys.path.append(os.path.join(os.path.dirname(__file__), ".."))

logger = logging.getLogger("ksp-llm")

DEFAULT_TIMEOUT = 20


def _redact(text: object, *secrets: str) -> str:
    """Scrub API keys out of anything on its way to a log.

    Gemini passes its key in the QUERY STRING, and `requests` quotes the full URL
    in its exception messages -- so an ordinary connection error would otherwise
    write the key into the application log in plaintext. Logs get shipped,
    screenshotted and pasted into bug reports, so they are treated as public.

    Also catches key-shaped tokens generically, in case a provider echoes one back
    in an error body.
    """
    out = str(text)
    for secret in secrets:
        if secret and len(secret) >= 8:
            out = out.replace(secret, "***REDACTED***")
    # Belt and braces: anything that looks like a key= parameter or a bearer token.
    out = re.sub(r"(key=)[A-Za-z0-9_\-]{8,}", r"***REDACTED***", out)
    out = re.sub(r"(Bearer\s+)[A-Za-z0-9_\-]{8,}", r"***REDACTED***", out)
    out = re.sub(r"(gsk_|AIza)[A-Za-z0-9_\-]{8,}", "***REDACTED***", out)
    return out


class LLMProvider(Protocol):
    name: str
    model: str

    def available(self) -> bool: ...
    def complete(self, prompt: str) -> str | None: ...


class NullProvider:
    """No key configured. Says so once, then stays quiet."""

    name = "none"
    model = "-"

    def available(self) -> bool:
        return False

    def complete(self, prompt: str) -> str | None:
        return None


class GroqProvider:
    """Groq — OpenAI-compatible chat completions.

    Chosen default model is a general instruct model; Groq rotates its lineup faster
    than most, so it is configurable via GROQ_MODEL. If a model is retired the API
    returns a 400 naming it, which is surfaced in the log rather than swallowed.
    """

    name = "groq"
    ENDPOINT = "https://api.groq.com/openai/v1/chat/completions"

    def __init__(self, api_key: str, model: str):
        self.api_key = api_key
        self.model = model

    def available(self) -> bool:
        return bool(self.api_key)

    def complete(self, prompt: str) -> str | None:
        if not self.available():
            return None
        try:
            response = requests.post(
                self.ENDPOINT,
                headers={
                    "Authorization": f"Bearer {self.api_key}",
                    "Content-Type": "application/json",
                },
                json={
                    "model": self.model,
                    "messages": [{"role": "user", "content": prompt}],
                    "temperature": 0.3,     # factual register; this answers on police data
                    "max_tokens": 1024,
                },
                timeout=DEFAULT_TIMEOUT,
            )
            if response.status_code == 200:
                return response.json()["choices"][0]["message"]["content"]
            # Surface the provider's own explanation -- a retired model or a bad key
            # both show up here and are otherwise invisible.
            logger.warning("Groq returned %s: %s", response.status_code,
                           _redact(response.text[:300], self.api_key))
        except Exception as exc:
            logger.warning("Groq request failed: %s: %s", type(exc).__name__,
                           _redact(exc, self.api_key))
        return None


class GeminiProvider:
    """Google Gemini — the original path, preserved verbatim in behaviour."""

    name = "gemini"

    def __init__(self, api_key: str, model: str):
        self.api_key = api_key
        self.model = model

    def available(self) -> bool:
        return bool(self.api_key)

    def complete(self, prompt: str) -> str | None:
        if not self.available():
            return None
        try:
            url = (f"https://generativelanguage.googleapis.com/v1beta/models/"
                   f"{self.model}:generateContent?key={self.api_key}")
            response = requests.post(
                url, json={"contents": [{"parts": [{"text": prompt}]}]}, timeout=DEFAULT_TIMEOUT
            )
            if response.status_code == 200:
                return response.json()["candidates"][0]["content"]["parts"][0]["text"]
            logger.warning("Gemini returned %s: %s", response.status_code,
                           _redact(response.text[:300], self.api_key))
        except Exception as exc:
            logger.warning("Gemini request failed: %s: %s", type(exc).__name__,
                           _redact(exc, self.api_key))
        return None


class OllamaProvider:
    """Local Ollama. Needs no key, and nothing leaves the machine — the option to reach
    for if crime data may not cross jurisdictions."""

    name = "ollama"

    def __init__(self, base_url: str, model: str):
        self.base_url = base_url.rstrip("/")
        self.model = model

    def available(self) -> bool:
        return bool(self.base_url)

    def complete(self, prompt: str) -> str | None:
        try:
            response = requests.post(
                f"{self.base_url}/api/generate",
                json={"model": self.model, "prompt": prompt, "stream": False},
                timeout=60,     # local generation on CPU is slow but free
            )
            if response.status_code == 200:
                return response.json().get("response")
            logger.warning("Ollama returned %s: %s", response.status_code, _redact(response.text[:300]))
        except Exception as exc:
            logger.warning("Ollama request failed: %s: %s", type(exc).__name__, _redact(exc))
        return None


_llm: LLMProvider | None = None


def _build() -> LLMProvider:
    from app.config import settings

    groq_key = getattr(settings, "GROQ_API_KEY", "") or ""
    gemini_key = getattr(settings, "GEMINI_API_KEY", "") or ""
    choice = (getattr(settings, "LLM_PROVIDER", "auto") or "auto").lower()

    if choice == "auto":
        # Prefer whichever is actually configured; Groq first, being the faster.
        choice = "groq" if groq_key else ("gemini" if gemini_key else "none")

    if choice == "groq":
        provider = GroqProvider(groq_key, getattr(settings, "GROQ_MODEL", "openai/gpt-oss-120b"))
    elif choice == "gemini":
        provider = GeminiProvider(gemini_key, getattr(settings, "GEMINI_MODEL", "gemini-1.5-flash"))
    elif choice == "ollama":
        provider = OllamaProvider(getattr(settings, "OLLAMA_BASE_URL", "http://localhost:11434"),
                                  getattr(settings, "OLLAMA_MODEL", "llama3"))
    else:
        provider = NullProvider()

    if provider.available():
        logger.info("AI Copilot using %s (model=%s).", provider.name, provider.model)
    else:
        logger.info("AI Copilot has no LLM configured — answering from the local SQL "
                    "compiler only. Set GROQ_API_KEY or GEMINI_API_KEY to enable free-form replies.")
    return provider


def get_llm() -> LLMProvider:
    global _llm
    if _llm is None:
        _llm = _build()
    return _llm


def reset_llm() -> None:
    """Drops the cached provider so a config change takes effect (used by tests)."""
    global _llm
    _llm = None


def describe() -> dict:
    """Which provider is live — for a health/diagnostics view."""
    llm = get_llm()
    return {"provider": llm.name, "model": llm.model, "available": llm.available()}


# ─────────────────────────────────────────────────────────────────────────────
# Multi-turn chat
#
# `complete()` above answers a single prompt. The Copilot routes
# (app/api/chatbot_grok.py, app/api/grok_insights.py) need a system prompt plus a
# conversation, and each had grown its own private copy of the HTTP call --
# reading a differently-spelled env var (GROK_API_KEY) straight from os.environ,
# hardcoding a model name that contradicted GROQ_MODEL, echoing the provider's
# raw error body back to the caller, and catching only RequestException so a
# non-JSON 200 became an unhandled 500.
#
# `chat()` is that call, once, here: same credential resolution, same redaction,
# same timeout, same error contract as the rest of this module.
# ─────────────────────────────────────────────────────────────────────────────


class LLMUnavailable(RuntimeError):
    """No provider is configured, or the configured one refused the request.

    Carries a `status` hint so a route can map it to 503 (nothing configured)
    versus 502 (provider reachable but failing) without inspecting strings.
    """

    def __init__(self, message: str, status: int = 503):
        super().__init__(message)
        self.status = status


def _extract_openai_text(data: object) -> str:
    """Pulls the assistant text out of an OpenAI-compatible response.

    Validates the shape instead of indexing blindly: a provider can return HTTP
    200 with an error object, or an empty `choices` array, and
    data["choices"][0]["message"]["content"] would raise KeyError/IndexError
    outside any handler.
    """
    if not isinstance(data, dict):
        raise LLMUnavailable("AI provider returned an unexpected response.", 502)
    choices = data.get("choices")
    if not isinstance(choices, list) or not choices:
        raise LLMUnavailable("AI provider returned no completion.", 502)
    message = choices[0].get("message") if isinstance(choices[0], dict) else None
    content = message.get("content") if isinstance(message, dict) else None
    if not content:
        # Reasoning models (the default openai/gpt-oss-120b is one) spend the token
        # budget on a hidden `reasoning` field first and only then emit `content`.
        # Too small a max_tokens therefore returns finish_reason="length" with an
        # EMPTY content string rather than a truncated answer -- which reads as
        # "the AI silently returned nothing". Name the actual cause.
        if choices[0].get("finish_reason") == "length":
            raise LLMUnavailable(
                "The AI model used its entire token budget before producing an "
                "answer. Raise max_tokens, or set GROQ_MODEL to a non-reasoning "
                "model.", 502,
            )
        raise LLMUnavailable("AI provider returned an empty completion.", 502)
    return content


def chat(system_prompt: str, messages: list[dict], *, max_tokens: int = 700,
         temperature: float = 0.5) -> str:
    """Runs a system prompt + conversation through the configured provider.

    Raises LLMUnavailable on any failure -- callers translate that into an HTTP
    status. Never leaks the provider's raw error body or the API key.
    """
    llm = get_llm()
    if not llm.available():
        raise LLMUnavailable(
            "The AI Copilot has no language model configured. Set GROQ_API_KEY "
            "(or GEMINI_API_KEY) and restart.", 503,
        )

    # Only user/assistant turns are forwarded. A caller-supplied "system" turn
    # would be appended AFTER the trusted system prompt, and OpenAI-compatible
    # APIs honour the later one -- letting a client replace the guardrails with
    # its own instructions.
    safe_messages = [
        {"role": m["role"], "content": m["content"]}
        for m in messages
        if isinstance(m, dict) and m.get("role") in ("user", "assistant") and m.get("content")
    ]

    if isinstance(llm, GroqProvider):
        return _groq_chat(llm, system_prompt, safe_messages, max_tokens, temperature)
    if isinstance(llm, OllamaProvider):
        return _ollama_chat(llm, system_prompt, safe_messages, temperature)
    if isinstance(llm, GeminiProvider):
        return _gemini_chat(llm, system_prompt, safe_messages, max_tokens, temperature)

    raise LLMUnavailable("No usable AI provider is configured.", 503)


def _groq_chat(llm: GroqProvider, system_prompt: str, messages: list[dict],
               max_tokens: int, temperature: float) -> str:
    try:
        response = requests.post(
            llm.ENDPOINT,
            headers={"Authorization": f"Bearer {llm.api_key}",
                     "Content-Type": "application/json"},
            json={
                "model": llm.model,
                "messages": [{"role": "system", "content": system_prompt}] + messages,
                "temperature": temperature,
                "max_tokens": max_tokens,
            },
            timeout=DEFAULT_TIMEOUT,
        )
    except Exception as exc:
        logger.warning("Groq chat request failed: %s: %s", type(exc).__name__,
                       _redact(exc, llm.api_key))
        raise LLMUnavailable("The AI provider could not be reached.", 502) from exc

    if response.status_code != 200:
        # Logged in full server-side; the caller gets the status only. The raw body
        # was previously returned to the client, and these routes are reachable by
        # any signed-in user.
        logger.warning("Groq chat returned %s: %s", response.status_code,
                       _redact(response.text[:300], llm.api_key))
        raise LLMUnavailable(
            f"The AI provider rejected the request (upstream status {response.status_code}).",
            502)

    try:
        data = response.json()
    except ValueError as exc:
        logger.warning("Groq chat returned non-JSON body: %s",
                       _redact(response.text[:300], llm.api_key))
        raise LLMUnavailable("The AI provider returned an unreadable response.", 502) from exc

    return _extract_openai_text(data)


def _ollama_chat(llm: OllamaProvider, system_prompt: str, messages: list[dict],
                 temperature: float) -> str:
    try:
        response = requests.post(
            f"{llm.base_url}/api/chat",
            json={
                "model": llm.model,
                "messages": [{"role": "system", "content": system_prompt}] + messages,
                "stream": False,
                "options": {"temperature": temperature},
            },
            timeout=60,
        )
        if response.status_code != 200:
            logger.warning("Ollama chat returned %s: %s", response.status_code,
                           _redact(response.text[:300]))
            raise LLMUnavailable("The local AI model rejected the request.", 502)
        text = (response.json() or {}).get("message", {}).get("content")
    except LLMUnavailable:
        raise
    except Exception as exc:
        logger.warning("Ollama chat failed: %s: %s", type(exc).__name__, _redact(exc))
        raise LLMUnavailable("The local AI model could not be reached.", 502) from exc

    if not text:
        raise LLMUnavailable("The local AI model returned an empty response.", 502)
    return text


def _gemini_chat(llm: GeminiProvider, system_prompt: str, messages: list[dict],
                 max_tokens: int, temperature: float) -> str:
    """Gemini has no `system` role -- the instruction goes in systemInstruction, and
    assistant turns are spelled "model"."""
    contents = [
        {"role": ("model" if m["role"] == "assistant" else "user"),
         "parts": [{"text": m["content"]}]}
        for m in messages
    ]
    if not contents:
        contents = [{"role": "user", "parts": [{"text": " "}]}]

    url = (f"https://generativelanguage.googleapis.com/v1beta/models/"
           f"{llm.model}:generateContent?key={llm.api_key}")
    try:
        response = requests.post(
            url,
            json={
                "systemInstruction": {"parts": [{"text": system_prompt}]},
                "contents": contents,
                "generationConfig": {"temperature": temperature,
                                     "maxOutputTokens": max_tokens},
            },
            timeout=DEFAULT_TIMEOUT,
        )
        if response.status_code != 200:
            logger.warning("Gemini chat returned %s: %s", response.status_code,
                           _redact(response.text[:300], llm.api_key))
            raise LLMUnavailable(
                f"The AI provider rejected the request (upstream status {response.status_code}).",
                502)
        data = response.json()
        return data["candidates"][0]["content"]["parts"][0]["text"]
    except LLMUnavailable:
        raise
    except Exception as exc:
        logger.warning("Gemini chat failed: %s: %s", type(exc).__name__,
                       _redact(exc, llm.api_key))
        raise LLMUnavailable("The AI provider could not be reached.", 502) from exc
