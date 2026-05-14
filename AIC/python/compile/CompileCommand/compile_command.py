"""
AIC Compile Command
Implements: aic compile <ComponentName> --target <language[@version]>

Compiles a component.intent file to target language using configured AI.
Uses delta-based compilation — only changed sections sent to AI.

Inheritance chain:
  project.intent
      ↓ python.intent
      ↓ business/compile/module.intent
      ↓ python/compile/CompileCommand/CompileCommand.intent
      ↓ this file

Four phases:
  Phase 1 — Retrieval    (deterministic) — read intent files
  Phase 2 — Diff         (deterministic) — compute delta vs lockfile
  Phase 3 — Inference    (LLM)           — call AI provider
  Phase 4 — Validation   (deterministic) — write output and lockfile
"""

import time
from pathlib import Path

import click

from core.exceptions import (
    AICError,
    GitNotInitialisedError,
    IntentLibraryMissingError,
    PermissionDeniedError,
)
from core.intent_parser import IntentParseError
from core.inheritance_resolver import InheritanceResolver
from core.lockfile_manager import LockfileManager
from core.delta_engine import DeltaEngine
from core.prompt_builder import PromptBuilder
from models.intent import CompileTarget
from models.lockfile import LockfileEntry
from models.config import AICConfig
from providers.base import ProviderCallError
from utils.git import is_git_repository
from utils.terminal import (
    print_error,
    print_header,
    print_info,
    print_next_steps,
    print_success,
    print_warning,
)

# ── Custom exceptions ─────────────────────────────────────────────────────────

class NotInitialisedError(AICError):
    exit_code = 1
    message = (
        "AIC is not initialised in this directory.\n"
        "Run: aic init"
    )


class ComponentNotFoundError(AICError):
    exit_code = 1

    def __init__(self, component_name: str, language: str):
        self.message = (
            f"Component not found: /{language}/{component_name}\n"
            f"Run: aic create {component_name} --language {language}"
        )
        super().__init__(self.message)


class ProviderNotConfiguredError(AICError):
    exit_code = 1
    message = (
        "AI provider not configured.\n"
        "Fill in .aic/config.json with your provider details.\n"
        "Supported providers: claude, gemini, ollama"
    )


class OutputWriteError(AICError):
    exit_code = 2

    def __init__(self, path: str):
        self.message = f"Failed to write output file: {path}"
        super().__init__(self.message)


# ── Provider factory ──────────────────────────────────────────────────────────

def _get_provider(config: AICConfig):
    """
    Return the appropriate provider adapter based on config.
    Adapter pattern — all providers implement BaseProvider interface.
    """
    if config.provider == "claude":
        from providers.claude_provider import ClaudeProvider
        return ClaudeProvider(model=config.model, api_key=config.api_key)

    elif config.provider == "gemini":
        from providers.gemini_provider import GeminiProvider
        return GeminiProvider(model=config.model, api_key=config.api_key)

    elif config.provider == "ollama":
        from providers.ollama_provider import OllamaProvider
        return OllamaProvider(
            model=config.model,
            api_key="",
            endpoint=config.endpoint or ""
        )

    else:
        raise ProviderNotConfiguredError()


# ── Verification ──────────────────────────────────────────────────────────────

def _verify_output(generated_code: str, component_intent: dict) -> list[tuple[str, bool]]:
    """
    Basic static verification — check declared behaviors exist in output.
    Returns list of (behavior_id, passed) tuples.
    Never fails compilation — warnings only.
    """
    results = []
    behaviors = component_intent.get("implementation", [])

    for behavior in behaviors:
        if isinstance(behavior, dict):
            behavior_id = behavior.get("id", "")
            intent_text = behavior.get("intent", "")

            # Extract key words from intent description
            keywords = [
                word.lower()
                for word in intent_text.split()
                if len(word) > 4
            ][:3]  # Check first 3 meaningful words

            passed = any(kw in generated_code.lower() for kw in keywords)
            results.append((behavior_id, passed))

    return results


# ── Entry point ───────────────────────────────────────────────────────────────

