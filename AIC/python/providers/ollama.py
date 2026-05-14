"""
AIC Ollama Provider
Adapter for local Ollama models.
Implements BaseProvider interface.
No API key required — local endpoint only.
"""

import httpx

from providers.base import BaseProvider, ProviderCallError


class OllamaProvider(BaseProvider):
    """Ollama local model provider adapter."""

    DEFAULT_ENDPOINT = "http://localhost:11434"

    def __init__(self, model: str, api_key: str = "", endpoint: str = ""):
        super().__init__(model, api_key)
        self.endpoint = endpoint.rstrip("/") if endpoint else self.DEFAULT_ENDPOINT

    @property
    def provider_name(self) -> str:
        return "ollama"

    def generate(self, prompt: str) -> str:
        """
        Send prompt to local Ollama instance and return generated code.
        No API key required for Ollama.
        """
        url = f"{self.endpoint}/api/generate"

        payload = {
            "model": self.model,
            "prompt": prompt,
            "stream": False,
        }

        try:
            response = httpx.post(
                url,
                json=payload,
                timeout=300.0,  # Local models can be slower
            )
            response.raise_for_status()
            data = response.json()

            text = data.get("response", "")
            if not text:
                raise ProviderCallError(self.provider_name, "Empty response from Ollama")

            return text

        except httpx.HTTPStatusError as e:
            raise ProviderCallError(
                self.provider_name,
                f"HTTP {e.response.status_code} — is Ollama running at {self.endpoint}?"
            )
        except httpx.TimeoutException:
            raise ProviderCallError(
                self.provider_name,
                "Request timed out — local model may need more time"
            )
        except httpx.ConnectError:
            raise ProviderCallError(
                self.provider_name,
                f"Cannot connect to Ollama at {self.endpoint}\n"
                "Is Ollama running? Try: ollama serve"
            )
