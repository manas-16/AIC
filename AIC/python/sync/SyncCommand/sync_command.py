"""
AIC Sync Command v2
Implements: aic sync <ComponentName> --language <language>

Compares current code against current intent using AI.
Suggests intent updates based on what changed in code.
Developer approves before anything is written.

Inheritance chain:
  project.intent
      ↓ python.intent
      ↓ business/sync/module.intent
      ↓ python/sync/SyncCommand/SyncCommand.intent
      ↓ this file

Phases:
  Phase 1 — Validation          (deterministic)
  Phase 2 — AI comparison       (LLM — one call only)
  Phase 3 — Display suggestions (deterministic)
  Approve — Apply to intent     (deterministic)
  Reject  — Discard             (deterministic)
"""

import hashlib
import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional

import click
import yaml

from core.exceptions import AICError, GitNotInitialisedError
from core.delta_engine import DeltaEngine
from core.lockfile_manager import LockfileManager
from models.intent import CompileTarget
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


class ComponentNotFoundError(AICError):
    exit_code = 1
    def __init__(self, component_name: str, language: str):
        self.message = (
            f"Component not found: /{language}/{component_name}\n"
            f"Run: aic create {component_name} --language {language}"
        )
        super().__init__(self.message)


class NoLockfileError(AICError):
    exit_code = 1
    def __init__(self, component_name: str, language: str):
        self.message = (
            f"No lockfile found for {component_name} ({language}).\n"
            "Component has not been compiled yet.\n"
            f"Run: aic compile {component_name} --target {language}"
        )
        super().__init__(self.message)


class ProviderNotConfiguredError(AICError):
    exit_code = 1
    message = (
        "AI provider not configured.\n"
        "Fill in .aic/aic.config.json with your provider details."
    )


class NoProposalError(AICError):
    exit_code = 1
    def __init__(self, component_name: str, language: str):
        self.message = (
            f"No suggestions found for {component_name} ({language}).\n"
            f"Run: aic sync {component_name} --language {language}\n"
            "to generate suggestions first."
        )
        super().__init__(self.message)


class IntentWriteError(AICError):
    exit_code = 2
    def __init__(self, path: str):
        self.message = (
            f"Failed to write component.intent: {path}\n"
            "Suggestions are preserved in .aic/sync-proposals/"
        )
        super().__init__(self.message)


# ── Helpers ───────────────────────────────────────────────────────────────────

def _hash_content(content: str) -> str:
    """Compute SHA256 hash of string content."""
    return hashlib.sha256(content.encode("utf-8")).hexdigest()


def _now() -> str:
    """Return current UTC timestamp as ISO string."""
    return datetime.now(timezone.utc).isoformat()


def _proposal_path(aic_dir: Path, component_name: str, language: str) -> Path:
    """Compute proposal file path."""
    proposals_dir = aic_dir / "sync-proposals"
    proposals_dir.mkdir(parents=True, exist_ok=True)
    return proposals_dir / f"{component_name}-{language}.proposal"


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


# ── Phase 2 — Sync prompt ─────────────────────────────────────────────────────

def _build_sync_prompt(component_intent: dict, current_code: str) -> str:
    """
    Build prompt asking AI to compare code against intent
    and suggest only the sections that need updating.
    """
    intent_yaml = yaml.dump(
        component_intent,
        default_flow_style=False,
        allow_unicode=True
    )

    border = "=" * 60

    return f"""{border}
CURRENT COMPONENT INTENT
{border}
{intent_yaml}

{border}
CURRENT CODE
{border}
{current_code}

{border}
INSTRUCTIONS
{border}
Compare the code above against the intent above.

Identify what is in the code that is:
  - Missing from the intent
  - Different from what the intent describes
  - A new behavior not captured in the intent

Return ONLY the YAML sections that need to be added or updated.
Use the exact same format, indentation and style as the intent file above.
Do not return the entire intent file — only what changed.
Do not include explanations or markdown.
Return only valid YAML.

If the code and intent are already in sync return exactly:
NO_CHANGES_NEEDED"""


# ── Phase 3 — Display suggestions ────────────────────────────────────────────

