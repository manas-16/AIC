"""
AIC Claude Provider
Adapter for Anthropic Claude API.
Implements BaseProvider interface.
"""

import httpx

from providers.base import BaseProvider, ProviderCallError


class ClaudeProvider(BaseProvider):
    """Anthropic Claude provider adapter."""

    API_URL = "https://api.anthropic.com/v1/messages"
    API_VERSION = "2023-06-01"

    @property
    def provider_name(self) -> str:
        return "claude"

    def generate(self, prompt: str) -> str:
        """
        Send prompt to Claude API and return generated code.
        Uses httpx for HTTP — consistent with python.intent dependency spec.
        API key never logged or included in error messages.
        """
        headers = {
            "Content-Type": "application/json",
            "x-api-key": self.api_key,
            "anthropic-version": self.API_VERSION,
        }

        payload = {
            "model": self.model,
            "max_tokens": 4096,
            "messages": [
                {
                    "role": "user",
                    "content": prompt,
                }
            ],
        }

        try:
            response = httpx.post(
                self.API_URL,
                headers=headers,
                json=payload,
                timeout=120.0,
            )
            response.raise_for_status()
            data = response.json()

            content_blocks = data.get("content", [])
            code_blocks = [
                block["text"]
                for block in content_blocks
                if block.get("type") == "text"
            ]

            if not code_blocks:
                raise ProviderCallError(self.provider_name, "Empty response from API")

            return "\n".join(code_blocks)

        except httpx.HTTPStatusError as e:
            # Never include API key in error message
            raise ProviderCallError(
                self.provider_name,
                f"HTTP {e.response.status_code} — check your API key and model name"
            )
        except httpx.TimeoutException:
            raise ProviderCallError(self.provider_name, "Request timed out after 120 seconds")
        except httpx.RequestError as e:
            raise ProviderCallError(self.provider_name, f"Connection error: {type(e).__name__}")
