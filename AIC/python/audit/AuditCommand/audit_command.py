"""
AIC Audit Command
Implements: aic audit <code-file-path>

Strictly judges a code file against all relevant intent files.
No extra suggestions. No style advice. No opinions.
Only checks whether the code complies with declared intent.
Pass or fail per intent rule. Nothing else.

Inheritance chain:
  project.intent
      ↓ python.intent
      ↓ business/audit/module.intent
      ↓ python/audit/AuditCommand/AuditCommand.intent
      ↓ this file

Phases:
  Phase 1 — File resolution   (deterministic)
  Phase 2 — Intent assembly   (deterministic)
  Phase 3 — Prompt building   (deterministic)
  Phase 4 — AI judgment       (LLM)
  Phase 5 — Report printing   (deterministic)
"""

import sys
from pathlib import Path
from typing import Optional

import yaml

from core.exceptions import AICError, GitNotInitialisedError
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
from colorama import Fore, Style


# ── Custom exceptions ─────────────────────────────────────────────────────────

class NotInitialisedError(AICError):
    exit_code = 1
    message = "AIC is not initialised. Run: aic init"


class FileNotFoundError(AICError):
    exit_code = 1
    def __init__(self, path: str):
        self.message = f"Code file not found: {path}"
        super().__init__(self.message)


class ComponentResolutionError(AICError):
    exit_code = 1
    def __init__(self, path: str, available: list[str]):
        self.message = (
            f"Cannot resolve component from path: {path}\n"
            f"Available components: {', '.join(sorted(available))}\n"
            "Path must include a known language folder and component folder.\n"
            "Example: python/UserService/user_service.py"
        )
        super().__init__(self.message)


class NoIntentFilesError(AICError):
    exit_code = 1
    message = (
        "No intent files found for this component.\n"
        "Run: aic init to initialise AIC\n"
        "Run: aic create <ComponentName> --language <language> to scaffold component"
    )


class ProviderNotConfiguredError(AICError):
    exit_code = 1
    message = (
        "AI provider not configured.\n"
        "Fill in .aic/aic.config.json with your provider details."
    )


# ── Helpers ───────────────────────────────────────────────────────────────────

def _read_safe(path: Path) -> Optional[str]:
    """Read file safely — None if missing."""
    try:
        return path.read_text(encoding="utf-8") if path.exists() else None
    except OSError:
        return None


def _discover_languages(project_root: Path) -> list[str]:
    """List all language folder names."""
    excluded = {"business", ".aic", ".git"}
    return [
        f.name for f in project_root.iterdir()
        if f.is_dir()
        and f.name not in excluded
        and len(list(f.glob("*.intent"))) > 0
    ]


def _discover_components(project_root: Path) -> list[str]:
    """List all component names from /business folder."""
    business_dir = project_root / "business"
    if not business_dir.exists():
        return []
    return [f.name for f in business_dir.iterdir() if f.is_dir()]


# ── Phase 1 — File resolution ─────────────────────────────────────────────────

def _resolve_component(
    file_path: str,
    project_root: Path,
) -> tuple[str, str]:
    """
    Extract language and component name from file path.
    Matches path segments against known language and component folders.
    Returns (language, component_name).
    Raises ComponentResolutionError if cannot resolve.
    """
    all_languages = _discover_languages(project_root)
    all_components = _discover_components(project_root)

    language_map = {lang.lower(): lang for lang in all_languages}
    component_map = {comp.lower(): comp for comp in all_components}

    parts = Path(file_path).parts
    detected_language = None
    detected_component = None

    for part in parts:
        part_lower = part.lower()
        if detected_language is None and part_lower in language_map:
            detected_language = language_map[part_lower]
        if detected_component is None and part_lower in component_map:
            detected_component = component_map[part_lower]

    if not detected_language or not detected_component:
        raise ComponentResolutionError(file_path, all_components)

    return detected_language, detected_component


# ── Phase 2 — Intent assembly ─────────────────────────────────────────────────

def _assemble_intents(
    project_root: Path,
    language: str,
    component_name: str,
) -> tuple[dict[str, str], bool]:
    """
    Read all relevant intent files for this component.
    Returns (dict of label->content, at_least_one_found).
    Missing files are noted but not fatal.
    """
    intents = {}

    # project.intent — always first
    content = _read_safe(project_root / "project.intent")
    if content:
        intents["PROJECT INTENT (project.intent)"] = content

    # language.intent
    lang_dir = project_root / language
    lang_content = (
        _read_safe(lang_dir / "language.intent")
        or _read_safe(lang_dir / f"{language}.intent")
    )
    if lang_content:
        intents[f"LANGUAGE INTENT ({language}.intent)"] = lang_content

    # module.intent
    module_content = _read_safe(
        project_root / "business" / component_name / "module.intent"
    )
    if module_content:
        intents[f"BUSINESS INTENT (business/{component_name}/module.intent)"] = module_content

    # component.intent
    component_content = _read_safe(
        project_root / language / component_name / f"{component_name}.intent"
    )
    if component_content:
        intents[f"COMPONENT INTENT ({language}/{component_name}/{component_name}.intent)"] = component_content

    return intents, len(intents) > 0


# ── Phase 3 — Prompt building ─────────────────────────────────────────────────

