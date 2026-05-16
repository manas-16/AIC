"""
AIC Delta Engine v2
Computes what changed between old and new intent.
Phase 2 of compilation — fully deterministic, zero LLM.

Tracks delta source — which level of the inheritance chain changed.
This is used by compile to know what to update in component.intent.
"""

import hashlib
import json
from dataclasses import dataclass, field
from typing import Optional

from models.lockfile import LockfileEntry


@dataclass
class IntentDelta:
    """
    Represents what changed between old and new intent.

    is_new        — no lockfile, first compilation, full generation
    is_unchanged  — nothing changed, skip compilation
    changed_sections — what changed in component.intent
    module_changes   — what changed in module.intent (business level)
    language_changes — what changed in language.intent
    full_intent   — current full component intent
    """
    is_new: bool = False
    is_unchanged: bool = False
    changed_sections: dict = field(default_factory=dict)
    module_changes: dict = field(default_factory=dict)    # ← new
    language_changes: dict = field(default_factory=dict)  # ← new
    full_intent: dict = field(default_factory=dict)


class DeltaEngine:
    """Computes intent delta between current and lockfile snapshot."""

    @staticmethod
    def compute_hash(intent: dict) -> str:
        """Compute SHA256 hash of intent dict."""
        serialised = json.dumps(intent, sort_keys=True, ensure_ascii=True)
        return hashlib.sha256(serialised.encode("utf-8")).hexdigest()

    @staticmethod
    def compute(
        current_component_intent: dict,
        lockfile: Optional[LockfileEntry],
        current_module_intent: dict = None,
        current_language_intent: dict = None,
    ) -> IntentDelta:
        """
        Compare current intent against lockfile snapshot.
        Also tracks changes at module and language level.
        """
        current_hash = DeltaEngine.compute_hash(current_component_intent)

        # Case 1 — no lockfile, first compilation
        if lockfile is None:
            return IntentDelta(
                is_new=True,
                full_intent=current_component_intent,
            )

        # Case 2 — nothing changed at any level
        component_unchanged = current_hash == lockfile.intent_hash

        # Check module level changes
        module_changes = {}
        if current_module_intent:
            stored_module_hash = lockfile.intent_snapshot.get("_module_hash", "")
            current_module_hash = DeltaEngine.compute_hash(current_module_intent)
            if stored_module_hash and current_module_hash != stored_module_hash:
                old_module = lockfile.intent_snapshot.get("_module_snapshot", {})
                module_changes = DeltaEngine._diff_dicts(old_module, current_module_intent)

        # Check language level changes
        language_changes = {}
        if current_language_intent:
            stored_language_hash = lockfile.intent_snapshot.get("_language_hash", "")
            current_language_hash = DeltaEngine.compute_hash(current_language_intent)
            if stored_language_hash and current_language_hash != stored_language_hash:
                old_language = lockfile.intent_snapshot.get("_language_snapshot", {})
                language_changes = DeltaEngine._diff_dicts(old_language, current_language_intent)

        # If nothing changed at any level
        if component_unchanged and not module_changes and not language_changes:
            return IntentDelta(is_unchanged=True)

        # Compute component delta
        changed_sections = {}
        if not component_unchanged:
            old_intent = lockfile.intent_snapshot
            changed_sections = DeltaEngine._diff_dicts(old_intent, current_component_intent)

        return IntentDelta(
            changed_sections=changed_sections,
            module_changes=module_changes,
            language_changes=language_changes,
            full_intent=current_component_intent,
        )

    @staticmethod
    def _diff_dicts(old: dict, new: dict) -> dict:
        """Find keys that changed, were added, or were removed."""
        changed = {}
        all_keys = set(old.keys()) | set(new.keys())
        for key in all_keys:
            # Skip internal tracking keys
            if key.startswith("_"):
                continue
            old_val = old.get(key)
            new_val = new.get(key)
            if old_val != new_val:
                changed[key] = {
                    "old": old_val,
                    "new": new_val,
                }
        return changed