def run_compile(
    component_name: str,
    target_string: str,
    force: bool = False,
    verify: bool = False,
) -> None:
    """
    Execute the aic compile command.
    Four deterministic phases with one LLM phase in the middle.
    No files written if any phase fails.
    """
    project_root = Path.cwd()
    start_time = time.time()

    try:
        # ── Pre-flight validation ─────────────────────────────────────────────
        if not is_git_repository(project_root):
            raise GitNotInitialisedError()

        if not (project_root / "project.intent").exists():
            raise NotInitialisedError()

        target = CompileTarget.parse(target_string)

        component_dir = project_root / target.language / component_name
        if not component_dir.exists():
            raise ComponentNotFoundError(component_name, target.language)

        config = AICConfig.load(project_root)

        print_header(f"Compiling {component_name} → {target}")

        # ── Phase 1 — Retrieval ───────────────────────────────────────────────
        print_info("Phase 1 — Reading intent files...")

        resolver = InheritanceResolver(project_root)
        context = resolver.resolve(component_name, target)

        print_success("Inheritance chain resolved")
        print_info(f"  project.intent")
        print_info(f"  {target.language}/{target.language}.intent")
        print_info(f"  business/{component_name}/module.intent")
        print_info(f"  {target.language}/{component_name}/{component_name}.intent")

        if context.existing_code:
            print_info("  Existing generated file found — delta mode active")
        else:
            print_info("  No existing file — full generation mode")

        # ── Phase 2 — Diff ────────────────────────────────────────────────────
        print_info("Phase 2 — Computing delta...")

        lockfile_manager = LockfileManager(project_root)

        if force:
            print_warning("--force flag set — deleting lockfile, full regeneration")
            lockfile_manager.delete(component_name, target)

        lockfile = lockfile_manager.read(component_name, target)
        delta = DeltaEngine.compute(context.component, lockfile)

        if delta.is_unchanged:
            print_success("Nothing changed — compilation skipped")
            print_info("Use --force to recompile anyway")
            return

        if delta.is_new:
            print_success("First compilation — full generation")
        else:
            changed = list(delta.changed_sections.keys())
            print_success(f"Delta computed — {len(changed)} section(s) changed: {', '.join(changed)}")

        # ── Phase 3 — Inference ───────────────────────────────────────────────
        print_info(f"Phase 3 — Calling {config.provider} ({config.model})...")

        provider = _get_provider(config)
        prompt = PromptBuilder.build(context, delta, target)
        generated_code = provider.generate(prompt)

        print_success(f"Code received from {config.provider}")

        # ── Phase 4 — Write and lockfile ──────────────────────────────────────
        print_info("Phase 4 — Writing output...")

        file_field = context.component.get("file", "")
        if not file_field:
            # Derive output path from component name and language
            language_extensions = {
                "python": f"{_to_snake_case(component_name)}.py",
                "java": f"{component_name}.java",
                "swift": f"{component_name}.swift",
                "kotlin": f"{component_name}.kt",
                "typescript": f"{component_name}.ts",
                "flutter": f"{_to_snake_case(component_name)}.dart",
            }
            file_name = language_extensions.get(
                target.language, f"{component_name}.{target.language}"
            )
            output_path = component_dir / file_name
        else:
            output_path = project_root / file_field

        try:
            output_path.write_text(generated_code, encoding="utf-8")
        except PermissionError:
            raise OutputWriteError(str(output_path))

        print_success(f"Written: {output_path.relative_to(project_root)}")

        # Verify if --verify flag set
        verified = False
        if verify:
            print_info("Running verification...")
            verification_results = _verify_output(generated_code, context.component)
            verified = all(passed for _, passed in verification_results)
            for behavior_id, passed in verification_results:
                if passed:
                    print_success(f"  {behavior_id} — verified")
                else:
                    print_warning(f"  {behavior_id} — not verified (review manually)")

        # Write lockfile
        intent_hash = DeltaEngine.compute_hash(context.component)
        entry = LockfileEntry(
            component_name=component_name,
            language=target.language,
            version=target.version,
            intent_hash=intent_hash,
            provider=config.provider,
            model=config.model,
            generated_at=LockfileManager.now(),
            target=str(target),
            verified=verified,
            intent_snapshot=context.component,
        )
        lockfile_manager.write(entry, target)
        print_success("Lockfile updated")

        # ── Summary ───────────────────────────────────────────────────────────
        elapsed = round(time.time() - start_time, 2)
        print_header(f"Done — {component_name} compiled to {target} in {elapsed}s")

        print_next_steps([
            f"Review generated code: {output_path.relative_to(project_root)}",
            f"Write tests for the generated code",
            f"Run: aic status to check all components",
            f"Raise PR when ready — lockfile will be included",
        ])

    except GitNotInitialisedError as e:
        print_error(e.message)
        raise SystemExit(1)

    except NotInitialisedError as e:
        print_error(e.message)
        raise SystemExit(1)

    except ComponentNotFoundError as e:
        print_error(e.message)
        raise SystemExit(1)

    except ProviderNotConfiguredError as e:
        print_error(e.message)
        raise SystemExit(1)

    except IntentParseError as e:
        print_error(f"Intent file error: {e.file_path}\n{e.reason}")
        raise SystemExit(1)

    except ProviderCallError as e:
        print_error(f"AI provider error [{e.provider}]: {e.reason}")
        raise SystemExit(2)

    except OutputWriteError as e:
        print_error(e.message)
        raise SystemExit(2)

    except PermissionDeniedError as e:
        print_error(e.message)
        raise SystemExit(2)


def _to_snake_case(name: str) -> str:
    """Convert PascalCase to snake_case."""
    import re
    return re.sub(r'(?<!^)(?=[A-Z])', '_', name).lower()
