---
description: Generate or update CLAUDE.md by analyzing the existing codebase
---

# Create Rules: Generate CLAUDE.md

## Objective

Analyze the current codebase and produce a tailored `CLAUDE.md` that accurately
reflects the project's stack, structure, commands, and conventions.

## Process

### Step 1: Gather Evidence

1. Read `package.json` (or equivalent: `pyproject.toml`, `Cargo.toml`, `go.mod`)
2. Read any existing `CLAUDE.md` or `README.md`
3. Run `find . -type f -not -path "*/node_modules/*" -not -path "*/.git/*" | head -100`
   to understand directory structure
4. Read 3–5 representative source files to identify naming conventions, patterns,
   import styles, and error handling approaches
5. Read existing test files to understand testing conventions
6. Check `tsconfig.json`, `.eslintrc`, `biome.json`, or linter config for enforced rules

### Step 2: Identify

- **Tech stack** with actual versions from package files
- **Dev commands**: start, build, test, lint — get exact command strings
- **Architecture pattern**: how is the code organized?
- **Naming conventions**: what patterns are actually used?
- **Export style**: named vs. default exports?
- **Error handling pattern**: how are errors created and thrown?
- **Test location and pattern**: where do test files live?

### Step 3: Generate CLAUDE.md

Write a complete `CLAUDE.md` using the template structure from `.claude/CLAUDE-template.md`
(if present) or the standard sections:

1. Project Overview
2. Tech Stack (table)
3. Commands (exact command strings)
4. Self-Correction Workflow
5. Architecture (directory tree with descriptions)
6. Code Patterns (naming, exports, errors, layer boundaries)
7. Testing
8. Validation Sequence
9. Key Files
10. On-Demand Context
11. Rules That Will Fail Checks

### Step 4: Flag Assumptions

At the end, list any conventions you inferred rather than observed directly,
so the user can correct them:

```
## Assumptions Made (Please Review)
- Assumed named exports based on 3/5 files checked — verify this is intentional
- Assumed test files use Jest based on package.json devDependencies
- Could not determine error handling pattern — please add to Code Patterns section
```

### Step 5: Write the File

Write the generated content to `CLAUDE.md` in the project root.
If a `CLAUDE.md` already exists, show a diff of changes and ask before overwriting.
