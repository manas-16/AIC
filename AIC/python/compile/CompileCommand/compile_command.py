"""
AIC Compile Command v2
Implements: aic compile <ComponentName> --target <language[@version]>

Key fix: when module.intent or language.intent changes,
compile now also updates component.intent with corresponding
intent stubs and informs the developer what changed.

Four phases:
  Phase 1 — Retrieval    (deterministic)
  Phase 2 — Diff         (deterministic) — now tracks all levels
  Phase 3 — Inference    (LLM)
  Phase 4 — Write        (deterministic) — now updates component.intent too
"""

import hashlib
import re
import time
from pathlib import Path

import yaml

from core.exceptions import (
    AICError,
    GitNotInitialisedError,
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
from colorama import Fore, Style


# ── Custom exceptions ─────────────────────────────────────────────────────────

class NotInitialisedError(AICError):
    exit_code = 1
    message = "AIC is not initialised in this directory.\nRun: aic init"


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
        "Fill in .aic/aic.config.json with your provider details.\n"
        "Supported providers: claude, gemini, ollama"
    )


class OutputWriteError(AICError):
    exit_code = 2
    def __init__(self, path: str):
        self.message = f"Failed to write output file: {path}"
        super().__init__(self.message)


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


def _to_snake_case(name: str) -> str:
    return re.sub(r'(?<!^)(?=[A-Z])', '_', name).lower()


# ── Component intent updater ──────────────────────────────────────────────────

def _build_intent_stubs_for_module_changes(
    module_changes: dict,
    existing_component_intent: dict,
) -> dict:
    """
    When module.intent behaviors change, build corresponding
    implementation stub entries for component.intent.
    Only adds stubs for NEW behaviors — does not overwrite existing ones.
    Returns dict of sections to merge into component.intent.
    """
    updates = {}

    # Check if behaviors changed in module
    if "behaviors" not in module_changes:
        return updates

    new_behaviors = module_changes["behaviors"].get("new", [])
    old_behaviors = module_changes["behaviors"].get("old", [])

    if not new_behaviors or not isinstance(new_behaviors, list):
        return updates

    # Find behavior IDs that are new
    old_ids = set()
    if old_behaviors and isinstance(old_behaviors, list):
        for b in old_behaviors:
            if isinstance(b, dict):
                old_ids.add(b.get("id", ""))

    new_stubs = []
    existing_impl = existing_component_intent.get("implementation", [])
    existing_impl_ids = set()
    if isinstance(existing_impl, list):
        for impl in existing_impl:
            if isinstance(impl, dict):
                existing_impl_ids.add(impl.get("id", ""))

    for behavior in new_behaviors:
        if not isinstance(behavior, dict):
            continue
        behavior_id = behavior.get("id", "")
        # Skip if already in component.intent implementation
        if behavior_id in existing_impl_ids:
            continue
        # Skip if this was in the old behaviors too
        if behavior_id in old_ids:
            continue

        # Create a stub implementation entry
        stub_id = f"{behavior_id}-IMPL"
        new_stubs.append({
            "id": stub_id,
            "intent": (
                f"# TODO: implement {behavior_id}\n"
                f"# Business intent: {behavior.get('intent', '').strip()[:100]}\n"
                f"# Add platform-specific implementation details here"
            )
        })

    if new_stubs:
        # Merge with existing implementation
        existing = list(existing_impl) if isinstance(existing_impl, list) else []
        updates["implementation"] = existing + new_stubs

    return updates


def _update_component_intent(
    component_intent_path: Path,
    component_intent: dict,
    updates: dict,
    component_name: str,
    module_changes: dict,
    language_changes: dict,
) -> dict:
    """
    Merge updates into component.intent file.
    Prints clear summary of what was added.
    Returns updated component intent dict.
    """
    if not updates:
        return component_intent

    # Merge updates
    updated = {**component_intent}
    for key, value in updates.items():
        updated[key] = value

    # Write updated component.intent
    updated_yaml = yaml.dump(updated, default_flow_style=False, allow_unicode=True)
    component_intent_path.write_text(updated_yaml, encoding="utf-8")

    # Inform developer what changed
    print(f"\n{Fore.CYAN}{'─' * 60}")
    print(f"component.intent updated — {component_name}")
    print(f"{'─' * 60}{Style.RESET_ALL}")

    if module_changes:
        print(f"{Fore.YELLOW}module.intent changed — these sections updated in component.intent:{Style.RESET_ALL}")
        for key in module_changes:
            if not key.startswith("_"):
                print(f"  + {key}")

    if language_changes:
        print(f"{Fore.YELLOW}language.intent changed — these sections updated in component.intent:{Style.RESET_ALL}")
        for key in language_changes:
            if not key.startswith("_"):
                print(f"  + {key}")

    if "implementation" in updates:
        new_stubs = [
            item for item in updates["implementation"]
            if isinstance(item, dict) and "TODO" in item.get("intent", "")
        ]
        if new_stubs:
            print(f"{Fore.CYAN}New implementation stubs added — fill these in:{Style.RESET_ALL}")
            for stub in new_stubs:
                print(f"  → {stub.get('id', '')}")

    print(f"{Fore.CYAN}{'─' * 60}{Style.RESET_ALL}\n")

    return updated


