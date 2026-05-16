"""
AIC Lockfile Models
Data models for .lock files.
"""

from dataclasses import dataclass, field
from typing import Optional


@dataclass
class LockfileEntry:
    """
    Represents one component's lock state.
    Stored as JSON in .aic/lockfiles/<ComponentName>-<language>.lock

    Field ordering rule: non-default fields must come before default fields.
    """
    # Required fields — no defaults
    component_name: str
    language: str
    version: Optional[str]
    intent_hash: str
    code_hash: str
    provider: str
    model: str
    generated_at: str
    target: str

    # Optional fields — with defaults
    verified: bool = False
    intent_snapshot: dict = field(default_factory=dict)

    def to_dict(self) -> dict:
        return {
            "component_name": self.component_name,
            "language": self.language,
            "version": self.version,
            "intent_hash": self.intent_hash,
            "code_hash": self.code_hash,
            "provider": self.provider,
            "model": self.model,
            "generated_at": self.generated_at,
            "target": self.target,
            "verified": self.verified,
            "intent_snapshot": self.intent_snapshot,
        }

    @classmethod
    def from_dict(cls, data: dict) -> "LockfileEntry":
        return cls(
            component_name=data.get("component_name", ""),
            language=data.get("language", ""),
            version=data.get("version"),
            intent_hash=data.get("intent_hash", ""),
            code_hash=data.get("code_hash", ""),
            provider=data.get("provider", ""),
            model=data.get("model", ""),
            generated_at=data.get("generated_at", ""),
            target=data.get("target", ""),
            verified=data.get("verified", False),
            intent_snapshot=data.get("intent_snapshot", {}),
        )
