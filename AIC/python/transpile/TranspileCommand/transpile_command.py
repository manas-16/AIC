"""
AIC Transpile Command
Implements: aic transpile --target <language[@version]>

Compiles every component in the project to a new target language.
Used for full project migrations and adding new language targets.
Does not touch existing language folders — additive only by default.

Inheritance chain:
  project.intent
      ↓ python.intent
      ↓ business/transpile/module.intent
      ↓ python/transpile/TranspileCommand/TranspileCommand.intent
      ↓ this file

Flow:
  1. Discover all components in /business
  2. For each component — check if exists in target language
  3. Skip existing (unless --force), scaffold missing
  4. Run compile for each component in target language
  5. Print progress and final summary
"""

import sys
from pathlib import Path
from typing import Optional

import yaml

from core.exceptions import AICError, GitNotInitialisedError
from models.intent import CompileTarget
from models.config import AICConfig
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


class NoComponentsError(AICError):
    exit_code = 0
    message = (
        "No components found in /business folder.\n"
        "Run: aic create <ComponentName> --language <language> to scaffold components."
    )


class ComponentNotFoundError(AICError):
    exit_code = 1
    def __init__(self, component_name: str, available: list[str]):
        self.message = (
            f"Component '{component_name}' not found in /business.\n"
            f"Available components: {', '.join(sorted(available))}"
        )
        super().__init__(self.message)


# ── Helpers ───────────────────────────────────────────────────────────────────

AIC_PACKAGE_DIR = Path(__file__).parent.parent.parent


def _read_safe(path: Path) -> Optional[str]:
    """Read file safely — None if missing."""
    try:
        return path.read_text(encoding="utf-8") if path.exists() else None
    except OSError:
        return None


def _get_template(template_name: str) -> str:
    """Load a template file from AIC templates directory."""
    template_path = AIC_PACKAGE_DIR / "templates" / template_name
    if not template_path.exists():
        # Fallback minimal template
        return (
            "id: {{component_id}}\n"
            "type: component\n"
            "extends:\n"
            "  business: {{module_id}}\n"
            "  language: {{language_id}}\n\n"
            "component: {{component_name}}\n"
            "file: {{file_path}}\n\n"
            "implementation:\n"
            "  # TODO: fill in implementation details\n"
        )
    return template_path.read_text(encoding="utf-8")


def _render_template(template: str, context: dict) -> str:
    """Replace {{key}} placeholders with context values."""
    result = template
    for key, value in context.items():
        result = result.replace(f"{{{{{key}}}}}", str(value))
    return result


def _to_snake_case(name: str) -> str:
    """Convert PascalCase to snake_case."""
    import re
    return re.sub(r'(?<!^)(?=[A-Z])', '_', name).lower()


def _get_code_filename(language: str, component_name: str) -> str:
    """Get code file name for language."""
    extensions = {
        "python": f"{_to_snake_case(component_name)}.py",
        "java": f"{component_name}.java",
        "swift": f"{component_name}.swift",
        "kotlin": f"{component_name}.kt",
        "flutter": f"{_to_snake_case(component_name)}.dart",
        "typescript": f"{component_name}.ts",
        "apex": f"{component_name}.cls",
    }
    return extensions.get(language, f"{component_name}.{language}")


def _get_module_id(project_root: Path, component_name: str) -> str:
    """Read module_id from existing module.intent."""
    module_intent_path = (
        project_root / "business" / component_name / "module.intent"
    )
    if module_intent_path.exists():
        try:
            content = yaml.safe_load(
                module_intent_path.read_text(encoding="utf-8")
            )
            if content and "id" in content:
                return content["id"]
        except Exception:
            pass
    return f"{component_name[:3].upper()}-001"


def _get_language_id(project_root: Path, language: str) -> str:
    """Read language id from language.intent."""
    lang_dir = project_root / language
    for candidate in [lang_dir / "language.intent", lang_dir / f"{language}.intent"]:
        if candidate.exists():
            try:
                content = yaml.safe_load(
                    candidate.read_text(encoding="utf-8")
                )
                if content and "id" in content:
                    return content["id"]
            except Exception:
                pass
    return f"{language}-guidelines"


# ── Component discovery ───────────────────────────────────────────────────────

def _discover_components(project_root: Path) -> list[str]:
    """List all component names from /business folder."""
    business_dir = project_root / "business"
    if not business_dir.exists():
        return []
    return sorted([f.name for f in business_dir.iterdir() if f.is_dir()])


# ── Scaffold component in new language ────────────────────────────────────────

def _scaffold_component(
    project_root: Path,
    component_name: str,
    target: CompileTarget,
) -> None:
    """
    Create component folder and component.intent in target language.
    Uses module.intent from /business as the source of truth.
    """
    component_dir = project_root / target.language / component_name
    component_dir.mkdir(parents=True, exist_ok=True)

    intent_path = component_dir / f"{component_name}.intent"
    if intent_path.exists():
        return  # Already exists — compile will handle it

    module_id = _get_module_id(project_root, component_name)
    language_id = _get_language_id(project_root, target.language)
    component_id = f"{module_id}-{target.language[:3].upper()}"
    stub_file = _get_code_filename(target.language, component_name)
    file_path = f"{target.language}/{component_name}/{stub_file}"

    template = _get_template("component.intent.template")
    context = {
        "component_id": component_id,
        "module_id": module_id,
        "language_id": language_id,
        "component_name": component_name,
        "file_path": file_path,
    }
    content = _render_template(template, context)
    intent_path.write_text(content, encoding="utf-8")


