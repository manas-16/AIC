"""
AIC Status Command
Implements: aic status

Shows sync state of every component across every language.
Three states: STALE, DRIFT, VIOLATION.
Zero LLM — fully deterministic file traversal.

Inheritance chain:
  project.intent
      ↓ python.intent
      ↓ business/status/module.intent
      ↓ python/status/StatusCommand/StatusCommand.intent
      ↓ this file
"""

import hashlib
from dataclasses import dataclass, field
from enum import Enum
from pathlib import Path
from typing import Optional

import click
import yaml
from colorama import Fore, Style

from core.exceptions import AICError, GitNotInitialisedError
from core.lockfile_manager import LockfileManager
from models.intent import CompileTarget
from utils.git import is_git_repository
from utils.terminal import print_error, print_info, print_success


# ── Custom exceptions ─────────────────────────────────────────────────────────

class NotInitialisedError(AICError):
    exit_code = 1
    message = (
        "AIC is not initialised in this directory.\n"
        "Run: aic init"
    )


# ── State enum ────────────────────────────────────────────────────────────────

class ComponentState(Enum):
    IN_SYNC   = "IN SYNC"
    STALE     = "STALE"
    DRIFT     = "DRIFT"
    VIOLATION = "VIOLATION"
    NOT_COMPILED = "NOT COMPILED"


STATE_COLORS = {
    ComponentState.IN_SYNC:      Fore.GREEN,
    ComponentState.STALE:        Fore.YELLOW,
    ComponentState.DRIFT:        Fore.RED,
    ComponentState.VIOLATION:    Fore.RED,
    ComponentState.NOT_COMPILED: Fore.YELLOW,
}

STATE_ICONS = {
    ComponentState.IN_SYNC:      "✓",
    ComponentState.STALE:        "⚠",
    ComponentState.DRIFT:        "✗",
    ComponentState.VIOLATION:    "✗",
    ComponentState.NOT_COMPILED: "⚠",
}


@dataclass
class ComponentStatus:
    """Status of one component in one language."""
    component_name: str
    language: str
    state: ComponentState
    resolution: str = ""


@dataclass
class ProjectStatus:
    """Full project status — all components, all languages."""
    statuses: list[ComponentStatus] = field(default_factory=list)
    languages: list[str] = field(default_factory=list)
    components: list[str] = field(default_factory=list)


# ── Helpers ───────────────────────────────────────────────────────────────────

def _hash_file(path: Path) -> Optional[str]:
    """Compute SHA256 hash of a file. Returns None if file does not exist."""
    if not path.exists():
        return None
    content = path.read_text(encoding="utf-8")
    return hashlib.sha256(content.encode("utf-8")).hexdigest()


def _hash_intent(intent: dict) -> str:
    """Compute SHA256 hash of an intent dict."""
    import json
    serialised = json.dumps(intent, sort_keys=True, ensure_ascii=True)
    return hashlib.sha256(serialised.encode("utf-8")).hexdigest()


def _is_language_folder(folder: Path) -> bool:
    """
    Determine if a folder is a language folder.
    A language folder contains a .intent file at its root level.
    Excludes /business and /.aic.
    """
    excluded = {"business", ".aic", ".git"}
    if folder.name in excluded:
        return False
    if not folder.is_dir():
        return False
    intent_files = list(folder.glob("*.intent"))
    return len(intent_files) > 0


# ── Component Scanner ─────────────────────────────────────────────────────────

class ComponentScanner:
    """Discovers all components and their language combinations."""

    def __init__(self, project_root: Path):
        self.project_root = project_root

    def discover_languages(self) -> list[str]:
        """Find all language folders in project root."""
        return [
            folder.name
            for folder in self.project_root.iterdir()
            if _is_language_folder(folder)
        ]

    def discover_components(self) -> list[str]:
        """Find all components by scanning /business folder."""
        business_dir = self.project_root / "business"
        if not business_dir.exists():
            return []
        return [
            folder.name
            for folder in business_dir.iterdir()
            if folder.is_dir()
        ]

    def discover_pairs(
        self,
        component_filter: Optional[str] = None,
        language_filter: Optional[str] = None,
    ) -> list[tuple[str, str]]:
        """
        Discover all (component, language) pairs that exist in the project.
        Applies optional filters.
        """
        components = self.discover_components()
        languages = self.discover_languages()

        if component_filter:
            components = [c for c in components if c == component_filter]
        if language_filter:
            languages = [l for l in languages if l == language_filter]

        pairs = []
        for component in components:
            for language in languages:
                component_dir = self.project_root / language / component
                if component_dir.exists():
                    pairs.append((component, language))

        return pairs


