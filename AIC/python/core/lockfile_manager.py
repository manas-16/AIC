"""
AIC Lockfile Manager
Reads and writes lockfiles for component compilation state.
Phase 1 (read) and Phase 4 (write) — fully deterministic.

Lockfiles stored at: .aic/lockfiles/<ComponentName>-<language>.lock
"""

import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional

from models.lockfile import LockfileEntry
from models.intent import CompileTarget


class LockfileManager:
    """Manages lockfile read and write operations."""

    def __init__(self, project_root: Path):
        self.lockfile_dir = project_root / ".aic" / "lockfiles"

    def _lockfile_path(self, component_name: str, target: CompileTarget) -> Path:
        """Compute lockfile path for a component and target."""
        filename = f"{component_name}-{target}.lock"
        return self.lockfile_dir / filename

    def read(
        self,
        component_name: str,
        target: CompileTarget,
    ) -> Optional[LockfileEntry]:
        """
        Read existing lockfile for a component.
        Returns None if no lockfile exists — not an error.
        First compilation has no lockfile.
        """
        lockfile_path = self._lockfile_path(component_name, target)
        if not lockfile_path.exists():
            return None

        try:
            with open(lockfile_path, encoding="utf-8") as f:
                data = json.load(f)
            return LockfileEntry.from_dict(data)
        except (json.JSONDecodeError, KeyError):
            # Corrupted lockfile — treat as no lockfile
            return None

    def write(self, entry: LockfileEntry, target: CompileTarget) -> None:
        """
        Write lockfile for a component.
        Only called after successful code generation and file write.
        Never written if compilation failed.
        """
        self.lockfile_dir.mkdir(parents=True, exist_ok=True)
        lockfile_path = self._lockfile_path(entry.component_name, target)

        with open(lockfile_path, "w", encoding="utf-8") as f:
            json.dump(entry.to_dict(), f, indent=2)

    def delete(self, component_name: str, target: CompileTarget) -> None:
        """
        Delete lockfile — used by --force flag.
        Silent if lockfile does not exist.
        """
        lockfile_path = self._lockfile_path(component_name, target)
        if lockfile_path.exists():
            lockfile_path.unlink()

    @staticmethod
    def now() -> str:
        """Return current UTC timestamp as ISO string."""
        return datetime.now(timezone.utc).isoformat()
