"""
AIC Ask Command
Implements: aic ask --query "your question or fix request"

Conversational AI interface for the repository.
Assembles scoped context from intent files and code,
sends to configured AI, returns answer or applies fix.

Two modes:
  Question mode (default) — answers query, no file changes
  Fix mode (--fix)        — applies code changes, triggers sync

Inheritance chain:
  project.intent
      ↓ python.intent
      ↓ business/ask/module.intent
      ↓ python/ask/AskCommand/AskCommand.intent
      ↓ this file

Phases:
  Phase 1 — Scope detection   (deterministic)
  Phase 2 — Context assembly  (deterministic)
  Phase 3 — Prompt building   (deterministic)
  Phase 4 — AI call           (LLM)
  Phase 5 — Write + sync      (deterministic + sync LLM, fix mode only)
"""

import re
from dataclasses import dataclass, field
from pathlib import Path
from typing import Optional

import yaml

from core.exceptions import AICError, GitNotInitialisedError
from models.config import AICConfig
from models.intent import CompileTarget
from providers.base import ProviderCallError
from utils.git import is_git_repository
from utils.terminal import (
    print_error,
    print_header,
    print_info,
    print_success,
    print_warning,
)
from colorama import Fore, Style


# ── Custom exceptions ─────────────────────────────────────────────────────────

class NotInitialisedError(AICError):
    exit_code = 1
    message = "AIC is not initialised. Run: aic init"


class ProviderNotConfiguredError(AICError):
    exit_code = 1
    message = (
        "AI provider not configured.\n"
        "Fill in .aic/aic.config.json with your provider details."
    )


class MultiLanguageFixError(AICError):
    exit_code = 1
    def __init__(self, component_name: str, languages: list[str]):
        self.message = (
            f"Component '{component_name}' exists in multiple languages: "
            f"{', '.join(languages)}\n"
            f"Fix mode requires --language to be specified.\n"
            f"Example: aic ask --query \"your fix\" --fix --language python"
        )
        super().__init__(self.message)


class NoMatchError(AICError):
    exit_code = 0
    def __init__(self, components: list[str]):
        self.message = (
            "No component matched your query.\n"
            f"Available components: {', '.join(sorted(components))}\n"
            "Try including a component name in your query.\n"
            "For project-level questions this is fine — "
            "AIC will use project and module intent."
        )
        super().__init__(self.message)


# ── Scope detection ───────────────────────────────────────────────────────────

@dataclass
class ScopeResult:
    """Result of query scope detection."""
    components: list[str] = field(default_factory=list)
    language: Optional[str] = None
    is_project_level: bool = False


def _discover_components(project_root: Path) -> list[str]:
    """List all component names from /business folder."""
    business_dir = project_root / "business"
    if not business_dir.exists():
        return []
    return [f.name for f in business_dir.iterdir() if f.is_dir()]


def _discover_languages(project_root: Path) -> list[str]:
    """List all language folder names."""
    excluded = {"business", ".aic", ".git"}
    return [
        f.name for f in project_root.iterdir()
        if f.is_dir()
        and f.name not in excluded
        and len(list(f.glob("*.intent"))) > 0
    ]


def _detect_scope(
    query: str,
    all_components: list[str],
    all_languages: list[str],
    language_override: Optional[str] = None,
) -> ScopeResult:
    """
    Detect scope from query by matching component and language names.
    Returns ScopeResult with matched components and language.
    """
    query_lower = query.lower()

    # Match components
    matched_components = [
        c for c in all_components
        if c.lower() in query_lower
    ]

    # Match language
    matched_language = language_override
    if not matched_language:
        for lang in all_languages:
            if lang.lower() in query_lower.split():
                matched_language = lang
                break

    is_project_level = len(matched_components) == 0

    return ScopeResult(
        components=matched_components,
        language=matched_language,
        is_project_level=is_project_level,
    )


# ── Context assembly ──────────────────────────────────────────────────────────

BORDER = "=" * 60


def _read_safe(path: Path) -> Optional[str]:
    """Read file safely — None if missing."""
    try:
        return path.read_text(encoding="utf-8") if path.exists() else None
    except OSError:
        return None


