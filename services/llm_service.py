"""
services/llm_service.py
========================
Pluggable LLM service supporting Ollama, OpenAI, and Google Gemini.
Switch providers by setting LLM_PROVIDER in .env.

All providers implement the same interface:
  generate(system_prompt, user_prompt) -> str
  stream(system_prompt, user_prompt) -> Iterator[str]
"""

from __future__ import annotations

import time
from typing import Iterator, Optional

import config
from utils.logger import logger


# ─── Base Interface ───────────────────────────────────────────────────────────

class BaseLLMProvider:
    """Abstract base for LLM providers."""

    def generate(self, system_prompt: str, user_prompt: str) -> str:
        raise NotImplementedError

    def stream(self, system_prompt: str, user_prompt: str) -> Iterator[str]:
        raise NotImplementedError

    def is_available(self) -> tuple[bool, str]:
        """Check if the provider/model is reachable. Returns (ok, error_msg)."""
        raise NotImplementedError


# ─── Ollama Provider ──────────────────────────────────────────────────────────

class OllamaProvider(BaseLLMProvider):
    """
    Ollama local LLM provider.
    Requires Ollama to be running: https://ollama.com
    """

    def __init__(self) -> None:
        try:
            import ollama as ollama_sdk
            self._sdk = ollama_sdk
        except ImportError:
            raise ImportError("Install the ollama package: pip install ollama")

        self.model = config.OLLAMA_MODEL
        self.base_url = config.OLLAMA_BASE_URL
        self.timeout = config.OLLAMA_TIMEOUT
        logger.info(
            f"OllamaProvider initialised | model={self.model} | url={self.base_url}"
        )

    def generate(self, system_prompt: str, user_prompt: str) -> str:
        """Generate a complete response from Ollama."""
        try:
            response = self._sdk.chat(
                model=self.model,
                messages=[
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": user_prompt},
                ],
                options={
                    "temperature": config.LLM_TEMPERATURE,
                    "num_predict": config.LLM_MAX_TOKENS,
                },
            )
            return response["message"]["content"].strip()
        except Exception as e:
            logger.error(f"Ollama generate error: {e}")
            raise

    def stream(self, system_prompt: str, user_prompt: str) -> Iterator[str]:
        """Stream tokens from Ollama."""
        try:
            stream = self._sdk.chat(
                model=self.model,
                messages=[
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": user_prompt},
                ],
                options={
                    "temperature": config.LLM_TEMPERATURE,
                    "num_predict": config.LLM_MAX_TOKENS,
                },
                stream=True,
            )
            for chunk in stream:
                token = chunk["message"]["content"]
                if token:
                    yield token
        except Exception as e:
            logger.error(f"Ollama stream error: {e}")
            raise

    def is_available(self) -> tuple[bool, str]:
        """Ping Ollama to verify it's running and the model is pulled."""
        try:
            import httpx

            r = httpx.get(f"{self.base_url}/api/tags", timeout=5)
            if r.status_code != 200:
                return False, f"Ollama returned HTTP {r.status_code}"
            models = [m["name"] for m in r.json().get("models", [])]
            # Accept both "llama3" and "llama3:latest"
            model_base = self.model.split(":")[0]
            found = any(m.startswith(model_base) for m in models)
            if not found:
                return (
                    False,
                    f"Model '{self.model}' not found. "
                    f"Run: ollama pull {self.model}\n"
                    f"Available: {', '.join(models) or 'none'}",
                )
            return True, ""
        except Exception as e:
            return False, f"Cannot reach Ollama at {self.base_url}: {e}"


# ─── OpenAI Provider ──────────────────────────────────────────────────────────

class OpenAIProvider(BaseLLMProvider):
    """OpenAI GPT provider (optional)."""

    def __init__(self) -> None:
        try:
            import openai

            self._client = openai.OpenAI(api_key=config.OPENAI_API_KEY)
        except ImportError:
            raise ImportError("Install openai: pip install openai")
        self.model = config.OPENAI_MODEL
        logger.info(f"OpenAIProvider initialised | model={self.model}")

    def generate(self, system_prompt: str, user_prompt: str) -> str:
        response = self._client.chat.completions.create(
            model=self.model,
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_prompt},
            ],
            temperature=config.LLM_TEMPERATURE,
            max_tokens=config.LLM_MAX_TOKENS,
        )
        return response.choices[0].message.content.strip()

    def stream(self, system_prompt: str, user_prompt: str) -> Iterator[str]:
        stream = self._client.chat.completions.create(
            model=self.model,
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_prompt},
            ],
            temperature=config.LLM_TEMPERATURE,
            max_tokens=config.LLM_MAX_TOKENS,
            stream=True,
        )
        for chunk in stream:
            delta = chunk.choices[0].delta.content
            if delta:
                yield delta

    def is_available(self) -> tuple[bool, str]:
        if not config.OPENAI_API_KEY:
            return False, "OPENAI_API_KEY not set in .env"
        return True, ""


