# AIC — AI Compiler

> Code is temporary. Intent is permanent.

## What is this?

AIC is the reference implementation of **Intent-Oriented Architecture (IOA)** — a methodology where human intent at each organisational level is explicitly declared, version-controlled, and treated as the source of truth for all downstream artefacts including code, documentation, and API specifications.

Instead of asking AI to reverse-engineer understanding from code, you give it a map.
Repository ←→ .intent files ←→ AI

Your codebase and your AI become a single coherent entity — instead of two disconnected systems patched together with impulsive prompts and partial context repeated every session.

---

## The Problem

- AI coding tools ignore your standards every session
- The prompt that produced your code is gone when the chat closes
- Schema and context get pasted manually every single time
- AI hallucinates when context grows across components
- PR reviews are manual, repetitive, and expensive
- Nothing you put into AI is reusable across your team

**Root cause:** AI has no permanent, structured, scoped awareness of your project.

---

## The Solution — .intent Files

Four levels of structured intent, each owned by the right role:

| File | Owner | Scope |
|------|-------|-------|
| `project.intent` | Architect | Org-wide standards, security, architecture |
| `module.intent` | BA / PM | Business logic, user journeys, rules |
| `language.intent` | Lead Engineer | Coding patterns, framework conventions |
| `component.intent` | Developer | Platform-specific implementation |

---

## Project Structure
```
/my-project
├── /intent
│   ├── project.intent
│   └── /UserService
│       └── module.intent
├── /android
│   ├── android.intent
│   └── /UserService
│       ├── UserService.intent
│       └── UserService.java
└── /swift
    ├── swift.intent
    └── /UserService
        ├── UserService.intent
        └── UserService.swift
```

---

## Status

🚧 **Working prototype in development.**

The full design document covering IOA methodology, AIC implementation, file structure, inheritance model, commands, use cases, and proposed proof-of-concept experiments is available here:

📄 [IOA & AIC Complete Design Document](./IOA_and_AIC_Complete_Design_Document.docx)

📝 [Introducing the concept — Medium Article](https://medium.com/@manaskhare07/your-ai-coding-tool-has-no-idea-what-your-codebase-is-supposed-to-do-5f4a3cd0e5a8)

---

## Proposed Proof of Concept Experiments

We invite the developer community to validate or challenge these claims:

1. **Migration** — Migrate a module the traditional way vs the intent-driven way. Compare output quality, idiomatic correctness, and time taken.

2. **Cross-language generation** — Generate a second language from existing code vs from a shared intent file. Compare behavioural consistency and maintainability.

3. **AI integration** — Develop with traditional chat-based AI context vs scoped intent files. Measure hallucination rate and context setup time.

If you run any of these experiments, share your results. Positive results strengthen the methodology. Negative results improve it.

---

## Roadmap

- [ ] `.intent` file format specification
- [ ] `aic init` — project initialisation
- [ ] `aic compile` — single component, single target
- [ ] `aic status` — sync state tracking
- [ ] `aic sync` — bidirectional sync
- [ ] Multi-target compilation
- [ ] VS Code extension

---

## License

MIT
