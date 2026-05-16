"""
AIC Init Command
Implements: aic init

Initialises a new AIC-compatible project in the current directory.

Inheritance chain:
  project.intent
      ↓ python.intent
      ↓ /business/init/module.intent
      ↓ /python/init/InitCommand/InitCommand.intent
      ↓ this file

Phases (all deterministic — zero LLM):
  1. Validation  — git check, existing init check
  2. Discovery   — derive project name and git remote
  3. Creation    — create folder structure
  4. Generation  — generate intent and config files from templates
  5. Installation — copy intent library and standards as read-only
  6. Output      — print success message and next steps
"""

import json
import os
import shutil
import stat
from datetime import date
from pathlib import Path

import click

from core.exceptions import (
    AlreadyInitialisedError,
    FolderCreationError,
    GitNotInitialisedError,
    IntentLibraryMissingError,
    PermissionDeniedError,
)
from utils.git import get_project_name, get_remote_url, is_git_repository
from utils.terminal import (
    print_error,
    print_header,
    print_info,
    print_next_steps,
    print_success,
    print_tree,
)

# Path to AIC's own installation directory
# Templates and intent library live here
AIC_PACKAGE_DIR = Path(__file__).parent.parent.parent


def _get_template(template_name: str) -> str:
    """
    Load a template file from AIC's templates directory.
    Raises IntentLibraryMissingError if templates are not found.
    """
    template_path = AIC_PACKAGE_DIR / "templates" / template_name
    if not template_path.exists():
        raise IntentLibraryMissingError()
    return template_path.read_text(encoding="utf-8")


def _render_template(template: str, context: dict) -> str:
    """
    Replace {{key}} placeholders in template with context values.
    Simple string replacement — no external templating engine needed.
    """
    result = template
    for key, value in context.items():
        result = result.replace(f"{{{{{key}}}}}", value)
    return result


def _create_folder(path: Path) -> None:
    """
    Create a folder at the given path.
    Raises FolderCreationError with the specific path if creation fails.
    """
    try:
        path.mkdir(parents=True, exist_ok=False)
    except PermissionError:
        raise PermissionDeniedError(str(path))
    except FileExistsError:
        # Folder already exists — not an error during init
        pass
    except OSError:
        raise FolderCreationError(str(path))


def _set_readonly(path: Path) -> None:
    """
    Set a file or all files in a directory to read-only.
    Handles Windows via stat flags — no platform-specific branching needed.
    """
    if path.is_file():
        path.chmod(stat.S_IRUSR | stat.S_IRGRP | stat.S_IROTH)
    elif path.is_dir():
        for item in path.rglob("*"):
            if item.is_file():
                item.chmod(stat.S_IRUSR | stat.S_IRGRP | stat.S_IROTH)


def _copy_intent_library(aic_dir: Path) -> None:
    """
    Copy AIC's own intent library into the project's .aic/intent-lib/ folder.
    Sets all copied files to read-only.
    Raises IntentLibraryMissingError if the library is not found in the installation.
    """
    intent_lib_source = AIC_PACKAGE_DIR.parent / "business"
    if not intent_lib_source.exists():
        raise IntentLibraryMissingError()

    intent_lib_dest = aic_dir / "intent-lib"
    _create_folder(intent_lib_dest)

    # Copy project.intent as part of the library
    project_intent_source = AIC_PACKAGE_DIR.parent / "project.intent"
    if project_intent_source.exists():
        shutil.copy2(project_intent_source, intent_lib_dest / "project.intent")

    # Copy business intent folder
    business_dest = intent_lib_dest / "business"
    if intent_lib_source.exists():
        shutil.copytree(intent_lib_source, business_dest, dirs_exist_ok=True)

    # Copy NAVIGATION.intent template as the navigation guide
    nav_template = AIC_PACKAGE_DIR / "templates" / "NAVIGATION.intent.template"
    if nav_template.exists():
        shutil.copy2(nav_template, intent_lib_dest / "NAVIGATION.intent")

    # Set entire intent-lib as read-only
    _set_readonly(intent_lib_dest)


def _copy_standards(aic_dir: Path) -> None:
    """
    Copy AIC's default standards configs into .aic/standards/.
    Sets all copied files to read-only.
    Standards are optional — no error if source does not exist.
    """
    standards_source = AIC_PACKAGE_DIR.parent / "standards"
    standards_dest = aic_dir / "standards"
    _create_folder(standards_dest)

    if standards_source.exists():
        shutil.copytree(standards_source, standards_dest, dirs_exist_ok=True)
        _set_readonly(standards_dest)


def _generate_project_intent(project_root: Path, project_name: str, git_remote: str) -> None:
    """
    Generate project.intent in the project root from template.
    Pre-fills project name, git remote, and today's date.
    """
    template = _get_template("project.intent.template")
    context = {
        "project_name": project_name,
        "git_remote": git_remote,
        "date": date.today().isoformat(),
    }
    content = _render_template(template, context)

    try:
        (project_root / "project.intent").write_text(content, encoding="utf-8")
    except PermissionError:
        raise PermissionDeniedError(str(project_root / "project.intent"))


def _generate_navigation_intent(project_root: Path) -> None:
    """
    Generate NAVIGATION.intent in the project root from template.
    This is the AI navigation entry point for the entire repository.
    """
    template = _get_template("NAVIGATION.intent.template")
    try:
        (project_root / "NAVIGATION.intent").write_text(template, encoding="utf-8")
    except PermissionError:
        raise PermissionDeniedError(str(project_root / "NAVIGATION.intent"))


