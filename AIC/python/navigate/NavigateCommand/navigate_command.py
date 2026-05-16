"""
AIC Navigate Command
Implements: aic navigate --query "your task description"

Traverses the project intent structure based on a natural language
query and assembles a scoped context package containing exactly
the right intent files for that task.

ZERO LLM — fully deterministic file traversal and assembly.
This is the bridge between your question and your AI context.

Four phases (all deterministic):
  Phase 1 — Query parsing    — extract component, language, action
  Phase 2 — File traversal   — read relevant intent files only
  Phase 3 — Context assembly — concatenate into structured block
  Phase 4 — Output           — print, copy, or write to file

v1 note: Developer pastes output into AI chat manually.
         MCP server integration planned for v2.
"""

import re
from pathlib import Path
from typing import Optional

import yaml
from colorama import Fore, Style

from core.exceptions import AICError, GitNotInitialisedError
from utils.git import is_git_repository
from utils.terminal import (
    print_error,
    print_info,
    print_success,
    print_warning,
)


# ── Custom exceptions ─────────────────────────────────────────────────────────

class NotInitialisedError(AICError):
    exit_code = 1
    message = "AIC is not initialised. Run: aic init"


# ── Constants ─────────────────────────────────────────────────────────────────

ACTION_KEYWORDS = {
    "fix", "create", "migrate", "explain", "audit",
    "update", "add", "remove", "refactor", "debug",
    "change", "implement", "review", "check", "test",
}

BORDER = "─" * 60


# ── Helpers ───────────────────────────────────────────────────────────────────

def _is_language_folder(folder: Path) -> bool:
    """Determine if a folder is a language folder."""
    excluded = {"business", ".aic", ".git"}
    if folder.name in excluded or not folder.is_dir():
        return False
    return len(list(folder.glob("*.intent"))) > 0


def _discover_components(project_root: Path) -> list[str]:
    """List all component names from /business folder."""
    business_dir = project_root / "business"
    if not business_dir.exists():
        return []
    return [f.name for f in business_dir.iterdir() if f.is_dir()]


def _discover_languages(project_root: Path) -> list[str]:
    """List all language folder names."""
    return [
        f.name for f in project_root.iterdir()
        if _is_language_folder(f)
    ]


def _slugify(query: str) -> str:
    """Convert query string to a safe filename slug."""
    slug = query.lower().strip()
    slug = re.sub(r'[^\w\s-]', '', slug)
    slug = re.sub(r'[\s_]+', '-', slug)
    return slug[:80]


def _read_file_safe(path: Path) -> Optional[str]:
    """Read a file safely — return None if not found or unreadable."""
    try:
        if path.exists():
            return path.read_text(encoding="utf-8")
        return None
    except OSError:
        return None


# ── Phase 1 — Query Parser ────────────────────────────────────────────────────

class QueryParser:
    """Extracts component name, language, and action from query string."""

    def __init__(self, components: list[str], languages: list[str]):
        self.components = components
        self.languages = languages

    def parse(self, query: str) -> tuple[Optional[str], Optional[str], Optional[str]]:
        """
        Parse query into (component_name, language, action).
        Matching is case-insensitive.
        Returns None for any field not found in query.
        """
        query_lower = query.lower()
        query_words = set(query_lower.split())

        # Match component
        matched_component = None
        for component in self.components:
            if component.lower() in query_lower:
                matched_component = component
                break

        # Match language
        matched_language = None
        for language in self.languages:
            if language.lower() in query_words:
                matched_language = language
                break

        # Match action
        matched_action = None
        for word in query_words:
            if word in ACTION_KEYWORDS:
                matched_action = word
                break

        return matched_component, matched_language, matched_action


# ── Phase 2 — File Traversal ──────────────────────────────────────────────────

class IntentTraverser:
    """Reads relevant intent files based on parsed query."""

    def __init__(self, project_root: Path):
        self.project_root = project_root

    def traverse(
        self,
        component_name: Optional[str],
        language: Optional[str],
    ) -> list[tuple[str, str]]:
        """
        Read relevant intent files in inheritance order.
        Returns list of (section_title, file_content) tuples.
        """
        sections = []

        # Always read project.intent first
        project_intent_path = self.project_root / "project.intent"
        content = _read_file_safe(project_intent_path)
        if content:
            sections.append(("PROJECT STANDARDS", content))

        # Read module.intent if component matched
        if component_name:
            module_intent_path = (
                self.project_root / "business" / component_name / "module.intent"
            )
            content = _read_file_safe(module_intent_path)
            if content:
                sections.append((f"BUSINESS INTENT: {component_name}", content))

        # Read language.intent if language matched
        if language:
            language_dir = self.project_root / language
            language_intent = (
                _read_file_safe(language_dir / "language.intent")
                or _read_file_safe(language_dir / f"{language}.intent")
            )
            if language_intent:
                sections.append((f"LANGUAGE GUIDELINES: {language}", language_intent))

        # Read component.intent if both matched
        if component_name and language:
            component_intent_path = (
                self.project_root
                / language
                / component_name
                / f"{component_name}.intent"
            )
            content = _read_file_safe(component_intent_path)
            if content:
                sections.append((
                    f"COMPONENT INTENT: {component_name} / {language}",
                    content
                ))

        return sections


