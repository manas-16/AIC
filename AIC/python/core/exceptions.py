"""
AIC Custom Exceptions
All errors are explicit — no bare except clauses anywhere in AIC.
Exit codes: 0 = success, 1 = user error, 2 = system error
"""


class AICError(Exception):
    """Base exception for all AIC errors."""
    exit_code: int = 1
    message: str = "An unexpected error occurred."


class GitNotInitialisedError(AICError):
    exit_code = 1
    message = (
        "No git repository detected in the current directory.\n"
        "AIC requires git to be initialised.\n"
        "Run: git init\n"
        "Then retry."
    )


class AlreadyInitialisedError(AICError):
    exit_code = 1
    message = (
        "AIC is already initialised in this directory.\n"
        "project.intent already exists.\n"
        "Run: aic status to check your project state."
    )


class NotInitialisedError(AICError):
    exit_code = 1
    message = (
        "AIC is not initialised in this directory.\n"
        "Run: aic init"
    )


class FolderCreationError(AICError):
    exit_code = 2

    def __init__(self, path: str):
        self.path = path
        self.message = (
            f"Failed to create folder: {path}\n"
            "Check that you have write permissions to this directory."
        )
        super().__init__(self.message)


class IntentLibraryMissingError(AICError):
    exit_code = 2
    message = (
        "AIC intent library not found in installation.\n"
        "Your AIC installation may be corrupted.\n"
        "Run: pip install --force-reinstall aic"
    )


class PermissionDeniedError(AICError):
    exit_code = 2

    def __init__(self, path: str):
        self.path = path
        self.message = (
            f"Permission denied: {path}\n"
            "Check that you have write permissions to this directory."
        )
        super().__init__(self.message)


class ConfigNotFoundError(AICError):
    exit_code = 1
    message = (
        "AIC configuration not found.\n"
        "Run: aic init to initialise your project first."
    )


class ProviderNotConfiguredError(AICError):
    exit_code = 1
    message = (
        "AI provider not configured.\n"
        "Fill in .aic/aic.config.json with your provider details.\n"
        "Supported providers: claude, gemini, ollama\n"
        "Example config:\n"
        "  provider: claude\n"
        "  model: claude-sonnet-4-5\n"
        "  apiKey: ${ANTHROPIC_API_KEY}"
    )


class InvalidComponentNameError(AICError):
    exit_code = 1

    def __init__(self, name: str):
        self.message = (
            f"Invalid component name: '{name}'\n"
            "Component names must be PascalCase.\n"
            "Valid examples:   UserService, PaymentRepository, AuthManager\n"
            "Invalid examples: userService, user_service, user service"
        )
        super().__init__(self.message)


class ComponentAlreadyExistsError(AICError):
    exit_code = 1

    def __init__(self, component_name: str, language: str):
        self.message = (
            f"Component already exists: /{language}/{component_name}\n"
            "AIC will not overwrite existing components.\n"
            "Run: aic status to check current component state."
        )
        super().__init__(self.message)


class ComponentNotFoundError(AICError):
    exit_code = 1

    def __init__(self, component_name: str, language: str):
        self.message = (
            f"Component not found: /{language}/{component_name}\n"
            f"Run: aic create {component_name} --language {language}"
        )
        super().__init__(self.message)


class LanguageFolderMissingError(AICError):
    exit_code = 1

    def __init__(self, language: str):
        self.language = language
        self.message = (
            f"Language folder not found: /{language}\n"
            f"Create it first with a {language}.intent file."
        )
        super().__init__(self.message)


class IntentParseError(AICError):
    exit_code = 1

    def __init__(self, file_path: str, reason: str):
        self.file_path = file_path
        self.reason = reason
        self.message = f"Failed to parse {file_path}:\n{reason}"
        super().__init__(self.message)


class OutputWriteError(AICError):
    exit_code = 2

    def __init__(self, path: str):
        self.message = (
            f"Failed to write output file: {path}\n"
            "Check write permissions."
        )
        super().__init__(self.message)


class LockfileWriteError(AICError):
    exit_code = 2

    def __init__(self, path: str):
        self.message = (
            f"Failed to write lockfile: {path}\n"
            "Output file was written. Lockfile will be missing.\n"
            "Run: aic compile again to regenerate lockfile."
        )
        super().__init__(self.message)