def _assemble_context(
    project_root: Path,
    scope: ScopeResult,
    include_code: bool = False,
) -> str:
    """
    Assemble context from intent files and optionally code files.
    Scope determines what gets included.
    """
    sections = []

    # Always include project.intent
    content = _read_safe(project_root / "project.intent")
    if content:
        sections.append(("PROJECT STANDARDS", content))

    if scope.is_project_level:
        # Project scope — read all module.intent files
        business_dir = project_root / "business"
        if business_dir.exists():
            for module_dir in sorted(business_dir.iterdir()):
                if module_dir.is_dir():
                    module_intent = _read_safe(module_dir / "module.intent")
                    if module_intent:
                        sections.append((
                            f"BUSINESS INTENT: {module_dir.name}",
                            module_intent
                        ))
    else:
        # Component scope — read per component
        for component_name in scope.components:
            # Business intent
            module_intent = _read_safe(
                project_root / "business" / component_name / "module.intent"
            )
            if module_intent:
                sections.append((
                    f"BUSINESS INTENT: {component_name}",
                    module_intent
                ))

            # Language intent and component files
            languages_to_read = (
                [scope.language] if scope.language
                else _discover_languages(project_root)
            )

            for language in languages_to_read:
                # Language guidelines
                lang_dir = project_root / language
                lang_intent = (
                    _read_safe(lang_dir / "language.intent")
                    or _read_safe(lang_dir / f"{language}.intent")
                )
                if lang_intent:
                    sections.append((
                        f"LANGUAGE GUIDELINES: {language}",
                        lang_intent
                    ))

                # All .intent files in component folder
                component_dir = project_root / language / component_name
                if component_dir.exists():
                    for intent_file in sorted(component_dir.rglob("*.intent")):
                        content = _read_safe(intent_file)
                        if content:
                            rel = intent_file.relative_to(project_root)
                            sections.append((
                                f"COMPONENT INTENT: {rel}",
                                content
                            ))

                    # Code files — only if include_code is True
                    if include_code:
                        code_extensions = {
                            ".py", ".java", ".swift", ".kt",
                            ".ts", ".dart", ".go", ".cs"
                        }
                        for code_file in sorted(component_dir.rglob("*")):
                            if (
                                code_file.is_file()
                                and code_file.suffix in code_extensions
                            ):
                                content = _read_safe(code_file)
                                if content:
                                    rel = code_file.relative_to(project_root)
                                    sections.append((
                                        f"CODE FILE: {rel}",
                                        content
                                    ))

    # Assemble into one string
    lines = []
    for title, content in sections:
        lines.append(BORDER)
        lines.append(f"[{title}]")
        lines.append(BORDER)
        lines.append(content.strip())
        lines.append("")

    return "\n".join(lines)


# ── Prompt building ───────────────────────────────────────────────────────────

def _build_question_prompt(context: str, query: str) -> str:
    """Build prompt for question mode."""
    return f"""{context}

{BORDER}
[DEVELOPER QUERY]
{BORDER}
{query}

{BORDER}
[INSTRUCTIONS]
{BORDER}
Answer the developer query above using the context provided.
Be specific, accurate, and reference the actual intent and code where relevant.
If the answer requires looking at something not in the context say so clearly.
"""


def _build_fix_prompt(context: str, query: str) -> str:
    """Build prompt for fix mode."""
    return f"""{context}

{BORDER}
[FIX REQUEST]
{BORDER}
{query}

{BORDER}
[INSTRUCTIONS]
{BORDER}
Apply the fix requested above to the relevant code files.

For each file you modify return the complete fixed file in this exact format:

FILE: <relative/path/to/file>
<complete file content here>
END_FILE

Rules:
- Return the COMPLETE file content — not just the changed lines
- Only include files you actually changed
- File path must be relative to project root
- Follow all coding standards and patterns from the intent context above
- Do not include explanations between FILE blocks
- After all FILE blocks add a SUMMARY section explaining what you changed
"""


# ── Fix response parsing ──────────────────────────────────────────────────────

def _parse_fix_response(response: str) -> list[tuple[str, str]]:
    """
    Parse AI fix response into list of (file_path, code_content) tuples.
    Looks for FILE: ... END_FILE markers.
    Returns empty list if no markers found.
    """
    file_blocks = []
    pattern = r'FILE:\s*(.+?)\n(.*?)END_FILE'
    matches = re.findall(pattern, response, re.DOTALL)

    for file_path, code_content in matches:
        file_path = file_path.strip()
        code_content = code_content.strip()
        if file_path and code_content:
            file_blocks.append((file_path, code_content))

    return file_blocks


def _extract_component_language(
    file_path: str,
    all_components: list[str],
    all_languages: list[str],
) -> tuple[Optional[str], Optional[str]]:
    """
    Extract component name and language from a file path.
    Example: python/UserService/user_service.py
             → language=python, component=UserService
    """
    parts = Path(file_path).parts
    detected_language = None
    detected_component = None

    for part in parts:
        if part in all_languages:
            detected_language = part
        if part in all_components:
            detected_component = part

    return detected_component, detected_language


# ── Provider factory ──────────────────────────────────────────────────────────

def _get_provider(config: AICConfig):
    """Return provider adapter based on config."""
    if config.provider == "claude":
        from providers.claude import ClaudeProvider
        return ClaudeProvider(model=config.model, api_key=config.api_key)
    elif config.provider == "gemini":
        from providers.gemini import GeminiProvider
        return GeminiProvider(model=config.model, api_key=config.api_key)
    elif config.provider == "ollama":
        from providers.ollama import OllamaProvider
        return OllamaProvider(model=config.model, endpoint=config.endpoint or "")
    else:
        raise ProviderNotConfiguredError()


# ── Entry point ───────────────────────────────────────────────────────────────

