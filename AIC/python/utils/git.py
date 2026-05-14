"""
AIC Git Utility
All git interactions are isolated here.
Uses subprocess — never shell=True.
"""

import subprocess
from pathlib import Path


def is_git_repository(path: Path) -> bool:
    """
    Check if the given path is inside a git repository.
    Returns True if git is initialised, False otherwise.
    """
    result = subprocess.run(
        ["git", "rev-parse", "--git-dir"],
        cwd=path,
        capture_output=True,
        text=True
    )
    return result.returncode == 0


def get_remote_url(path: Path) -> str:
    """
    Get the git remote origin URL for the given path.
    Returns empty string if no remote is configured — not an error.
    """
    result = subprocess.run(
        ["git", "remote", "get-url", "origin"],
        cwd=path,
        capture_output=True,
        text=True
    )
    if result.returncode == 0:
        return result.stdout.strip()
    return ""


def get_project_name(path: Path) -> str:
    """
    Derive project name from the current directory name.
    Falls back to folder name if git remote is not available.
    """
    return path.name