# ─── Gemini Provider ──────────────────────────────────────────────────────────

class GeminiProvider(BaseLLMProvider):
    """Google Gemini provider (optional)."""

    def __init__(self) -> None:
        try:
            import google.generativeai as genai

            genai.configure(api_key=config.GEMINI_API_KEY)
            self._model = genai.GenerativeModel(config.GEMINI_MODEL)
        except ImportError:
            raise ImportError(
                "Install google-generativeai: pip install google-generativeai"
            )
        logger.info(f"GeminiProvider initialised | model={config.GEMINI_MODEL}")

    def generate(self, system_prompt: str, user_prompt: str) -> str:
        full_prompt = f"{system_prompt}\n\n{user_prompt}"
        response = self._model.generate_content(
            full_prompt,
            generation_config={
                "temperature": config.LLM_TEMPERATURE,
                "max_output_tokens": config.LLM_MAX_TOKENS,
            },
        )
        return response.text.strip()

    def stream(self, system_prompt: str, user_prompt: str) -> Iterator[str]:
        full_prompt = f"{system_prompt}\n\n{user_prompt}"
        response = self._model.generate_content(
            full_prompt,
            generation_config={
                "temperature": config.LLM_TEMPERATURE,
                "max_output_tokens": config.LLM_MAX_TOKENS,
            },
            stream=True,
        )
        for chunk in response:
            if chunk.text:
                yield chunk.text

    def is_available(self) -> tuple[bool, str]:
        if not config.GEMINI_API_KEY:
            return False, "GEMINI_API_KEY not set in .env"
        return True, ""


# ─── Factory ──────────────────────────────────────────────────────────────────

class LLMService:
    """
    LLM service factory.
    Instantiates the correct provider based on LLM_PROVIDER config.
    """

    def __init__(self) -> None:
        self._provider: Optional[BaseLLMProvider] = None
        self._provider_name: str = ""
        self._load_provider()

    def _load_provider(self) -> None:
        """Load the configured LLM provider."""
        provider = config.LLM_PROVIDER.lower()
        logger.info(f"Loading LLM provider: {provider}")
        try:
            if provider == "ollama":
                self._provider = OllamaProvider()
            elif provider == "openai":
                self._provider = OpenAIProvider()
            elif provider == "gemini":
                self._provider = GeminiProvider()
            else:
                raise ValueError(f"Unknown LLM_PROVIDER: '{provider}'")
            self._provider_name = provider
        except Exception as e:
            logger.error(f"Failed to load LLM provider '{provider}': {e}")
            raise

    def generate(
        self,
        system_prompt: str,
        user_prompt: str,
        retries: int = 2,
    ) -> str:
        """
        Generate a response with retry logic.

        Args:
            system_prompt: System instruction for the LLM.
            user_prompt: User message.
            retries: Number of retry attempts on failure.

        Returns:
            Generated text string.
        """
        for attempt in range(retries + 1):
            try:
                start = time.time()
                result = self._provider.generate(system_prompt, user_prompt)  # type: ignore[union-attr]
                elapsed = int((time.time() - start) * 1000)
                logger.info(
                    f"LLM generate | provider={self._provider_name} | "
                    f"tokens≈{len(result)//4} | time={elapsed}ms"
                )
                return result
            except Exception as e:
                if attempt < retries:
                    logger.warning(f"LLM attempt {attempt+1} failed: {e} — retrying")
                    time.sleep(1.0 * (attempt + 1))
                else:
                    logger.error(f"LLM generate failed after {retries+1} attempts: {e}")
                    raise

    def stream(
        self, system_prompt: str, user_prompt: str
    ) -> Iterator[str]:
        """Stream tokens from the LLM provider."""
        return self._provider.stream(system_prompt, user_prompt)  # type: ignore[union-attr]

    def is_available(self) -> tuple[bool, str]:
        """Check if the LLM provider is reachable."""
        return self._provider.is_available()  # type: ignore[union-attr]

    @property
    def provider_name(self) -> str:
        return self._provider_name

    @property
    def model_name(self) -> str:
        if self._provider_name == "ollama":
            return config.OLLAMA_MODEL
        if self._provider_name == "openai":
            return config.OPENAI_MODEL
        if self._provider_name == "gemini":
            return config.GEMINI_MODEL
        return "unknown"


# ─── Singleton ────────────────────────────────────────────────────────────────
llm_service = LLMService()