def _build_audit_prompt(
    intents: dict[str, str],
    code_content: str,
    file_path: str,
) -> str:
    """
    Build strict audit prompt.
    AI must judge code only against declared intents.
    No extra suggestions. No opinions. No style advice.
    """
    border = "=" * 60

    intent_sections = ""
    for label, content in intents.items():
        intent_sections += f"{border}\n{label}\n{border}\n{content.strip()}\n\n"

    return f"""{border}
INTENT FILES — AUDIT BASIS
{border}
The following intent files declare the rules this code must comply with.
These are the ONLY rules that matter for this audit.

{intent_sections}
{border}
CODE FILE TO AUDIT: {file_path}
{border}
{code_content}

{border}
AUDIT INSTRUCTIONS — READ CAREFULLY
{border}
You are a strict code auditor. Your job is to check whether the code
above complies with the intent files above.

STRICT RULES FOR YOUR RESPONSE:
1. Judge the code ONLY against rules explicitly declared in the intent files above
2. Do NOT suggest improvements that are not in the intent files
3. Do NOT comment on code style, performance, or patterns not mentioned in intent
4. Do NOT add opinions, recommendations, or best practices not in the intent
5. If the intent files say nothing about something — it is not your concern
6. Silence on topics not covered by intent is CORRECT behavior

RESPONSE FORMAT — use exactly this format for each rule you check:
PASS | <intent-id-or-rule-name> | <one line explanation>
FAIL | <intent-id-or-rule-name> | <one line explanation of what is missing or wrong>
SKIP | <intent-id-or-rule-name> | <one line explanation of why not applicable>

After all checks print exactly:
SUMMARY: X passed, Y failed, Z skipped

Do not add anything after the SUMMARY line.
Do not add introductory text before the first PASS/FAIL/SKIP line.
Start your response directly with the first PASS/FAIL/SKIP line."""


# ── Phase 4 + 5 — Call AI and print report ────────────────────────────────────

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


def _print_report(response: str, file_path: str) -> int:
    """
    Parse and print structured audit report.
    Returns 0 if all pass/skip, 1 if any fail.
    """
    print(f"\n{Fore.BLUE}{'─' * 60}")
    print(f"AUDIT REPORT — {file_path}")
    print(f"{'─' * 60}{Style.RESET_ALL}\n")

    has_failures = False
    lines = response.strip().splitlines()

    for line in lines:
        line = line.strip()
        if not line:
            continue

        upper = line.upper()

        if upper.startswith("PASS"):
            print(f"{Fore.GREEN}{line}{Style.RESET_ALL}")

        elif upper.startswith("FAIL"):
            print(f"{Fore.RED}{line}{Style.RESET_ALL}")
            has_failures = True

        elif upper.startswith("SKIP"):
            print(f"{Fore.YELLOW}{line}{Style.RESET_ALL}")

        elif upper.startswith("SUMMARY"):
            print(f"\n{Fore.BLUE}{'─' * 60}")
            print(f"{Fore.WHITE}{line}{Style.RESET_ALL}")
            print(f"{Fore.BLUE}{'─' * 60}{Style.RESET_ALL}")

        else:
            # AI added something outside the format — print dimmed
            print(f"{Style.DIM}{line}{Style.RESET_ALL}")

    print()
    return 1 if has_failures else 0


# ── Entry point ───────────────────────────────────────────────────────────────

def run_audit(file_path: str) -> None:
    """Execute the aic audit command."""
    project_root = Path.cwd()

    try:
        # Validation
        if not is_git_repository(project_root):
            raise GitNotInitialisedError()

        if not (project_root / "project.intent").exists():
            raise NotInitialisedError()

        # Resolve full path
        full_path = project_root / file_path
        if not full_path.exists():
            raise FileNotFoundError(str(full_path))

        # Phase 1 — Resolve component
        print_info(f"Resolving component from: {file_path}")
        language, component_name = _resolve_component(file_path, project_root)
        print_success(f"Resolved: {component_name} ({language})")

        # Phase 2 — Assemble intents
        print_info("Assembling intent files...")
        intents, found_any = _assemble_intents(project_root, language, component_name)

        if not found_any:
            raise NoIntentFilesError()

        for label in intents:
            print_success(f"  Found: {label}")

        # Read code file
        code_content = full_path.read_text(encoding="utf-8")

        # Phase 3 — Build prompt
        prompt = _build_audit_prompt(intents, code_content, file_path)

        # Phase 4 — Call AI
        config = AICConfig.load(project_root)
        provider = _get_provider(config)
        print_info(f"Sending to {config.provider} for strict audit...")
        response = provider.generate(prompt)
        print_success("Audit complete")

        # Phase 5 — Print report
        exit_code = _print_report(response, file_path)

        sys.exit(exit_code)

    except GitNotInitialisedError as e:
        print_error(e.message)
        sys.exit(1)

    except NotInitialisedError as e:
        print_error(e.message)
        sys.exit(1)

    except FileNotFoundError as e:
        print_error(e.message)
        sys.exit(1)

    except ComponentResolutionError as e:
        print_error(e.message)
        sys.exit(1)

    except NoIntentFilesError as e:
        print_error(e.message)
        sys.exit(1)

    except ProviderNotConfiguredError as e:
        print_error(e.message)
        sys.exit(1)

    except ProviderCallError as e:
        print_error(f"AI provider error [{e.provider}]: {e.reason}")
        sys.exit(2)