def _generate_aic_config(aic_dir: Path) -> None:
    """
    Generate aic.config.json in .aic/ from template.
    All values are placeholders — developer fills in their provider details.
    """
    template = _get_template("aic.config.template.json")
    config_path = aic_dir / "aic.config.json"
    try:
        config_path.write_text(template, encoding="utf-8")
    except PermissionError:
        raise PermissionDeniedError(str(config_path))


# ── Phase 1 — Validation ──────────────────────────────────────────────────────

def _validate(project_root: Path) -> None:
    """
    Run all pre-flight checks before creating any files.
    Fail loudly with clear messages — do not create anything if checks fail.
    """
    if not is_git_repository(project_root):
        raise GitNotInitialisedError()

    if (project_root / "project.intent").exists():
        raise AlreadyInitialisedError()


# ── Phase 2 — Discovery ───────────────────────────────────────────────────────

def _discover(project_root: Path) -> tuple[str, str]:
    """
    Derive project name and git remote from the current directory.
    Returns (project_name, git_remote).
    git_remote may be empty string — not an error.
    """
    project_name = get_project_name(project_root)
    git_remote = get_remote_url(project_root)
    return project_name, git_remote


# ── Phase 3 — Creation ────────────────────────────────────────────────────────

def _create_structure(project_root: Path) -> list[tuple[str, str]]:
    """
    Create all required folders in the correct order.
    Returns list of (path, description) tuples for output display.
    Raises FolderCreationError with specific path if any creation fails.
    """
    aic_dir = project_root / ".aic"

    folders = [
        (project_root / "business", "business intent modules"),
        (aic_dir, "AIC internal directory"),
        (aic_dir / "intent-lib", "AIC intent library (read-only reference)"),
        (aic_dir / "standards", "coding standards configs (read-only)"),
        (aic_dir / "lockfiles", "component lockfiles"),
        (aic_dir / "logs", "AIC error logs"),
    ]

    created = []
    for folder_path, description in folders:
        _create_folder(folder_path)
        created.append((str(folder_path.relative_to(project_root)), description))

    return created


# ── Phase 4 — Generation ──────────────────────────────────────────────────────

def _generate_files(
    project_root: Path,
    project_name: str,
    git_remote: str
) -> list[tuple[str, str]]:
    """
    Generate all intent and config files from templates.
    Returns list of (path, description) tuples for output display.
    """
    aic_dir = project_root / ".aic"

    _generate_project_intent(project_root, project_name, git_remote)
    _generate_navigation_intent(project_root)
    _generate_aic_config(aic_dir)

    return [
        ("project.intent", "fill in your architectural rules"),
        ("NAVIGATION.intent", "AI navigation entry point — read-only"),
        (".aic/aic.config.json", "configure your AI provider here"),
    ]


# ── Phase 5 — Installation ────────────────────────────────────────────────────

def _install_library(project_root: Path) -> list[tuple[str, str]]:
    """
    Copy AIC intent library and standards into .aic/ as read-only.
    Returns list of (path, description) tuples for output display.
    """
    aic_dir = project_root / ".aic"

    _copy_intent_library(aic_dir)
    _copy_standards(aic_dir)

    return [
        (".aic/intent-lib/", "AIC intent library — read-only reference"),
        (".aic/standards/", "coding standards — read-only"),
    ]


# ── Phase 6 — Output ──────────────────────────────────────────────────────────

def _print_success(
    project_name: str,
    created_folders: list[tuple[str, str]],
    created_files: list[tuple[str, str]],
    installed: list[tuple[str, str]],
) -> None:
    """
    Print the success message showing everything that was created.
    Uses Rich-style output via terminal utility.
    """
    print_header(f"AIC initialised — {project_name}")

    print_success("Project structure created")
    print_tree(created_folders + created_files + installed)

    print_next_steps([
        "Fill in project.intent with your architectural rules",
        "Configure your AI provider in .aic/aic.config.json",
        "Create your first module: aic create <ComponentName> --language <language>",
        "Read AIC's own intent files for reference: .aic/intent-lib/",
    ])

    print_info(
        "Tip: run 'aic navigate --query \"your task\"' to get scoped "
        "context for your AI before starting any task."
    )


# ── Entry Point ───────────────────────────────────────────────────────────────

def run_init() -> None:
    """
    Execute the aic init command.
    All phases run in order. Any failure exits cleanly with a clear message.
    No files are created if validation fails.
    """
    project_root = Path.cwd()

    try:
        # Phase 1 — Validation
        _validate(project_root)

        # Phase 2 — Discovery
        project_name, git_remote = _discover(project_root)
        print_info(f"Initialising AIC for project: {project_name}")

        # Phase 3 — Creation
        created_folders = _create_structure(project_root)

        # Phase 4 — Generation
        created_files = _generate_files(project_root, project_name, git_remote)

        # Phase 5 — Installation
        installed = _install_library(project_root)

        # Phase 6 — Output
        _print_success(project_name, created_folders, created_files, installed)

    except GitNotInitialisedError as e:
        print_error(e.message)
        raise SystemExit(1)

    except AlreadyInitialisedError as e:
        print_error(e.message)
        raise SystemExit(1)

    except FolderCreationError as e:
        print_error(e.message)
        raise SystemExit(2)

    except IntentLibraryMissingError as e:
        print_error(e.message)
        raise SystemExit(2)

    except PermissionDeniedError as e:
        print_error(e.message)
        raise SystemExit(2)