def _display_suggestions(
    component_intent: dict,
    suggested_yaml: str,
    component_name: str,
    language: str,
) -> None:
    """Print suggested intent changes clearly to terminal."""
    print(f"\n{Fore.CYAN}{'─' * 60}")
    print(f"SYNC SUGGESTIONS — {component_name} ({language})")
    print(f"{'─' * 60}{Style.RESET_ALL}")

    print(f"\n{Fore.YELLOW}Current intent sections that would change:{Style.RESET_ALL}")
    try:
        suggested = yaml.safe_load(suggested_yaml)
        if suggested and isinstance(suggested, dict):
            for key in suggested:
                if key in component_intent:
                    print(f"\n{Fore.YELLOW}  [{key}] currently:{Style.RESET_ALL}")
                    current_val = yaml.dump(
                        {key: component_intent[key]},
                        default_flow_style=False
                    )
                    for line in current_val.splitlines():
                        print(f"  {Fore.YELLOW}{line}{Style.RESET_ALL}")
                else:
                    print(f"\n{Fore.YELLOW}  [{key}] — new section{Style.RESET_ALL}")
    except yaml.YAMLError:
        pass

    print(f"\n{Fore.GREEN}Suggested updates:{Style.RESET_ALL}")
    for line in suggested_yaml.splitlines():
        print(f"  {Fore.GREEN}{line}{Style.RESET_ALL}")

    print(f"\n{Fore.CYAN}{'─' * 60}{Style.RESET_ALL}")


def _write_proposal(
    proposal_path: Path,
    component_name: str,
    language: str,
    suggested_yaml: str,
) -> None:
    """Write proposal file."""
    content = f"""COMPONENT: {component_name}
LANGUAGE: {language}
GENERATED: {_now()}
STATUS: PENDING

{suggested_yaml}
"""
    proposal_path.write_text(content, encoding="utf-8")


# ── Approve flow ──────────────────────────────────────────────────────────────

def _apply_suggestions(
    proposal_path: Path,
    component_intent_path: Path,
    component_intent: dict,
    output_path: Path,
    lockfile_manager: LockfileManager,
    component_name: str,
    target: CompileTarget,
) -> None:
    """Apply approved suggestions to component.intent and update lockfile."""
    proposal_content = proposal_path.read_text(encoding="utf-8")

    # Strip header lines — find where YAML starts
    lines = proposal_content.splitlines()
    yaml_lines = []
    in_yaml = False
    for line in lines:
        if line.startswith("COMPONENT:") or line.startswith("LANGUAGE:") \
                or line.startswith("GENERATED:") or line.startswith("STATUS:"):
            continue
        if line.strip() == "":
            if not in_yaml:
                continue
        in_yaml = True
        yaml_lines.append(line)

    suggested_yaml = "\n".join(yaml_lines).strip()

    try:
        suggested_updates = yaml.safe_load(suggested_yaml)
    except yaml.YAMLError as e:
        print_error(f"Failed to parse suggestions: {e}")
        raise SystemExit(1)

    if suggested_updates and isinstance(suggested_updates, dict):
        # Merge only changed sections — do not overwrite entire file
        component_intent.update(suggested_updates)

        try:
            updated_yaml = yaml.dump(
                component_intent,
                default_flow_style=False,
                allow_unicode=True
            )
            component_intent_path.write_text(updated_yaml, encoding="utf-8")
        except OSError:
            raise IntentWriteError(str(component_intent_path))

    # Update lockfile
    new_intent_hash = DeltaEngine.compute_hash(component_intent)
    current_code = output_path.read_text(encoding="utf-8") if output_path.exists() else ""
    new_code_hash = _hash_content(current_code)

    from models.lockfile import LockfileEntry
    existing = lockfile_manager.read(component_name, target)

    entry = LockfileEntry(
        component_name=component_name,
        language=target.language,
        version=target.version,
        intent_hash=new_intent_hash,
        code_hash=new_code_hash,
        provider=existing.provider if existing else "",
        model=existing.model if existing else "",
        generated_at=_now(),
        target=str(target),
        verified=False,
        intent_snapshot=component_intent,
    )
    lockfile_manager.write(entry, target)

    # Delete proposal
    proposal_path.unlink(missing_ok=True)

    print_success("Suggestions applied to component.intent")
    print_success("Lockfile updated — DRIFT cleared")
    print_info(f"Run: aic status to confirm {component_name} is in sync")