# ── Verification ──────────────────────────────────────────────────────────────

def _verify_output(generated_code: str, component_intent: dict) -> list[tuple[str, bool]]:
    results = []
    behaviors = component_intent.get("implementation", [])
    for behavior in behaviors:
        if isinstance(behavior, dict):
            behavior_id = behavior.get("id", "")
            intent_text = behavior.get("intent", "")
            keywords = [
                word.lower()
                for word in intent_text.split()
                if len(word) > 4
            ][:3]
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
    project_root = Path.cwd()
    start_time = time.time()

    try:
        # Pre-flight validation
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

        # Pass module and language intent for cross-level delta detection
        delta = DeltaEngine.compute(
            current_component_intent=context.component,
            lockfile=lockfile,
            current_module_intent=context.module,
            current_language_intent=context.language,
        )

        if delta.is_unchanged:
            print_success("Nothing changed — compilation skipped")
            print_info("Use --force to recompile anyway")
            return

        if delta.is_new:
            print_success("First compilation — full generation")
        else:
            changed = list(delta.changed_sections.keys())
            module_changed = list(delta.module_changes.keys())
            language_changed = list(delta.language_changes.keys())

            if changed:
                print_success(
                    f"Delta computed — component.intent changed: "
                    f"{', '.join(changed)}"
                )
            if module_changed:
                print_warning(
                    f"module.intent changed: {', '.join(k for k in module_changed if not k.startswith('_'))}"
                )
            if language_changed:
                print_warning(
                    f"language.intent changed: {', '.join(k for k in language_changed if not k.startswith('_'))}"
                )

        # ── Phase 3 — Inference ───────────────────────────────────────────────
        print_info(f"Phase 3 — Calling {config.provider} ({config.model})...")

        provider = _get_provider(config)
        prompt = PromptBuilder.build(context, delta, target)
        generated_code = provider.generate(prompt)

        print_success(f"Code received from {config.provider}")

        # ── Phase 4 — Write ───────────────────────────────────────────────────
        print_info("Phase 4 — Writing output...")

        # Determine output path
        file_field = context.component.get("file", "")
        if not file_field:
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

        # ── Update component.intent if module/language changed ────────────────
        component_intent_path = component_dir / f"{component_name}.intent"
        current_component_intent = context.component

        if delta.module_changes or delta.language_changes:
            intent_updates = _build_intent_stubs_for_module_changes(
                delta.module_changes,
                current_component_intent,
            )
            current_component_intent = _update_component_intent(
                component_intent_path,
                current_component_intent,
                intent_updates,
                component_name,
                delta.module_changes,
                delta.language_changes,
            )

        # ── Verify if --verify flag ───────────────────────────────────────────
        verified = False
        if verify:
            print_info("Running verification...")
            verification_results = _verify_output(generated_code, current_component_intent)
            verified = all(passed for _, passed in verification_results)
            for behavior_id, passed in verification_results:
                if passed:
                    print_success(f"  {behavior_id} — verified")
                else:
                    print_warning(f"  {behavior_id} — not verified (review manually)")

        # ── Write lockfile ────────────────────────────────────────────────────
        intent_hash = DeltaEngine.compute_hash(current_component_intent)
        generated_code_hash = hashlib.sha256(
            generated_code.encode("utf-8")
        ).hexdigest()

        # Store module and language hashes in snapshot for future delta detection
        snapshot = {**current_component_intent}
        if context.module:
            snapshot["_module_hash"] = DeltaEngine.compute_hash(context.module)
            snapshot["_module_snapshot"] = context.module
        if context.language:
            snapshot["_language_hash"] = DeltaEngine.compute_hash(context.language)
            snapshot["_language_snapshot"] = context.language

        entry = LockfileEntry(
            component_name=component_name,
            language=target.language,
            version=target.version,
            intent_hash=intent_hash,
            code_hash=generated_code_hash,
            provider=config.provider,
            model=config.model,
            generated_at=LockfileManager.now(),
            target=str(target),
            verified=verified,
            intent_snapshot=snapshot,
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