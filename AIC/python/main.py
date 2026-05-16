"""
AIC — AI Compiler
CLI entry point. All commands registered here.

Commands:
  aic init      ← initialise AIC in current directory
  aic create    ← scaffold a new component
  aic compile   ← compile intent to code via AI
  aic validate  ← validate a .intent file against AIC guidelines
  aic status    ← check sync state of all components
  aic navigate  ← assemble scoped context for AI chat
"""

import os
import sys
import click

CURRENT_DIR = os.path.dirname(os.path.abspath(__file__))
PROJECT_ROOT = os.path.dirname(CURRENT_DIR)

if CURRENT_DIR not in sys.path:
    sys.path.insert(0, CURRENT_DIR)
if PROJECT_ROOT not in sys.path:
    sys.path.insert(0, PROJECT_ROOT)

from init.InitCommand.init_command import run_init
from create.CreateCommand.create_command import run_create
from compile.CompileCommand.compile_command import run_compile
from status.StatusCommand.status_command import run_status
from navigate.NavigateCommand.navigate_command import run_navigate
from validate.ValidateCommand.validate_command import run_validate


@click.group()
@click.version_option(version="0.1.0", prog_name="aic")
def cli():
    """
    AIC — AI Compiler

    Compile .intent files to any target language.
    Bridge your repository and your AI.

    Documentation: https://github.com/manas-16/AIC
    """
    pass


@cli.command()
def init():
    """
    Initialise AIC in the current directory.

    Creates the base folder structure, generates a boilerplate
    project.intent, and installs the AIC intent library as a
    read-only reference.

    Requirements:
      - Must be run inside a git repository (git init first)
      - Will not overwrite an existing AIC project
    """
    run_init()


@cli.command()
@click.argument("component_name")
@click.option("--language", required=True, help="Target language folder")
@click.option("--path", "custom_path", default=None, 
              help="Custom path relative to project root (skips subfolder creation)")
def create(component_name: str, language: str, custom_path: str):
    """
    Scaffold a new component with intent and code stub.

    Standard mode — creates subfolder + intent + stub:
      aic create UserService --language python

    Path mode — creates intent only at exact path:
      aic create UserService --language apex --path force-app/main/default/classes
      aic create UserCard --language lwc --path force-app/main/default/lwc/userCard
    """
    run_create(component_name, language, custom_path)


@cli.command(name="compile")
@click.argument("component_name")
@click.option(
    "--target", required=True,
    help="Target language and optional version e.g. python or python@3.11"
)
@click.option(
    "--force", is_flag=True, default=False,
    help="Force full regeneration — ignores lockfile"
)
@click.option(
    "--verify", is_flag=True, default=False,
    help="Run static verification after generation"
)
def compile_component(component_name: str, target: str, force: bool, verify: bool):
    """
    Compile a component intent file to target language using AI.

    COMPONENT_NAME must match an existing component folder.

    Uses delta-based compilation — only changed sections sent to AI.
    Writes a lockfile on completion.

    Examples:
      aic compile UserService --target python
      aic compile UserService --target java@21
      aic compile UserService --target python --force
      aic compile UserService --target python --verify
    """
    run_compile(component_name, target, force, verify)


@cli.command()
@click.option(
    "--component", default=None,
    help="Filter to one component only"
)
@click.option(
    "--language", default=None,
    help="Filter to one language only"
)
@click.option(
    "--expand", is_flag=True, default=False,
    help="Show per-file detail for multi-file components"
)
def status(component: str, language: str, expand: bool):
    """
    Show sync state of all components across all languages.

    Three states:
      ✓ IN SYNC   — intent and code are aligned
      ⚠ STALE     — intent changed, recompile needed
      ✗ DRIFT     — code manually changed, sync needed
      ✗ VIOLATION — code violates declared guidelines

    Examples:
      aic status
      aic status --component UserService
      aic status --language python
      aic status --expand
    """
    run_status(component, language, expand)


@cli.command()
@click.argument("intent_file")
def validate(intent_file: str):
    """
    Validate a .intent file against AIC intent and project guidelines.

    Examples:
      aic validate business/UserService/module.intent
      aic validate python/UserService/UserService.intent
    """
    run_validate(intent_file)


@cli.command()
@click.option(
    "--query", required=True,
    help="Natural language description of your task"
)
@click.option(
    "--copy", is_flag=True, default=False,
    help="Copy context to clipboard automatically"
)
@click.option(
    "--file", "to_file", is_flag=True, default=False,
    help="Write context to .aic/context/ folder"
)
def navigate(query: str, copy: bool, to_file: bool):
    """
    Assemble scoped intent context for your AI chat.

    Reads the right intent files for your query and assembles
    them into a context block ready to paste into any AI tool.

    Zero LLM — fully deterministic file traversal.

    Examples:
      aic navigate --query "fix account lockout in python"
      aic navigate --query "UserService android" --copy
      aic navigate --query "payment flow" --file

    v1 note: Paste the output into your AI chat before your question.
    MCP server integration coming in v2.
    """
    run_navigate(query, copy, to_file)

from sync.SyncCommand.sync_command import run_sync

@cli.command()
@click.argument("component_name")
@click.option("--language", required=True, help="Language of the component")
@click.option("--approve", is_flag=True, default=False, help="Approve pending proposal")
@click.option("--reject", is_flag=True, default=False, help="Reject pending proposal")
def sync(component_name: str, language: str, approve: bool, reject: bool):
    """
    Sync manual code changes back to component.intent as a proposal.

    Detects drift, asks AI to interpret changes in intent language,
    writes a proposal for developer review before committing.

    Examples:
      aic sync UserService --language python
      aic sync UserService --language python --approve
      aic sync UserService --language python --reject
    """
    run_sync(component_name, language, approve, reject)

from ask.AskCommand.ask_command import run_ask

@cli.command()
@click.option("--query", required=True, help="Your question or fix request")
@click.option("--fix", is_flag=True, default=False, help="Apply fix to code files")
@click.option("--language", default=None, help="Scope to one language (required for fix with multiple languages)")
def ask(query: str, fix: bool, language: str):
    """
    Ask AI a question or request a fix using your repository context.

    Question mode (default):
      aic ask --query "how does UserService handle auth"

    Fix mode:
      aic ask --query "fix null check in UserService" --fix
      aic ask --query "fix UserService" --fix --language python
    """
    run_ask(query, fix, language)

if __name__ == "__main__":
    cli()
