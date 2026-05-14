"""
AIC Terminal Output Utility
Wraps colorama to provide consistent terminal output across AIC.
Degrades gracefully if color support is not available.
"""

import sys
from colorama import Fore, Style, init

# Initialise colorama — handles Windows color support automatically
init(autoreset=True)


def print_success(message: str) -> None:
    """Print a green success message."""
    print(f"{Fore.GREEN}✓ {message}{Style.RESET_ALL}")


def print_error(message: str) -> None:
    """Print a red error message to stderr."""
    print(f"{Fore.RED}✗ {message}{Style.RESET_ALL}", file=sys.stderr)


def print_warning(message: str) -> None:
    """Print a yellow warning message."""
    print(f"{Fore.YELLOW}⚠ {message}{Style.RESET_ALL}")


def print_info(message: str) -> None:
    """Print a blue informational message."""
    print(f"{Fore.CYAN}→ {message}{Style.RESET_ALL}")


def print_header(title: str) -> None:
    """Print a bold section header."""
    width = max(len(title) + 4, 50)
    border = "─" * width
    print(f"\n{Fore.BLUE}{border}")
    print(f"  {title}")
    print(f"{border}{Style.RESET_ALL}\n")


def print_tree(items: list[tuple[str, str]]) -> None:
    """
    Print a tree of created files and folders.
    Each item is a tuple of (path, description).
    """
    print(f"{Fore.BLUE}Created:{Style.RESET_ALL}")
    for i, (path, description) in enumerate(items):
        is_last = i == len(items) - 1
        connector = "└──" if is_last else "├──"
        print(f"  {Fore.BLUE}{connector}{Style.RESET_ALL} {path}"
              f"  {Fore.WHITE}{Style.DIM}{description}{Style.RESET_ALL}")


def print_next_steps(steps: list[str]) -> None:
    """Print numbered next steps for the developer."""
    print(f"\n{Fore.CYAN}Next steps:{Style.RESET_ALL}")
    for i, step in enumerate(steps, 1):
        print(f"  {Fore.CYAN}{i}.{Style.RESET_ALL} {step}")
    print()


def print_panel(title: str, lines: list[str], color: str = Fore.BLUE) -> None:
    """Print a bordered panel with title and content lines."""
    width = max(len(title) + 4, max((len(l) for l in lines), default=0) + 4, 50)
    border = "─" * width
    print(f"\n{color}{border}")
    print(f"  {title}")
    print(f"{border}{Style.RESET_ALL}")
    for line in lines:
        print(f"  {line}")
    print(f"{color}{border}{Style.RESET_ALL}\n")
