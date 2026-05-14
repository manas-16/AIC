"""
AIC Gemini Provider
Adapter for Google Gemini API.
Implements BaseProvider interface.
"""

import httpx

from providers.base import BaseProvider, ProviderCallError


class GeminiProvider(BaseProvider):
    """Google Gemini provider adapter."""

    API_URL = "https://generativelanguage.googleapis.com/v1beta/models/{model}:generateContent"

    @property
    def provider_name(self) -> str:
        return "gemini"

    def generate(self, prompt: str) -> str:
        """
        Send prompt to Gemini API and return generated code.
        API key passed as query parameter per Gemini API spec.
        API key never logged or included in error messages.
        """
        url = self.API_URL.format(model=self.model)

        payload = {
            "contents": [
                {
                    "parts": [{"text": prompt}]
                }
            ],
            "generationConfig": {
                "maxOutputTokens": 4096,
            }
        }

        try:
            response = httpx.post(
                url,
                params={"key": self.api_key},
                json=payload,
                timeout=120.0,
            )
            response.raise_for_status()
            data = response.json()

            candidates = data.get("candidates", [])
            if not candidates:
                raise ProviderCallError(self.provider_name, "Empty response from API")

            parts = candidates[0].get("content", {}).get("parts", [])
            text_parts = [p["text"] for p in parts if "text" in p]

            if not text_parts:
                raise ProviderCallError(self.provider_name, "No text in response")

            return "\n".join(text_parts)

        except httpx.HTTPStatusError as e:
            raise ProviderCallError(
                self.provider_name,
                f"HTTP {e.response.status_code} — check your API key and model name"
            )
        except httpx.TimeoutException:
            raise ProviderCallError(self.provider_name, "Request timed out after 120 seconds")
        except httpx.RequestError as e:
            raise ProviderCallError(self.provider_name, f"Connection error: {type(e).__name__}")
