"""
AIC Delta Engine
Computes what changed between old and new intent.
Phase 2 of compilation — fully deterministic, zero LLM.

The delta is the ONLY thing sent to the AI in Phase 3.
This is what makes AIC delta-based not full-regeneration.
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
    If is_new is True — no previous version exists, full generation needed.
    If is_unchanged is True — nothing changed, skip compilation.
    Otherwise changed_sections contains only what changed.
    """
    is_new: bool = False
    is_unchanged: bool = False
    changed_sections: dict = field(default_factory=dict)
    full_intent: dict = field(default_factory=dict)


class DeltaEngine:
    """Computes intent delta between current and lockfile snapshot."""

    @staticmethod
    def compute_hash(intent: dict) -> str:
        """
        Compute SHA256 hash of intent dict.
        Used to detect changes between compilations.
        Deterministic — same intent always produces same hash.
        """
        serialised = json.dumps(intent, sort_keys=True, ensure_ascii=True)
        return hashlib.sha256(serialised.encode("utf-8")).hexdigest()

    @staticmethod
    def compute(
        current_component_intent: dict,
        lockfile: Optional[LockfileEntry],
    ) -> IntentDelta:
        """
        Compare current intent against lockfile snapshot.

        Three outcomes:
          1. No lockfile → is_new=True → full generation
          2. Hash matches → is_unchanged=True → skip compilation
          3. Hash differs → changed_sections contains delta → partial update
        """
        current_hash = DeltaEngine.compute_hash(current_component_intent)

        # Case 1 — no lockfile, first compilation
        if lockfile is None:
            return IntentDelta(
                is_new=True,
                full_intent=current_component_intent,
            )

        # Case 2 — nothing changed
        if current_hash == lockfile.intent_hash:
            return IntentDelta(is_unchanged=True)

        # Case 3 — compute delta
        old_intent = lockfile.intent_snapshot
        changed_sections = DeltaEngine._diff_dicts(old_intent, current_component_intent)

        return IntentDelta(
            changed_sections=changed_sections,
            full_intent=current_component_intent,
        )

    @staticmethod
    def _diff_dicts(old: dict, new: dict) -> dict:
        """
        Find keys that changed, were added, or were removed.
        Returns dict containing only changed sections.
        """
        changed = {}

        all_keys = set(old.keys()) | set(new.keys())
        for key in all_keys:
            old_val = old.get(key)
            new_val = new.get(key)
            if old_val != new_val:
                changed[key] = {
                    "old": old_val,
                    "new": new_val,
                }

        return changed
