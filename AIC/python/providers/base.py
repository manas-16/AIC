"""
AIC Base Provider
Abstract interface for all AI provider adapters.
All providers implement this interface — swapping providers
requires only changing aic.config.json, nothing else.
"""

from abc import ABC, abstractmethod


class ProviderCallError(Exception):
    """Raised when an AI provider call fails."""
    def __init__(self, provider: str, reason: str):
        self.provider = provider
        self.reason = reason
        super().__init__(f"Provider call failed [{provider}]: {reason}")


class BaseProvider(ABC):
    """Abstract base class for all AI provider adapters."""

    def __init__(self, model: str, api_key: str):
        self.model = model
        self.api_key = api_key

    @abstractmethod
    def generate(self, prompt: str) -> str:
        """
        Send prompt to AI provider and return generated code.
        Raises ProviderCallError on any failure.
        API key must never appear in error messages or logs.
        """
        pass

    @property
    @abstractmethod
    def provider_name(self) -> str:
        """Return the provider name for display and lockfile recording."""
        pass
