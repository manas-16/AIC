"""
AIC — AI Compiler
CLI entry point. All commands registered here.
"""

import click
from init.InitCommand.init_command import run_init


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

from create.CreateCommand.create_command import run_create

@cli.command()
@click.argument("component_name")
@click.option("--language", required=True, help="Target language folder")
def create(component_name: str, language: str):
    """
    Scaffold a new component with intent and code stub.

    COMPONENT_NAME must be PascalCase (e.g. UserService)
    """
    run_create(component_name, language)


from compile.CompileCommand.compile_command import run_compile

@cli.command(name="compile")
@click.argument("component_name")
@click.option("--target", required=True, help="Target language e.g. python or python@3.11")
@click.option("--force", is_flag=True, default=False, help="Force full regeneration")
@click.option("--verify", is_flag=True, default=False, help="Verify output after generation")
def compile_component(component_name, target, force, verify):
    """Compile a component intent file to target language."""
    run_compile(component_name, target, force, verify)
# Future commands registered here as they are built
# @cli.command()
# def create(): ...

# @cli.command()
# def compile(): ...

# @cli.command()
# def navigate(): ...

# @cli.command()
# def sync(): ...

# @cli.command()
# def status(): ...

# @cli.command()
# def audit(): ...


if __name__ == "__main__":
    cli()
