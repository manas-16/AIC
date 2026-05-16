"""
AIC Validate Command
Implements: aic validate <intent-file-path>

Validates a .intent file against AIC intent standards and project/language
guidelines. Uses the configured AI provider to provide feedback on user-entered
intent without modifying any files.
"""

from pathlib import Path
from typing import Optional

import yaml

from core.exceptions import AICError, GitNotInitialisedError
from core.intent_parser import IntentParseError, IntentParser
from models.config import AICConfig
from providers.base import ProviderCallError
from utils.git import is_git_repository
from utils.terminal import (
    print_error,
    print_header,
    print_info,
    print_success,
    print_warning,
)
from colorama import Fore


# ── Custom exceptions ─────────────────────────────────────────────────────────

class NotInitialisedError(AICError):
    exit_code = 1
    message = "AIC is not initialised. Run: aic init"


class IntentFileError(AICError):
    exit_code = 1

    def __init__(self, path: Path):
        self.message = (
            f"Intent file not found or invalid: {path}\n"
            f"Provide a valid .intent path. Example: aic validate business/UserService/module.intent"
        )
        super().__init__(self.message)


class ProviderNotConfiguredError(AICError):
    exit_code = 1
    message = (
        "AI provider not configured.\n"
        "Fill in .aic/aic.config.json with your provider details."
    )


# ── Provider factory ──────────────────────────────────────────────────────────

def _get_provider(config: AICConfig):
    if config.provider == "claude":
        from providers.claude import ClaudeProvider

        return ClaudeProvider(model=config.model, api_key=config.api_key)
    elif config.provider == "gemini":
        from providers.gemini import GeminiProvider

        return GeminiProvider(model=config.model, api_key=config.api_key)
    elif config.provider == "ollama":
        from providers.ollama import OllamaProvider

        return OllamaProvider(model=config.model, api_key="", endpoint=config.endpoint or "")
    else:
        raise ProviderNotConfiguredError()


def _resolve_source_root() -> Path:
    return Path(__file__).resolve().parents[4]


def _load_optional_text(path: Path) -> Optional[str]:
    if not path.exists():
        return None
    try:
        return path.read_text(encoding="utf-8")
    except OSError:
        return None


def _validate_schema(intent_data: dict, file_path: Path) -> list[str]:
    issues = []
    required = ["id", "type", "owner", "extends"]
    for field in required:
        if field not in intent_data:
            issues.append(f"Missing required field: {field}")

    intent_type = intent_data.get("type", "").lower()
    if intent_type == "module":
        if "behaviors" not in intent_data:
            issues.append("Module intent should define a behaviors section.")
    elif intent_type == "component":
        if "implementation" not in intent_data:
            issues.append("Component intent should define an implementation section.")
    elif intent_type:
        if intent_type not in {"project", "module", "language", "component"}:
            issues.append(f"Unexpected intent type: {intent_type}")
    else:
        issues.append("Missing or empty intent type.")

    return issues


def _build_validation_prompt(
    intent_path: Path,
    intent_text: str,
    project_intent_text: Optional[str],
    language_intent_text: Optional[str],
    validate_module_text: Optional[str],
    validate_component_text: Optional[str],
) -> str:
    border = "=" * 60
    sections = [
        f"{border}\nUSER INTENT FILE\n{border}\nPath: {intent_path}\n\n{intent_text.strip()}"
    ]

    if project_intent_text:
        sections.append(f"{border}\nPROJECT INTENT CONTEXT\n{border}\n{project_intent_text.strip()}")

    if language_intent_text:
        sections.append(f"{border}\nLANGUAGE GUIDELINES CONTEXT\n{border}\n{language_intent_text.strip()}")

    if validate_module_text:
        sections.append(f"{border}\nAIC VALIDATE MODULE GUIDELINES\n{border}\n{validate_module_text.strip()}")

    if validate_component_text:
        sections.append(f"{border}\nAIC VALIDATE COMPONENT GUIDELINES\n{border}\n{validate_component_text.strip()}")

    instructions = f"""{border}
VALIDATION INSTRUCTIONS
{border}
Review the user intent file above and the provided standards.

Identify all issues that would prevent this intent from being high quality for AIC:
  - missing required metadata or sections
  - malformed or ambiguous intent language
  - unsupported or inconsistent intent structure
  - missing implementation detail for component intent
  - missing behaviors or user journeys for module intent

Provide:
  1. A short summary of the most important issues.
  2. A list of validation findings.
  3. Suggested improvements for the intent text.

Do not modify the intent file.
Do not return code fences. Return only plain text.
"""

    sections.append(instructions)
    return "\n\n".join(sections)


def _get_language_guidelines(intent_path: Path, project_root: Path) -> Optional[str]:
    try:
        relative = intent_path.relative_to(project_root)
    except ValueError:
        return None

    parts = relative.parts
    if len(parts) >= 3 and parts[0] != "business":
        language = parts[0]
        language_intent = project_root / language / "language.intent"
        if language_intent.exists():
            return language_intent.read_text(encoding="utf-8")
        alt = project_root / language / f"{language}.intent"
        if alt.exists():
            return alt.read_text(encoding="utf-8")
    return None


def run_validate(intent_file_path: str) -> None:
    project_root = Path.cwd()

    if not is_git_repository(project_root):
        raise GitNotInitialisedError()

    intent_path = Path(intent_file_path)
    if not intent_path.is_absolute():
        intent_path = project_root / intent_path

    if not intent_path.exists() or intent_path.suffix != ".intent":
        raise IntentFileError(Path(intent_file_path))

    try:
        intent_data = IntentParser.parse(intent_path)
    except IntentParseError as e:
        print_error(str(e))
        return

    schema_issues = _validate_schema(intent_data, intent_path)
    if schema_issues:
        print_header("Intent Schema Issues")
        for issue in schema_issues:
            print_warning(issue)
        print_info("Proceeding to AI-based validation for additional guidance.")

    source_root = _resolve_source_root()
    validate_module_path = source_root / "business" / "validate" / "module.intent"
    validate_component_path = source_root / "python" / "validate" / "ValidateCommand" / "ValidateCommand.intent"

    project_intent_text = _load_optional_text(project_root / "project.intent")
    language_intent_text = _get_language_guidelines(intent_path, project_root)
    validate_module_text = _load_optional_text(validate_module_path)
    validate_component_text = _load_optional_text(validate_component_path)

    intent_text = intent_path.read_text(encoding="utf-8")
    prompt = _build_validation_prompt(
        intent_path,
        intent_text,
        project_intent_text,
        language_intent_text,
        validate_module_text,
        validate_component_text,
    )

    config = AICConfig.load(project_root)
    provider = _get_provider(config)

    print_header("AIC Intent Validation")
    print_info(f"Validating: {intent_path.relative_to(project_root)}")
    if project_intent_text:
        print_info("Loaded project.intent for context.")
    if language_intent_text:
        print_info("Loaded language guidelines for context.")

    try:
        feedback = provider.generate(prompt)
    except ProviderCallError as e:
        raise e

    print_header("Validation Feedback")
    print(feedback.strip())

    if "no issues" in feedback.lower() or "no problems" in feedback.lower():
        print_success("Intent appears valid.")
    else:
        print_info("Review the feedback above and update the intent file as needed.")
