"""
AIC Prompt Builder
Builds the structured prompt sent to the AI in Phase 3.
The prompt is the core of AIC's compilation quality.

Structure:
  Section 1: Project standards and rules
  Section 2: Language guidelines and patterns
  Section 3: Business intent behaviors and journeys
  Section 4: Component intent delta (changed sections only)
  Section 5: Existing code file if present
  Section 6: Target language and version instruction
  Section 7: Explicit delta instruction
"""

import json
from typing import Optional

from models.intent import IntentContext, CompileTarget
from core.delta_engine import IntentDelta


class PromptBuilder:
    """Builds compilation prompts from intent context and delta."""

    @staticmethod
    def build(
        context: IntentContext,
        delta: IntentDelta,
        target: CompileTarget,
    ) -> str:
        """
        Build the full prompt for the AI provider.
        Only the delta is sent for changed sections — not the full intent.
        Full intent sent on first compilation.
        """
        sections = []

        # Section 1 — Project standards
        sections.append(PromptBuilder._section(
            "PROJECT STANDARDS AND RULES",
            PromptBuilder._format_intent(context.project)
        ))

        # Append any referenced standards files
        if context.standards:
            for name, content in context.standards.items():
                sections.append(PromptBuilder._section(
                    f"STANDARDS FILE: {name}",
                    content
                ))

        # Section 2 — Language guidelines
        if context.language:
            sections.append(PromptBuilder._section(
                "LANGUAGE GUIDELINES AND PATTERNS",
                PromptBuilder._format_intent(context.language)
            ))

        # Section 3 — Business intent
        if context.module:
            sections.append(PromptBuilder._section(
                "BUSINESS INTENT — BEHAVIORS AND JOURNEYS",
                PromptBuilder._format_intent(context.module)
            ))

        # Section 4 — Component intent (delta or full)
        if delta.is_new:
            sections.append(PromptBuilder._section(
                "COMPONENT INTENT — FULL (FIRST COMPILATION)",
                PromptBuilder._format_intent(delta.full_intent)
            ))
        else:
            sections.append(PromptBuilder._section(
                "COMPONENT INTENT — CHANGED SECTIONS ONLY",
                json.dumps(delta.changed_sections, indent=2)
            ))
            sections.append(PromptBuilder._section(
                "COMPONENT INTENT — FULL CONTEXT",
                PromptBuilder._format_intent(delta.full_intent)
            ))

        # Section 5 — Existing code
        if context.existing_code:
            sections.append(PromptBuilder._section(
                "EXISTING GENERATED CODE — READ BEFORE MAKING CHANGES",
                context.existing_code
            ))

        # Section 6 — Target instruction
        version_note = f" version {target.version}" if target.version else ""
        sections.append(PromptBuilder._section(
            "COMPILATION TARGET",
            f"Generate code for: {target.language}{version_note}\n"
            f"Follow all language-specific idioms and best practices for this version."
        ))

        # Section 7 — Delta instruction
        if delta.is_new:
            instruction = (
                "Generate complete, production-ready code implementing all behaviors "
                "declared in the component intent above.\n"
                "Follow all project standards, language guidelines, and business rules.\n"
                "Return ONLY the code — no explanation, no markdown, no code fences."
            )
        else:
            instruction = (
                "Update ONLY the sections of the existing code that correspond to "
                "the changed intent sections above.\n"
                "DO NOT regenerate unchanged sections.\n"
                "DO NOT alter existing logic that is not related to the delta.\n"
                "Preserve all comments and structure in unchanged sections.\n"
                "Return the COMPLETE updated file — not just the changed sections.\n"
                "Return ONLY the code — no explanation, no markdown, no code fences."
            )

        sections.append(PromptBuilder._section("INSTRUCTIONS", instruction))

        return "\n".join(sections)

    @staticmethod
    def _section(title: str, content: str) -> str:
        """Format a named section of the prompt."""
        border = "=" * 60
        return f"{border}\n{title}\n{border}\n{content}\n"

    @staticmethod
    def _format_intent(intent: dict) -> str:
        """Format an intent dict as readable text for the prompt."""
        import yaml
        return yaml.dump(intent, default_flow_style=False, allow_unicode=True)
