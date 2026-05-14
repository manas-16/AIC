#!/bin/bash

# AIC — AI Compiler
# Project scaffold script
# Creates the complete folder structure with empty files
# Run from the root of your AIC repository

set -e

echo "Creating AIC project structure..."

# ── Root level ────────────────────────────────────────────────────────────────
touch project.intent
touch NAVIGATION.intent
touch README.md
touch setup.py
touch .gitignore

# ── Business intent folder ────────────────────────────────────────────────────
mkdir -p business/init
mkdir -p business/create
mkdir -p business/compile
mkdir -p business/sync
mkdir -p business/status
mkdir -p business/audit
mkdir -p business/validate
mkdir -p business/navigate
mkdir -p business/transpile

touch business/init/module.intent
touch business/create/module.intent
touch business/compile/module.intent
touch business/sync/module.intent
touch business/status/module.intent
touch business/audit/module.intent
touch business/validate/module.intent
touch business/navigate/module.intent
touch business/transpile/module.intent

# ── Python language folder ────────────────────────────────────────────────────
mkdir -p python/init/InitCommand
mkdir -p python/create/CreateCommand
mkdir -p python/compile/CompileCommand
mkdir -p python/sync/SyncCommand
mkdir -p python/status/StatusCommand
mkdir -p python/audit/AuditCommand
mkdir -p python/validate/ValidateCommand
mkdir -p python/navigate/NavigateCommand
mkdir -p python/transpile/TranspileCommand

touch python/python.intent

touch python/init/InitCommand/InitCommand.intent
touch python/init/InitCommand/init_command.py

touch python/create/CreateCommand/CreateCommand.intent
touch python/create/CreateCommand/create_command.py

touch python/compile/CompileCommand/CompileCommand.intent
touch python/compile/CompileCommand/compile_command.py

touch python/sync/SyncCommand/SyncCommand.intent
touch python/sync/SyncCommand/sync_command.py

touch python/status/StatusCommand/StatusCommand.intent
touch python/status/StatusCommand/status_command.py

touch python/audit/AuditCommand/AuditCommand.intent
touch python/audit/AuditCommand/audit_command.py

touch python/validate/ValidateCommand/ValidateCommand.intent
touch python/validate/ValidateCommand/validate_command.py

touch python/navigate/NavigateCommand/NavigateCommand.intent
touch python/navigate/NavigateCommand/navigate_command.py

touch python/transpile/TranspileCommand/TranspileCommand.intent
touch python/transpile/TranspileCommand/transpile_command.py

# ── AIC package (Python source) ───────────────────────────────────────────────
mkdir -p aic/commands
mkdir -p aic/core
mkdir -p aic/models
mkdir -p aic/utils
mkdir -p aic/providers
mkdir -p aic/templates

touch aic/__init__.py
touch aic/main.py

touch aic/commands/__init__.py
touch aic/commands/init_command.py
touch aic/commands/create_command.py
touch aic/commands/compile_command.py
touch aic/commands/sync_command.py
touch aic/commands/status_command.py
touch aic/commands/audit_command.py
touch aic/commands/validate_command.py
touch aic/commands/navigate_command.py
touch aic/commands/transpile_command.py

touch aic/core/__init__.py
touch aic/core/exceptions.py
touch aic/core/intent_parser.py
touch aic/core/inheritance_resolver.py
touch aic/core/lockfile_manager.py
touch aic/core/delta_engine.py

touch aic/models/__init__.py
touch aic/models/intent.py
touch aic/models/lockfile.py
touch aic/models/config.py

touch aic/utils/__init__.py
touch aic/utils/terminal.py
touch aic/utils/git.py
touch aic/utils/file_utils.py

touch aic/providers/__init__.py
touch aic/providers/base_provider.py
touch aic/providers/claude_provider.py
touch aic/providers/gemini_provider.py
touch aic/providers/ollama_provider.py

touch aic/templates/project.intent.template
touch aic/templates/NAVIGATION.intent.template
touch aic/templates/aic.config.template.json
touch aic/templates/module.intent.template
touch aic/templates/component.intent.template
touch aic/templates/language.intent.template

# ── Tests ─────────────────────────────────────────────────────────────────────
mkdir -p tests/commands
mkdir -p tests/core
mkdir -p tests/utils
mkdir -p tests/providers

touch tests/__init__.py
touch tests/commands/__init__.py
touch tests/commands/test_init_command.py
touch tests/commands/test_create_command.py
touch tests/commands/test_compile_command.py
touch tests/commands/test_sync_command.py
touch tests/commands/test_status_command.py
touch tests/commands/test_navigate_command.py

touch tests/core/__init__.py
touch tests/core/test_intent_parser.py
touch tests/core/test_inheritance_resolver.py
touch tests/core/test_lockfile_manager.py
touch tests/core/test_delta_engine.py

touch tests/utils/__init__.py
touch tests/utils/test_git.py
touch tests/utils/test_file_utils.py

touch tests/providers/__init__.py
touch tests/providers/test_claude_provider.py
touch tests/providers/test_gemini_provider.py

# ── Standards ─────────────────────────────────────────────────────────────────
mkdir -p standards
touch standards/pylint.cfg
touch standards/black.toml
touch standards/mypy.ini
touch standards/radon.cfg

# ── Done ──────────────────────────────────────────────────────────────────────
echo ""
echo "✓ AIC project structure created successfully"
echo ""
echo "Structure:"
find . -not -path './.git/*' -not -path './.git' | sort | sed 's|[^/]*/|  |g'
echo ""
echo "Next steps:"
echo "  1. Copy intent files from our design session into business/ and python/"
echo "  2. Copy working code from aic init into aic/commands/init_command.py"
echo "  3. Run: git add . && git commit -m 'chore: initial project structure'"
