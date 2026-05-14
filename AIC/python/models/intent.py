"""
AIC Intent Models
Data models for .intent file contents.
"""

from dataclasses import dataclass, field
from typing import Optional


@dataclass
class IntentContext:
    """
    Represents the full resolved inheritance chain for one component.
    Built by InheritanceResolver from all four intent levels.
    """
    project: dict = field(default_factory=dict)
    language: dict = field(default_factory=dict)
    module: dict = field(default_factory=dict)
    component: dict = field(default_factory=dict)
    standards: dict = field(default_factory=dict)   # referenced standards files
    existing_code: Optional[str] = None              # existing generated file content


@dataclass
class CompileTarget:
    """Parsed compilation target — language and optional version."""
    language: str
    version: Optional[str] = None

    def __str__(self) -> str:
        if self.version:
            return f"{self.language}@{self.version}"
        return self.language

    @classmethod
    def parse(cls, target_string: str) -> "CompileTarget":
        """Parse 'python@3.11' into CompileTarget(language='python', version='3.11')."""
        if "@" in target_string:
            parts = target_string.split("@", 1)
            return cls(language=parts[0].strip(), version=parts[1].strip())
        return cls(language=target_string.strip())