# ── Entry Point ───────────────────────────────────────────────────────────────

def run_sync(
    component_name: str,
    language: str,
    approve: bool = False,
    reject: bool = False,
) -> None:
    """Execute the aic sync command."""
    project_root = Path.cwd()
    aic_dir = project_root / ".aic"
    target = CompileTarget(language=language)

    try:
        # Phase 1 — Validation
        if not is_git_repository(project_root):
            raise GitNotInitialisedError()

        if not (project_root / "project.intent").exists():
            raise NotInitialisedError()

        component_dir = project_root / language / component_name
        if not component_dir.exists():
            raise ComponentNotFoundError(component_name, language)

        lockfile_manager = LockfileManager(project_root)
        lockfile = lockfile_manager.read(component_name, target)
        if not lockfile:
            raise NoLockfileError(component_name, language)

        proposal_path = _proposal_path(aic_dir, component_name, language)

        component_intent_path = component_dir / f"{component_name}.intent"
        component_intent = yaml.safe_load(
            component_intent_path.read_text(encoding="utf-8")
        ) or {}

        file_field = component_intent.get("file", "")
        output_path = (
            project_root / file_field if file_field
            else component_dir / f"{component_name}.py"
        )

        # ── Handle --reject ───────────────────────────────────────────────────
        if reject:
            if proposal_path.exists():
                proposal_path.unlink()
                print_success("Suggestions discarded")
            else:
                print_info("No pending suggestions found — nothing to reject")
            print_info(
                f"To reset code to intent: "
                f"aic compile {component_name} --target {language} --force"
            )
            return

        # ── Handle --approve ──────────────────────────────────────────────────
        if approve:
            if not proposal_path.exists():
                raise NoProposalError(component_name, language)

            print_header(f"Applying suggestions — {component_name}")
            _apply_suggestions(
                proposal_path,
                component_intent_path,
                component_intent,
                output_path,
                lockfile_manager,
                component_name,
                target,
            )
            return

        # ── Main flow — generate suggestions ──────────────────────────────────
        print_header(f"Syncing {component_name} ({language})")

        if not output_path.exists():
            print_warning("Generated code file not found.")
            print_info(
                f"Run: aic compile {component_name} --target {language}"
            )
            raise SystemExit(1)

        current_code = output_path.read_text(encoding="utf-8")

        # Phase 2 — AI comparison
        print_info("Comparing code against intent...")
        config = AICConfig.load(project_root)
        provider = _get_provider(config)
        prompt = _build_sync_prompt(component_intent, current_code)
        response = provider.generate(prompt)
        print_success(f"Comparison received from {config.provider}")

        # Check if in sync
        if response.strip() == "NO_CHANGES_NEEDED":
            print_success(
                f"{component_name} — code and intent are in sync. "
                "Nothing to update."
            )
            return

        # Phase 3 — Display suggestions
        _display_suggestions(
            component_intent,
            response.strip(),
            component_name,
            language,
        )

        # Save proposal
        _write_proposal(proposal_path, component_name, language, response.strip())

        print_success(
            f"Suggestions saved to: "
            f"{proposal_path.relative_to(project_root)}"
        )
        print_info("")
        print_info("Review the suggestions above then run:")
        print_info(
            f"  aic sync {component_name} --language {language} --approve"
        )
        print_info(
            f"  aic sync {component_name} --language {language} --reject"
        )

    except GitNotInitialisedError as e:
        print_error(e.message)
        raise SystemExit(1)

    except NotInitialisedError as e:
        print_error(e.message)
        raise SystemExit(1)

    except ComponentNotFoundError as e:
        print_error(e.message)
        raise SystemExit(1)

    except NoLockfileError as e:
        print_error(e.message)
        raise SystemExit(1)

    except NoProposalError as e:
        print_error(e.message)
        raise SystemExit(1)

    except ProviderNotConfiguredError as e:
        print_error(e.message)
        raise SystemExit(1)

    except ProviderCallError as e:
        print_error(f"AI provider error [{e.provider}]: {e.reason}")
        raise SystemExit(2)

    except IntentWriteError as e:
        print_error(e.message)
        raise SystemExit(2)