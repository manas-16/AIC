"""
AIC Config Model
Data model for config.json
"""

import json
import os
from dataclasses import dataclass
from pathlib import Path
from typing import Optional


@dataclass
class AICConfig:
    """Represents the AI provider configuration from config.json."""
    provider: str
    model: str
    api_key: str
    endpoint: Optional[str] = None  # for Ollama local endpoint

    @classmethod
    def load(cls, project_root: Path) -> "AICConfig":
        """
        Load config from .aic/config.json.
        Resolves environment variable references like ${ANTHROPIC_API_KEY}.
        Raises ProviderNotConfiguredError if required fields are missing.
        """
        from core.exceptions import ProviderNotConfiguredError

        config_path = project_root / ".aic" / "config.json"
        if not config_path.exists():
            raise ProviderNotConfiguredError()

        with open(config_path, encoding="utf-8") as f:
            data = json.load(f)

        ai_config = data.get("ai", {})
        provider = ai_config.get("provider", "").strip()
        model = ai_config.get("model", "").strip()
        api_key = ai_config.get("apiKey", "").strip()
        endpoint = ai_config.get("endpoint", "").strip() or None

        # Resolve environment variable references
        if api_key.startswith("${") and api_key.endswith("}"):
            env_var = api_key[2:-1]
            api_key = os.environ.get(env_var, "")

        if not provider or not model:
            raise ProviderNotConfiguredError()

        # Ollama does not need an API key
        if provider != "ollama" and not api_key:
            raise ProviderNotConfiguredError()

        return cls(
            provider=provider,
            model=model,
            api_key=api_key,
            endpoint=endpoint,
        )
