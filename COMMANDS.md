# AIC CLI Commands Reference

Complete guide to all AIC (AI Compiler) commands and their usage.

---

## Table of Contents

1. [Project Initialization](#project-initialization)
2. [Component Management](#component-management)
3. [Compilation & Code Generation](#compilation--code-generation)
4. [Code Synchronization](#code-synchronization)
5. [Validation & Auditing](#validation--auditing)
6. [AI Interaction](#ai-interaction)
7. [Project Navigation](#project-navigation)
8. [Multi-Target Operations](#multi-target-operations)

---

## Project Initialization

### `aic init`

Initialize AIC in the current directory. Creates the base folder structure, generates a boilerplate `project.intent`, and installs the AIC intent library as a read-only reference.

**Requirements:**
- Must be run inside a git repository (`git init` first if needed)
- Will not overwrite an existing AIC project

**Usage:**
```bash
aic init
```

**What it creates:**
- `.aic/` — AIC configuration and metadata folder
- `project.intent` — Organization-wide standards and architecture declarations
- Initial folder structure ready for adding modules and components

---

## Component Management

### `aic create`

Scaffold a new component with intent file and code stub.

**Syntax:**
```bash
aic create <COMPONENT_NAME> --language <LANGUAGE_FOLDER> [--path <CUSTOM_PATH>]
```

**Options:**
- `<COMPONENT_NAME>` — Name of the component to create (e.g., `UserService`, `AuthHelper`)
- `--language <LANGUAGE_FOLDER>` **(required)** — Target language folder (e.g., `python`, `java`, `typescript`)
- `--path <CUSTOM_PATH>` — Custom path relative to project root (skips subfolder creation)

**Modes:**

**Standard mode** — Creates subfolder + intent + stub:
```bash
aic create UserService --language python
# Creates: python/UserService/UserService.intent and UserService.py
```

**Path mode** — Creates intent only at exact path:
```bash
aic create UserService --language apex --path force-app/main/default/classes
aic create UserCard --language lwc --path force-app/main/default/lwc/userCard
```

**What it creates:**
- `<LANGUAGE>/<COMPONENT_NAME>/<COMPONENT_NAME>.intent` — Component intent file
- `<LANGUAGE>/<COMPONENT_NAME>/<COMPONENT_NAME>.[ext]` — Code stub file
- Inherits from `business/<MODULE_NAME>/module.intent` (detected automatically)

---

## Compilation & Code Generation

### `aic compile`

Compile a component intent file to target language using AI. Uses **delta-based compilation** — only changed sections are sent to AI.

**Syntax:**
```bash
aic compile <COMPONENT_NAME> --target <LANGUAGE[@VERSION]> [--force] [--verify]
```

**Arguments:**
- `<COMPONENT_NAME>` — Must match an existing component folder

**Options:**
- `--target <LANGUAGE[@VERSION]>` **(required)** — Target language and optional version (e.g., `python`, `python@3.11`, `java@21`)
- `--force` — Force full regeneration, ignores lockfile
- `--verify` — Run static verification after generation

**Examples:**
```bash
aic compile UserService --target python
aic compile UserService --target java@21
aic compile UserService --target python --force
aic compile UserService --target python --verify
```

**What happens:**
1. **Phase 1 — Retrieval** — Reads project.intent, module.intent, language.intent, and component.intent
2. **Phase 2 — Diff** — Detects what changed in all intent files (deterministic)
3. **Phase 3 — Inference** — Sends only changed sections to AI provider (LLM call)
4. **Phase 4 — Write** — Updates component code file and creates lockfile

**Output:**
- Updated `<LANGUAGE>/<COMPONENT_NAME>/<COMPONENT_NAME>.[ext]` code file
- `.aic/lockfiles/<COMPONENT_NAME>.<LANGUAGE>.lock` — Tracks compilation state

---

## Code Synchronization

### `aic sync`

Detect manual code changes and sync them back to `component.intent` as a proposal.

**Syntax:**
```bash
aic sync <COMPONENT_NAME> --language <LANGUAGE> [--approve] [--reject]
```

**Arguments:**
- `<COMPONENT_NAME>` — Component to sync

**Options:**
- `--language <LANGUAGE>` **(required)** — Language of the component (e.g., `python`, `java`)
- `--approve` — Approve the pending sync proposal and write to intent
- `--reject` — Reject the pending sync proposal

**Examples:**
```bash
aic sync UserService --language python
aic sync UserService --language python --approve
aic sync UserService --language python --reject
```

**Workflow:**
1. Compares current code against current `component.intent`
2. Uses AI to interpret changes in intent language
3. Displays a proposal for developer review
4. Developer approves or rejects the changes
5. If approved, updates `component.intent` with suggested changes

---

## Delta Code Compilation Workflow (Important)

For **efficient delta-based compilation** that keeps all intent levels in sync:

### Scenario: Changes made to intent at multiple levels

When you modify intent at a higher level (e.g., `module.intent` or `language.intent`), the compiled component may inherit new standards or requirements:

**Step 1: Compile with --force to regenerate**
```bash
aic compile UserService --target python --force
```
- This tells AIC to ignore the lockfile and regenerate the entire component
- Ensures all changes from higher-level intent files are reflected in the code

**Step 2: Run sync to update component.intent**
```bash
aic sync UserService --language python
```
- After compilation regenerates code based on parent intent changes, sync ensures that `component.intent` is also updated to reflect the new inherited standards
- This prevents false "STALE" status in next sync check
- The component now has a consistent intent chain: `project.intent` → `language.intent` → `module.intent` → `component.intent`

**Complete workflow:**
```bash
# Edit module.intent (e.g., add new business rule)
# Edit language.intent (e.g., update coding standards)

# Force recompile to pick up parent changes
aic compile UserService --target python --force

# Sync component.intent to capture inherited changes
aic sync UserService --language python --approve

# Now component is fully in sync across all levels
aic status --component UserService
```

---

## Validation & Auditing

### `aic validate`

Validate a `.intent` file against AIC intent guidelines and project standards.

**Syntax:**
```bash
aic validate <INTENT_FILE>
```

**Arguments:**
- `<INTENT_FILE>` — Path to the intent file to validate

**Examples:**
```bash
aic validate business/UserService/module.intent
aic validate python/UserService/UserService.intent
aic validate project.intent
```

**Checks:**
- Syntax validity of YAML
- Adherence to AIC intent schema
- Compliance with declared project guidelines
- Required fields and structure

### `aic audit`

Strictly audit a code file against its declared intent files. No opinions, only compliance.

**Syntax:**
```bash
aic audit <FILE_PATH>
```

**Arguments:**
- `<FILE_PATH>` — Path to code file to audit

**Examples:**
```bash
aic audit python/UserService/user_service.py
aic audit java/UserService/UserService.java
aic audit force-app/main/default/classes/AccountService.cls
```

**Exit codes:**
- `0` — All rules pass
- `1` — One or more rules fail

**What it checks:**
- Code compliance against `project.intent` rules
- Code compliance against `language.intent` rules
- Code compliance against `business/<MODULE>/module.intent` rules
- Code compliance against `component.intent` rules
- **No suggestions, no style opinions — only declared intent rules**

---

## Status Reporting

### `aic status`

Show sync state of all components across all languages.

**Syntax:**
```bash
aic status [--component <COMPONENT>] [--language <LANGUAGE>] [--expand]
```

**Options:**
- `--component <COMPONENT>` — Filter to one component only
- `--language <LANGUAGE>` — Filter to one language only
- `--expand` — Show per-file detail for multi-file components

**Examples:**
```bash
aic status
aic status --component UserService
aic status --language python
aic status --expand
```

**States:**
- `✓ IN SYNC` — intent and code are aligned
- `⚠ STALE` — intent changed, recompile needed (run `aic compile`)
- `✗ DRIFT` — code manually changed without sync (run `aic sync`)
- `✗ VIOLATION` — code violates declared guidelines (run `aic audit`)

---

## AI Interaction

### `aic ask`

Ask AI a question or request a fix using your repository context.

**Syntax:**
```bash
aic ask --query "<QUESTION>" [--fix] [--language <LANGUAGE>]
```

**Options:**
- `--query "<QUESTION>"` **(required)** — Your question or fix request
- `--fix` — Apply fix to code files (fix mode)
- `--language <LANGUAGE>` — Scope to one language (required for fix with multiple languages)

**Examples:**

**Question mode** (ask for information):
```bash
aic ask --query "how does UserService handle auth"
aic ask --query "what's the difference between sync and compile"
aic ask --query "show me the UserService flow diagram"
```

**Fix mode** (apply changes):
```bash
aic ask --query "fix null check in UserService" --fix
aic ask --query "fix UserService" --fix --language python
aic ask --query "add logging to AuthService" --fix --language java
```

**Behavior:**
- Reads relevant intent files and code
- Maintains context awareness across the entire project
- Question mode: Returns AI response based on your repository
- Fix mode: Generates code changes and applies them to the component

---

## Project Navigation

### `aic navigate`

Assemble scoped intent context for your AI chat. Zero LLM — fully deterministic file traversal.

**Syntax:**
```bash
aic navigate --query "<DESCRIPTION>" [--copy] [--file]
```

**Options:**
- `--query "<DESCRIPTION>"` **(required)** — Natural language description of your task
- `--copy` — Copy context to clipboard automatically
- `--file` — Write context to `.aic/context/` folder

**Examples:**
```bash
aic navigate --query "fix account lockout in python"
aic navigate --query "UserService android" --copy
aic navigate --query "payment flow" --file
aic navigate --query "auth flow across all languages"
```

**Output:**
- Assembled context block with relevant intent files
- Ready to paste into any AI tool (ChatGPT, Claude, Gemini, etc.)
- Includes: project.intent → language.intent → module.intent → component.intent (hierarchical)

**Note:** v1 requires manual paste into AI chat. MCP server integration coming in v2.

---

## Multi-Target Operations

### `aic transpile`

Compile every component to a new target language. Used for full project migrations or adding a new language target.

**Syntax:**
```bash
aic transpile --target <LANGUAGE[@VERSION]> [--force] [--component <COMPONENT>]
```

**Options:**
- `--target <LANGUAGE[@VERSION]>` **(required)** — Target language (e.g., `flutter`, `java@21`, `swift`)
- `--force` — Overwrite existing components in target language
- `--component <COMPONENT>` — Transpile single component only (instead of all)

**Examples:**
```bash
aic transpile --target flutter
aic transpile --target java@21
aic transpile --target swift --force
aic transpile --target flutter --component UserService
```

**Behavior:**
- Compiles every component in the business layer to the new target language
- Existing components in the target language are **skipped unless `--force`** is used
- Each component uses its `module.intent` and the new language's `language.intent`
- Creates full folder structure with intent + code for all components

**Use cases:**
1. **Add new language** — Transpile to Swift/Flutter/Kotlin
2. **Full migration** — Transpile entire project to Java@21
3. **Selective transpile** — `--component` to test single component first

---

## Common Workflows

### Workflow 1: Create and Compile a New Component

```bash
# Step 1: Create component scaffold
aic create UserService --language python

# Step 2: Edit business/UserService/module.intent (add business logic)
# Step 3: Edit python/UserService/UserService.intent (add implementation details)
# Step 4: Compile to code
aic compile UserService --target python

# Step 5: Check status
aic status --component UserService
```

### Workflow 2: Update Intent and Sync Code

```bash
# Step 1: Manually edit python/UserService/user_service.py (manual fix)
# Step 2: Sync changes back to intent
aic sync UserService --language python
# Review the proposal, then:
aic sync UserService --language python --approve

# Step 3: Verify status
aic status --component UserService
```

### Workflow 3: Handle Intent Changes at Multiple Levels

```bash
# Step 1: Update parent intent (module.intent or language.intent)
# Step 2: Recompile with --force to pick up parent changes
aic compile UserService --target python --force

# Step 3: Sync component.intent to stay in sync
aic sync UserService --language python --approve

# Step 4: Verify all levels are consistent
aic status --component UserService
```

### Workflow 4: Add New Language to Existing Project

```bash
# Step 1: Transpile all components to new language
aic transpile --target java@21

# Step 2: Verify status for new language
aic status --language java

# Step 3: Audit specific files if needed
aic audit java/UserService/UserService.java
```

### Workflow 5: Get Context for AI Chat

```bash
# Step 1: Determine what you need to ask AI
# Step 2: Use navigate to get scoped context
aic navigate --query "fix authentication flow" --copy

# Step 3: Paste into AI chat and ask your question
# (Context already loaded with relevant intent files)
```

---

## Configuration

AIC reads configuration from `.aic/aic.config.json`:

```json
{
  "project_name": "MyProject",
  "ai_provider": "claude",
  "claude_api_key": "your-api-key-here",
  "gemini_api_key": "optional",
  "ollama_url": "http://localhost:11434",
  "auto_verify": false
}
```

**Supported AI Providers:**
- `claude` — Anthropic Claude (recommended)
- `gemini` — Google Gemini
- `ollama` — Local LLM via Ollama

---

## Tips & Best Practices

1. **Always run `aic init` first** — Sets up the project structure
2. **Use `aic navigate` before complex AI chats** — Ensures AI has correct context
3. **Run `aic status` frequently** — Catch drift or staleness early
4. **Use `--force` carefully** — It regenerates code, use only when intent changes at higher levels
5. **Audit before committing** — `aic audit <file>` to verify compliance
6. **Use `aic sync --approve` cautiously** — Review proposals carefully before approving
7. **Validate intent files regularly** — `aic validate <file>` catches schema issues early

---

## Exit Codes

- `0` — Command succeeded
- `1` — Expected error (invalid input, file not found, validation failed)
- `2` — System error (file write failed, permission denied, git not initialized)

---

## Getting Help

```bash
aic --help
aic <COMMAND> --help
```

For detailed documentation and design:
- 📄 [IOA & AIC Complete Design Document](./IOA_and_AIC_Complete_Design_Document.docx)
- 📝 [Intent-Oriented Architecture Concept](https://medium.com/@manaskhare07/your-ai-coding-tool-has-no-idea-what-your-codebase-is-supposed-to-do-5f4a3cd0e5a8)
- 🔗 [GitHub Repository](https://github.com/manas-16/AIC)