# ── Entry point ───────────────────────────────────────────────────────────────

def run_transpile(
    target_string: str,
    force: bool = False,
    component_filter: Optional[str] = None,
) -> None:
    """Execute the aic transpile command."""
    project_root = Path.cwd()

    try:
        # Validation
        if not is_git_repository(project_root):
            raise GitNotInitialisedError()

        if not (project_root / "project.intent").exists():
            raise NotInitialisedError()

        # Validate provider configured
        try:
            AICConfig.load(project_root)
        except Exception:
            raise ProviderNotConfiguredError()

        target = CompileTarget.parse(target_string)

        # Discover components
        all_components = _discover_components(project_root)

        if not all_components:
            raise NoComponentsError()

        # Apply --component filter
        if component_filter:
            if component_filter not in all_components:
                raise ComponentNotFoundError(component_filter, all_components)
            components_to_process = [component_filter]
        else:
            components_to_process = all_components

        print_header(f"Transpiling {len(components_to_process)} components → {target}")

        # Categorise components
        to_compile = []
        to_skip = []

        for component_name in components_to_process:
            component_dir = project_root / target.language / component_name
            intent_path = component_dir / f"{component_name}.intent"

            if intent_path.exists() and not force:
                to_skip.append(component_name)
            else:
                to_compile.append(component_name)

        if to_skip:
            print_warning(
                f"{len(to_skip)} component(s) already exist in /{target.language} "
                f"— skipping. Use --force to overwrite."
            )

        if not to_compile:
            print_info("Nothing to compile.")
            _print_summary(len(components_to_process), 0, len(to_skip), 0, [], target)
            return

        # Scaffold missing components first
        print_info(f"Scaffolding {len(to_compile)} component(s) in /{target.language}...")
        for component_name in to_compile:
            component_dir = project_root / target.language / component_name
            if not component_dir.exists() or not (component_dir / f"{component_name}.intent").exists():
                _scaffold_component(project_root, component_name, target)

        # Compile each component
        compiled = []
        failed = []
        total = len(to_compile)

        from compile.CompileCommand.compile_command import run_compile

        for i, component_name in enumerate(to_compile, 1):
            print(
                f"\n{Fore.BLUE}[{i}/{total}]{Style.RESET_ALL} "
                f"Compiling {component_name}..."
            )

            try:
                # Capture SystemExit from run_compile
                run_compile(
                    component_name=component_name,
                    target_string=target_string,
                    force=force,
                    verify=False,
                )
                compiled.append(component_name)
                print_success(f"{component_name} — done")

            except SystemExit as e:
                exit_code = e.code if e.code is not None else 1
                if exit_code == 0:
                    compiled.append(component_name)
                    print_success(f"{component_name} — done")
                else:
                    failed.append(component_name)
                    print_error(
                        f"{component_name} — failed "
                        f"(run: aic compile {component_name} --target {target} for details)"
                    )

            except Exception as e:
                failed.append(component_name)
                print_error(f"{component_name} — failed: {str(e)[:80]}")

        # Final summary
        _print_summary(total, len(compiled), len(to_skip), len(failed), failed, target)

        if failed:
            sys.exit(1)

    except GitNotInitialisedError as e:
        print_error(e.message)
        sys.exit(1)

    except NotInitialisedError as e:
        print_error(e.message)
        sys.exit(1)

    except ProviderNotConfiguredError as e:
        print_error(e.message)
        sys.exit(1)

    except NoComponentsError as e:
        print_info(e.message)
        sys.exit(0)

    except ComponentNotFoundError as e:
        print_error(e.message)
        sys.exit(1)


def _print_summary(
    total: int,
    compiled: int,
    skipped: int,
    failed: int,
    failed_names: list[str],
    target: CompileTarget,
) -> None:
    """Print final transpile summary."""
    print(f"\n{Fore.BLUE}{'─' * 60}")
    print(f"TRANSPILE SUMMARY — {target}")
    print(f"{'─' * 60}{Style.RESET_ALL}")
    print(f"  Total components:  {total}")
    print(f"  {Fore.GREEN}Compiled:          {compiled}{Style.RESET_ALL}")
    print(f"  {Fore.YELLOW}Skipped:           {skipped}{Style.RESET_ALL}")
    print(f"  {Fore.RED}Failed:            {failed}{Style.RESET_ALL}")

    if failed_names:
        print(f"\n{Fore.RED}Failed components:{Style.RESET_ALL}")
        for name in failed_names:
            print(f"  aic compile {name} --target {target}")

    print(f"{Fore.BLUE}{'─' * 60}{Style.RESET_ALL}\n")