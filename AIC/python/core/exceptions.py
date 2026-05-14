"""
AIC Custom Exceptions
All errors are explicit — no bare except clauses anywhere in AIC.
Exit codes: 0 = success, 1 = user error, 2 = system error
"""


class AICError(Exception):
    """Base exception for all AIC errors."""
    exit_code: int = 1


class GitNotInitialisedError(AICError):
    """Raised when aic is run outside a git repository."""
    exit_code = 1
    message = (
        "No git repository detected in the current directory.\n"
        "AIC requires git to be initialised.\n"
        "Run: git init\n"
        "Then retry: aic init"
    )


class AlreadyInitialisedError(AICError):
    """Raised when aic init is run in an already initialised project."""
    exit_code = 1
    message = (
        "AIC is already initialised in this directory.\n"
        "project.intent already exists.\n"
        "Run: aic status to check your project state."
    )


class FolderCreationError(AICError):
    """Raised when a required folder cannot be created."""
    exit_code = 2

    def __init__(self, path: str):
        self.path = path
        self.message = (
            f"Failed to create folder: {path}\n"
            "Check that you have write permissions to this directory."
        )
        super().__init__(self.message)


class IntentLibraryMissingError(AICError):
    """Raised when the AIC intent library cannot be found in the installation."""
    exit_code = 2
    message = (
        "AIC intent library not found in installation.\n"
        "Your AIC installation may be corrupted.\n"
        "Run: pip install --force-reinstall aic"
    )


class PermissionDeniedError(AICError):
    """Raised when AIC cannot write to a path due to permissions."""
    exit_code = 2

    def __init__(self, path: str):
        self.path = path
        self.message = (
            f"Permission denied: {path}\n"
            "Check that you have write permissions to this directory."
        )
        super().__init__(self.message)


class ConfigNotFoundError(AICError):
    """Raised when aic.config.json is missing."""
    exit_code = 1
    message = (
        "AIC configuration not found.\n"
        "Run: aic init to initialise your project first."
    )