# ── State Checker ─────────────────────────────────────────────────────────────

class StateChecker:
    """Determines the state of one component in one language."""

    def __init__(self, project_root: Path):
        self.project_root = project_root
        self.lockfile_manager = LockfileManager(project_root)

    def check(self, component_name: str, language: str) -> ComponentStatus:
        """
        Determine state for one component and language combination.
        Checks STALE → DRIFT → VIOLATION in that order.
        Returns ComponentStatus with state and resolution command.
        """
        target = CompileTarget(language=language)

        # Read component intent
        component_intent_path = (
            self.project_root / language / component_name / f"{component_name}.intent"
        )

        if not component_intent_path.exists():
            return ComponentStatus(
                component_name=component_name,
                language=language,
                state=ComponentState.NOT_COMPILED,
                resolution=f"aic compile {component_name} --target {language}",
            )

        # Read intent
        try:
            intent_content = yaml.safe_load(
                component_intent_path.read_text(encoding="utf-8")
            ) or {}
        except yaml.YAMLError:
            return ComponentStatus(
                component_name=component_name,
                language=language,
                state=ComponentState.NOT_COMPILED,
                resolution=f"aic validate {component_name} --language {language}",
            )

        # Read lockfile
        lockfile = self.lockfile_manager.read(component_name, target)

        # STALE check
        current_intent_hash = _hash_intent(intent_content)
        if lockfile is None or current_intent_hash != lockfile.intent_hash:
            return ComponentStatus(
                component_name=component_name,
                language=language,
                state=ComponentState.STALE,
                resolution=f"aic compile {component_name} --target {language}",
            )

        # DRIFT check — hash the generated code file
        file_field = intent_content.get("file", "")
        if file_field:
            output_path = self.project_root / file_field
            current_code_hash = _hash_file(output_path)

            # Compare against stored code hash if present
            # AFTER — reads actual stored hash
            stored_code_hash = lockfile.code_hash
            if stored_code_hash and current_code_hash != stored_code_hash:
                return ComponentStatus(
                    component_name=component_name,
                    language=language,
                    state=ComponentState.DRIFT,
                    resolution=f"aic sync {component_name} --language {language}",
                )

        # VIOLATION check — check overrides against immutable rules
        project_intent_path = self.project_root / "project.intent"
        if project_intent_path.exists():
            try:
                project_intent = yaml.safe_load(
                    project_intent_path.read_text(encoding="utf-8")
                ) or {}
                immutable_rules = project_intent.get("immutable", [])
                overrides = intent_content.get("overrides", [])

                if immutable_rules and overrides:
                    for override in overrides:
                        if isinstance(override, dict):
                            for rule_id in override.keys():
                                if rule_id in immutable_rules:
                                    return ComponentStatus(
                                        component_name=component_name,
                                        language=language,
                                        state=ComponentState.VIOLATION,
                                        resolution=f"aic audit {component_name} --language {language}",
                                    )
            except yaml.YAMLError:
                pass

        # All checks passed
        return ComponentStatus(
            component_name=component_name,
            language=language,
            state=ComponentState.IN_SYNC,
        )


# ── Status Formatter ──────────────────────────────────────────────────────────