# ── Phase 3 — Context Assembly ────────────────────────────────────────────────

class ContextAssembler:
    """Assembles intent sections into a structured context block."""

    @staticmethod
    def assemble(query: str, sections: list[tuple[str, str]]) -> str:
        """Concatenate sections into one structured context block."""
        lines = []
        lines.append(BORDER)
        lines.append(f"AIC CONTEXT: {query}")
        lines.append(BORDER)
        lines.append("")

        for title, content in sections:
            lines.append(BORDER)
            lines.append(f"[{title}]")
            lines.append(BORDER)
            lines.append(content.strip())
            lines.append("")

        lines.append(BORDER)
        lines.append("Paste this context into your AI before describing your task.")
        lines.append("Your AI now has full scoped context for this component.")
        lines.append(BORDER)

        return "\n".join(lines)


# ── Phase 4 — Output ──────────────────────────────────────────────────────────

def _output_terminal(assembled_context: str) -> None:
    """Print context to terminal. Named explicitly to avoid shadowing."""
    print(f"\n{assembled_context}\n")


def _output_clipboard(assembled_context: str) -> None:
    """Copy context to clipboard using pyperclip."""
    try:
        import pyperclip
        pyperclip.copy(assembled_context)
        print_success("Context copied to clipboard")
    except ImportError:
        print_warning(
            "pyperclip not installed — falling back to terminal output.\n"
            "Install with: pip install pyperclip"
        )
        _output_terminal(assembled_context)
    except Exception:
        print_warning("Clipboard copy failed — falling back to terminal output")
        _output_terminal(assembled_context)


def _output_file(assembled_context: str, query: str, project_root: Path) -> None:
    """Write context to .aic/context/<slug>.txt"""
    context_dir = project_root / ".aic" / "context"
    context_dir.mkdir(parents=True, exist_ok=True)

    slug = _slugify(query)
    output_path = context_dir / f"{slug}.txt"

    try:
        output_path.write_text(assembled_context, encoding="utf-8")
        print_success(f"Context written to: {output_path.relative_to(project_root)}")
    except OSError:
        print_warning("File write failed — falling back to terminal output")
        _output_terminal(assembled_context)


def _print_no_match(components: list[str]) -> None:
    """Print helpful message when no component matched the query."""
    print_warning("No component matched your query.")
    print_info("")
    print_info("Available components:")
    for component in sorted(components):
        print_info(f"  {component}")
    print_info("")
    print_info("Try: aic navigate --query '<ComponentName> your task'")
    print_info("Example: aic navigate --query 'fix UserService login in python'")


# ── Entry Point ───────────────────────────────────────────────────────────────

def run_navigate(
    query: str,
    copy: bool = False,
    to_file: bool = False,
) -> None:
    """
    Execute the aic navigate command.
    Zero LLM — fully deterministic.
    Assembles scoped intent context for developer to paste into AI.
    """
    project_root = Path.cwd()

    try:
        # Validation
        if not is_git_repository(project_root):
            raise GitNotInitialisedError()

        if not (project_root / "project.intent").exists():
            raise NotInitialisedError()

        # Discovery
        components = _discover_components(project_root)
        languages = _discover_languages(project_root)

        # Phase 1 — Query parsing
        parser = QueryParser(components, languages)
        component_name, language, action = parser.parse(query)

        # No match — help developer refine
        if not component_name and not language:
            _print_no_match(components)
            return

        # Summary
        matched = []
        if component_name:
            matched.append(f"component={component_name}")
        if language:
            matched.append(f"language={language}")
        if action:
            matched.append(f"action={action}")

        print_info(f"Context assembled for: {', '.join(matched)}")

        # Phase 2 — File traversal
        traverser = IntentTraverser(project_root)
        sections = traverser.traverse(component_name, language)

        print_info(f"Files included: {len(sections)}")

        # Phase 3 — Context assembly
        # Variable named assembled_context explicitly
        # to avoid any chance of shadowing by imports
        assembled_context = ContextAssembler.assemble(query, sections)

        # Phase 4 — Output
        if copy:
            _output_clipboard(assembled_context)
        elif to_file:
            _output_file(assembled_context, query, project_root)
        else:
            _output_terminal(assembled_context)

        if not copy and not to_file:
            print_info(
                "Tip: use --copy to copy directly to clipboard, "
                "or --file to save to .aic/context/"
            )

    except GitNotInitialisedError as e:
        print_error(e.message)
        raise SystemExit(1)

    except NotInitialisedError as e:
        print_error(e.message)
        raise SystemExit(1)

    except OSError as e:
        print_error(f"File system error: {e}")
        raise SystemExit(2)