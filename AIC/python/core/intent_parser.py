"""
AIC Intent Parser
Reads and parses .intent files using yaml.safe_load.
Phase 1 of compilation — fully deterministic, zero LLM.
"""

import yaml
from pathlib import Path
from typing import Optional


class IntentParseError(Exception):
    """Raised when an intent file cannot be parsed."""
    def __init__(self, file_path: str, reason: str):
        self.file_path = file_path
        self.reason = reason
        super().__init__(f"Failed to parse {file_path}: {reason}")


class IntentParser:
    """Reads and parses .intent YAML files."""

    @staticmethod
    def parse(intent_path: Path) -> dict:
        """
        Parse a single .intent file.
        Returns parsed dict.
        Raises IntentParseError if file is missing or malformed.
        """
        if not intent_path.exists():
            raise IntentParseError(str(intent_path), "File not found")

        try:
            content = intent_path.read_text(encoding="utf-8")
            parsed = yaml.safe_load(content)
            if parsed is None:
                return {}
            if not isinstance(parsed, dict):
                raise IntentParseError(str(intent_path), "Expected YAML mapping at root level")
            return parsed
        except yaml.YAMLError as e:
            raise IntentParseError(str(intent_path), str(e))

    @staticmethod
    def parse_optional(intent_path: Path) -> Optional[dict]:
        """
        Parse a .intent file if it exists.
        Returns None if file does not exist — not an error.
        """
        if not intent_path.exists():
            return None
        return IntentParser.parse(intent_path)

    @staticmethod
    def load_standards(standards_refs: dict, project_root: Path) -> dict:
        """
        Load referenced standards files declared in project.intent.
        Returns dict of {standard_name: file_content}.
        Missing files are skipped with a warning — not a fatal error.
        """
        loaded = {}
        for name, path_str in standards_refs.items():
            standards_path = project_root / path_str
            if standards_path.exists():
                loaded[name] = standards_path.read_text(encoding="utf-8")
        return loaded