class StatusFormatter:
    """Formats and prints project status output."""

    @staticmethod
    def print_table(
        project_status: ProjectStatus,
        expand: bool = False,
    ) -> None:
        """Print status table grouped by component."""
        if not project_status.statuses:
            print_info("No components found.")
            print_info("Run: aic create <ComponentName> --language <language>")
            return

        # Build lookup: (component, language) → state
        lookup: dict[tuple[str, str], ComponentStatus] = {
            (s.component_name, s.language): s
            for s in project_status.statuses
        }

        languages = project_status.languages
        components = project_status.components

        # Header row
        col_width = 18
        header = f"{'Component':<{col_width}}"
        for lang in languages:
            header += f"  {lang:<{col_width}}"
        print(f"\n{Fore.BLUE}{header}{Style.RESET_ALL}")
        print(f"{Fore.BLUE}{'─' * len(header)}{Style.RESET_ALL}")

        # Data rows
        for component in components:
            row = f"{component:<{col_width}}"
            for language in languages:
                status = lookup.get((component, language))
                if status is None:
                    cell = f"{'—':<{col_width}}"
                    row += f"  {Fore.WHITE}{Style.DIM}{cell}{Style.RESET_ALL}"
                else:
                    color = STATE_COLORS[status.state]
                    icon = STATE_ICONS[status.state]
                    label = f"{icon} {status.state.value}"
                    cell = f"{label:<{col_width}}"
                    row += f"  {color}{cell}{Style.RESET_ALL}"
            print(row)

        print()

    @staticmethod
    def print_resolutions(project_status: ProjectStatus) -> None:
        """Print grouped resolution commands for non-sync states."""
        stale = [s for s in project_status.statuses
                 if s.state in (ComponentState.STALE, ComponentState.NOT_COMPILED)]
        drift = [s for s in project_status.statuses if s.state == ComponentState.DRIFT]
        violations = [s for s in project_status.statuses if s.state == ComponentState.VIOLATION]

        if not stale and not drift and not violations:
            return

        if stale:
            print(f"{Fore.YELLOW}STALE — recompile:{Style.RESET_ALL}")
            for s in stale:
                print(f"  {s.resolution}")
            print()

        if drift:
            print(f"{Fore.RED}DRIFT — sync intent:{Style.RESET_ALL}")
            for s in drift:
                print(f"  {s.resolution}")
            print()

        if violations:
            print(f"{Fore.RED}VIOLATIONS — inspect:{Style.RESET_ALL}")
            for s in violations:
                print(f"  {s.resolution}")
            print()

    @staticmethod
    def print_summary(project_status: ProjectStatus) -> None:
        """Print summary line at bottom."""
        total = len(project_status.statuses)
        in_sync = sum(1 for s in project_status.statuses
                      if s.state == ComponentState.IN_SYNC)
        stale = sum(1 for s in project_status.statuses
                    if s.state in (ComponentState.STALE, ComponentState.NOT_COMPILED))
        drift = sum(1 for s in project_status.statuses
                    if s.state == ComponentState.DRIFT)
        violations = sum(1 for s in project_status.statuses
                         if s.state == ComponentState.VIOLATION)

        if in_sync == total:
            print_success("All components in sync — ready to raise PR")
            return

        parts = [
            f"{Fore.GREEN}{in_sync} in sync{Style.RESET_ALL}",
            f"{Fore.YELLOW}{stale} stale{Style.RESET_ALL}",
            f"{Fore.RED}{drift} drift{Style.RESET_ALL}",
            f"{Fore.RED}{violations} violations{Style.RESET_ALL}",
        ]
        print("  ".join(parts))
        print()


# ── Entry Point ───────────────────────────────────────────────────────────────

def run_status(
    component_filter: Optional[str] = None,
    language_filter: Optional[str] = None,
    expand: bool = False,
) -> None:
    """
    Execute the aic status command.
    Fully deterministic — zero LLM.
    Scans all components and languages and prints their state.
    """
    project_root = Path.cwd()

    try:
        # Validation
        if not is_git_repository(project_root):
            raise GitNotInitialisedError()

        if not (project_root / "project.intent").exists():
            raise NotInitialisedError()

        # Discovery
        scanner = ComponentScanner(project_root)
        pairs = scanner.discover_pairs(component_filter, language_filter)
        all_components = scanner.discover_components()
        all_languages = scanner.discover_languages()

        if component_filter:
            all_components = [c for c in all_components if c == component_filter]
        if language_filter:
            all_languages = [l for l in all_languages if l == language_filter]

        if not pairs:
            print_info("No components found.")
            print_info("Run: aic create <ComponentName> --language <language>")
            return

        # Check state for every pair
        checker = StateChecker(project_root)
        statuses = [
            checker.check(component, language)
            for component, language in pairs
        ]

        # Build project status
        project_status = ProjectStatus(
            statuses=statuses,
            languages=all_languages,
            components=all_components,
        )

        # Output
        StatusFormatter.print_table(project_status, expand=expand)
        StatusFormatter.print_resolutions(project_status)
        StatusFormatter.print_summary(project_status)

    except GitNotInitialisedError as e:
        print_error(e.message)
        raise SystemExit(1)

    except NotInitialisedError as e:
        print_error(e.message)
        raise SystemExit(1)
