"""
Ollama-backed LLMProvider (default: qwen2.5:1.5b on a local Ollama server).

Uses only the standard library (urllib) so it adds no new dependency to the
backend. Configurable entirely via environment variables so switching host
or model needs no code change:

    OLLAMA_HOST    default http://localhost:11434
    OLLAMA_MODEL   default qwen2.5:1.5b
    OLLAMA_TIMEOUT default 120 (seconds, per chat request)
"""

import json
import os
import urllib.error
import urllib.request
from typing import Dict, List, Optional

from services.llm.base import LLMProvider, LLMProviderError


class OllamaProvider(LLMProvider):
    """Talks to a local Ollama server's /api/chat endpoint."""

    def __init__(
        self,
        host: Optional[str] = None,
        model: Optional[str] = None,
        timeout: Optional[float] = None,
    ):
        self.host = (host or os.environ.get("OLLAMA_HOST", "http://localhost:11434")).rstrip("/")
        self.model = model or os.environ.get("OLLAMA_MODEL", "qwen2.5:1.5b")
        try:
            self.timeout = timeout if timeout is not None else float(os.environ.get("OLLAMA_TIMEOUT", "120"))
        except ValueError:
            self.timeout = 120.0

    @property
    def name(self) -> str:
        return f"ollama:{self.model}"

    def is_available(self) -> bool:
        try:
            req = urllib.request.Request(f"{self.host}/api/tags", method="GET")
            with urllib.request.urlopen(req, timeout=5) as resp:
                return 200 <= resp.status < 300
        except Exception:
            return False

    def chat(self, messages: List[Dict[str, str]]) -> str:
        payload = json.dumps({
            "model": self.model,
            "messages": messages,
            "stream": False,
        }).encode("utf-8")

        req = urllib.request.Request(
            f"{self.host}/api/chat",
            data=payload,
            headers={"Content-Type": "application/json"},
            method="POST",
        )

        try:
            with urllib.request.urlopen(req, timeout=self.timeout) as resp:
                body = json.loads(resp.read().decode("utf-8"))
        except urllib.error.HTTPError as e:
            raise LLMProviderError(self._http_error_message(e)) from e
        except urllib.error.URLError as e:
            raise LLMProviderError(
                f"Could not reach Ollama at {self.host} - is it running? "
                f"Start it with `ollama serve` and pull the model with "
                f"`ollama pull {self.model}`. ({e.reason})"
            ) from e
        except TimeoutError as e:
            raise LLMProviderError(
                f"The assistant took too long to respond (over {self.timeout:.0f}s). Please try again."
            ) from e
        except Exception as e:
            raise LLMProviderError(f"Unexpected error talking to Ollama: {e}") from e

        content = (body.get("message") or {}).get("content", "").strip()
        if not content:
            raise LLMProviderError("The assistant returned an empty response. Please try again.")
        return content

    def _http_error_message(self, err: "urllib.error.HTTPError") -> str:
        """Turn Ollama's JSON error body into a friendly message (e.g. model not pulled)."""
        detail = ""
        try:
            detail = (json.loads(err.read().decode("utf-8")) or {}).get("error", "")
        except Exception:
            pass
        if err.code == 404 or "not found" in detail.lower():
            return (
                f"The model '{self.model}' isn't available on Ollama. "
                f"Pull it first with `ollama pull {self.model}`."
            )
        return f"Ollama returned an error (HTTP {err.code}): {detail or err.reason}"
