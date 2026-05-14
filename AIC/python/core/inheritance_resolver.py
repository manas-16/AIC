"""
AIC Inheritance Resolver
Builds the full intent context from the inheritance chain.
Phase 1 of compilation — fully deterministic, zero LLM.

Inheritance order (most general to most specific):
  1. project.intent
  2. language.intent
  3. module.intent
  4. component.intent
"""

from pathlib import Path
from typing import Optional

from core.intent_parser import IntentParser
from models.intent import IntentContext, CompileTarget


class InheritanceResolver:
    """Resolves the full inheritance chain for a component compilation."""

    def __init__(self, project_root: Path):
        self.project_root = project_root
        self.parser = IntentParser()

    def resolve(
        self,
        component_name: str,
        target: CompileTarget,
    ) -> IntentContext:
        """
        Build full IntentContext from all four inheritance levels.
        Reads files in order — project → language → module → component.
        Loads referenced standards files.
        Reads existing generated code if present.
        """
        context = IntentContext()

        # Level 1 — project.intent
        project_intent_path = self.project_root / "project.intent"
        context.project = self.parser.parse(project_intent_path)

        # Load referenced standards files
        standards_refs = context.project.get("standards", {})
        if isinstance(standards_refs, dict):
            context.standards = self.parser.load_standards(
                standards_refs, self.project_root
            )

        # Level 2 — language.intent
        language_dir = self.project_root / target.language
        language_intent = (
            self.parser.parse_optional(language_dir / "language.intent")
            or self.parser.parse_optional(language_dir / f"{target.language}.intent")
            or {}
        )
        context.language = language_intent

        # Level 3 — module.intent
        module_intent_path = (
            self.project_root / "business" / component_name / "module.intent"
        )
        context.module = self.parser.parse_optional(module_intent_path) or {}

        # Level 4 — component.intent
        component_intent_path = (
            self.project_root
            / target.language
            / component_name
            / f"{component_name}.intent"
        )
        context.component = self.parser.parse(component_intent_path)

        # Read existing generated code file if present
        file_field = context.component.get("file", "")
        if file_field:
            output_path = self.project_root / file_field
            if output_path.exists():
                context.existing_code = output_path.read_text(encoding="utf-8")

        return context