def run_ask(
    query: str,
    fix: bool = False,
    language_override: Optional[str] = None,
) -> None:
    """Execute the aic ask command."""
    project_root = Path.cwd()

    try:
        # Validation
        if not is_git_repository(project_root):
            raise GitNotInitialisedError()

        if not (project_root / "project.intent").exists():
            raise NotInitialisedError()

        config = AICConfig.load(project_root)
        provider = _get_provider(config)

        all_components = _discover_components(project_root)
        all_languages = _discover_languages(project_root)

        # Phase 1 — Scope detection
        scope = _detect_scope(query, all_components, all_languages, language_override)

        print_header("AIC Ask")
        if scope.is_project_level:
            print_info("Scope: project level — reading all module intents")
        else:
            print_info(f"Scope: {', '.join(scope.components)}")
            if scope.language:
                print_info(f"Language: {scope.language}")

        # Multi-language fix guard
        if fix and not language_override and not scope.is_project_level:
            for component in scope.components:
                langs_with_component = [
                    lang for lang in all_languages
                    if (project_root / lang / component).exists()
                ]
                if len(langs_with_component) > 1:
                    raise MultiLanguageFixError(component, langs_with_component)

        # Phase 2 — Context assembly
        print_info("Assembling context...")
        context = _assemble_context(
            project_root,
            scope,
            include_code=fix or not scope.is_project_level,
        )
        print_success("Context assembled")

        # Phase 3 — Prompt building
        if fix:
            prompt = _build_fix_prompt(context, query)
        else:
            prompt = _build_question_prompt(context, query)

        # Phase 4 — AI call
        print_info(f"Sending to {config.provider}...")
        response = provider.generate(prompt)
        print_success("Response received")

        # Phase 5 — Handle response
        if not fix:
            # Question mode — print answer
            print(f"\n{Fore.CYAN}{'─' * 60}")
            print("ANSWER")
            print(f"{'─' * 60}{Style.RESET_ALL}")
            print(response)
            print(f"{Fore.CYAN}{'─' * 60}{Style.RESET_ALL}\n")
            return

        # Fix mode — parse and apply
        file_blocks = _parse_fix_response(response)

        if not file_blocks:
            # No FILE markers — print raw response as fallback
            print_warning(
                "Could not parse file blocks from AI response.\n"
                "Apply the following changes manually:"
            )
            print(f"\n{response}\n")
            return

        # Write each fixed file
        modified_files = []
        sync_needed = []

        for file_path, code_content in file_blocks:
            full_path = project_root / file_path
            try:
                full_path.parent.mkdir(parents=True, exist_ok=True)
                full_path.write_text(code_content, encoding="utf-8")
                print_success(f"Fixed: {file_path}")
                modified_files.append(file_path)

                # Detect component and language for sync
                component, language = _extract_component_language(
                    file_path, all_components, all_languages
                )
                if component and language:
                    sync_needed.append((component, language))

            except OSError as e:
                print_warning(f"Could not write {file_path}: {e}")

        # Auto-trigger sync for each modified component
        if sync_needed:
            print_info("\nTriggering sync for modified components...")
            from sync.SyncCommand.sync_command import run_sync
            for component, language in set(sync_needed):
                print_info(f"  Syncing {component} ({language})...")
                try:
                    run_sync(component, language)
                    print_success(
                        f"  Sync suggestions generated for {component}"
                    )
                except SystemExit:
                    print_warning(
                        f"  Sync skipped for {component} — "
                        "run manually: "
                        f"aic sync {component} --language {language}"
                    )

        # Summary
        print(f"\n{Fore.CYAN}{'─' * 60}")
        print("SUMMARY")
        print(f"{'─' * 60}{Style.RESET_ALL}")

        print(f"{Fore.GREEN}Files modified:{Style.RESET_ALL}")
        for f in modified_files:
            print(f"  {f}")

        if sync_needed:
            print(f"\n{Fore.CYAN}Sync triggered for:{Style.RESET_ALL}")
            for component, language in set(sync_needed):
                print(f"  {component} ({language})")
            print(
                f"\n{Fore.YELLOW}Review sync suggestions then run:{Style.RESET_ALL}"
            )
            for component, language in set(sync_needed):
                print(
                    f"  aic sync {component} "
                    f"--language {language} --approve"
                )

        print(f"\n{Fore.CYAN}Next steps:{Style.RESET_ALL}")
        print("  aic status — verify everything is in sync")
        print(f"{Fore.CYAN}{'─' * 60}{Style.RESET_ALL}\n")

    except GitNotInitialisedError as e:
        print_error(e.message)
        raise SystemExit(1)

    except NotInitialisedError as e:
        print_error(e.message)
        raise SystemExit(1)

    except ProviderNotConfiguredError as e:
        print_error(e.message)
        raise SystemExit(1)

    except MultiLanguageFixError as e:
        print_error(e.message)
        raise SystemExit(1)

    except ProviderCallError as e:
        print_error(f"AI provider error [{e.provider}]: {e.reason}")
        raise SystemExit(2)
