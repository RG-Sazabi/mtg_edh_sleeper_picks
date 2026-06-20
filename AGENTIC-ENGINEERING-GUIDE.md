# Agentic Engineering with Claude Code: A Complete Getting-Started Guide

> Based on Cole Medin's "Principled Agentic Engineering" methodology
> GitHub repo: [coleam00/ai-transformation-workshop](https://github.com/coleam00/ai-transformation-workshop)

---

## Table of Contents

1. [The Big Picture: What Is Agentic Engineering?](#1-the-big-picture-what-is-agentic-engineering)
2. [Key Concepts You Need to Know](#2-key-concepts-you-need-to-know)
3. [Prerequisites and Installation](#3-prerequisites-and-installation)
4. [The Three-Phase Methodology Overview](#4-the-three-phase-methodology-overview)
5. [Setting Up Your AI Layer](#5-setting-up-your-ai-layer)
6. [Understanding and Configuring CLAUDE.md](#6-understanding-and-configuring-claudemd)
7. [Understanding and Using Commands (Slash Commands)](#7-understanding-and-using-commands-slash-commands)
8. [Browser Automation with Playwright MCP](#8-browser-automation-with-playwright-mcp)
9. [The Persistent Memory System](#9-the-persistent-memory-system)
10. [Understanding Sub-Agents](#10-understanding-sub-agents)
11. [Connecting to GitHub with MCP](#11-connecting-to-github-with-mcp)
12. [Establishing Coding Conventions](#12-establishing-coding-conventions)
13. [Part I: Starting a Greenfield Project](#part-i-starting-a-greenfield-project)
14. [Part II: Continuing a Brownfield Project](#part-ii-continuing-a-brownfield-project)
15. [The System Evolution Loop](#15-the-system-evolution-loop)
16. [Working with Git Worktrees for Parallel Development](#16-working-with-git-worktrees-for-parallel-development)
17. [Command Reference Cheat Sheet](#17-command-reference-cheat-sheet)

---

## 1. The Big Picture: What Is Agentic Engineering?

When people start using Claude Code, they often treat it like an advanced autocomplete — paste some code, get some code back. This works, but it doesn't scale. You end up constantly re-explaining context, the agent makes assumptions that break things, and every session feels like starting over.

Agentic engineering is a different philosophy. The goal is to build a *system* that makes AI coding reliable, repeatable, and shippable — not just fast in the moment.

The core insight is this: **every codebase now has two layers.** The first is your actual application code. The second is your *AI layer* — all the instructions, context documents, commands, and conventions that tell your coding agent how to work *in your specific project*. Most people build the first layer and completely skip the second. That's the gap this guide addresses.

When your AI layer is properly set up, the agent knows your tech stack, your naming conventions, your error handling patterns, how to run your tests, and how your features are organized. It doesn't guess. It follows the same standards every time.

---

## 2. Key Concepts You Need to Know

Before diving in, here are the terms you'll encounter constantly. Understanding these upfront will make everything else click.

**Claude Code** is Anthropic's command-line tool that lets you have a full coding agent running in your terminal. You install it once, navigate to your project folder, and type `claude` to start a session. It can read and write files, run shell commands, browse your codebase, and remember instructions you give it through special configuration files.

**CLAUDE.md** is the most important file in this workflow. It's a plain Markdown file you place in the root of your project. Claude Code reads it automatically at the start of every session. Think of it as a permanent briefing document: your tech stack, how to run the project, your coding standards, your file organization — everything the agent needs to work correctly without you having to re-explain it.

**Commands (slash commands)** are reusable workflows you define as Markdown files inside a `.claude/commands/` folder. You invoke them by typing `/command-name` in a Claude Code session. For example, `/create-prd` might run a multi-step workflow that interviews you about your project idea and produces a structured Product Requirements Document. Commands are how you standardize *how your team builds*, not just *what you build*.

**Skills** are more complex, multi-step capabilities — like a browser automation skill that can interact with a web UI, or a presentation generator that builds PowerPoint files. Skills go in `.claude/skills/` and are invoked similarly to commands.

**MCP (Model Context Protocol)** is how Claude Code connects to external services. An MCP server is a small program that exposes tools (like "create a GitHub issue" or "read a pull request") that the agent can call during a session. This is how you replace Jira in this workflow — you install the GitHub MCP server and the agent can read and write GitHub Issues directly.

**Sub-agents** are separate Claude instances that the main agent can spin up to do focused research work. They're useful because they have their own context windows — you can send a sub-agent off to explore a large codebase and get back a summary, without consuming the main agent's context. Critically: sub-agents are used for *research only*, never for writing code directly.

**The PIV Loop** stands for Plan, Implement, Validate. It's the per-feature cycle you repeat for every unit of work: plan in one session, implement in a fresh session, validate by running tests and checks. Separating these phases and keeping context clean is what makes the agent reliable.

**The AI Layer** is the collective name for everything in your `.claude/` directory plus your `CLAUDE.md`. It's your project's second codebase — the one that teaches the agent how to work.

---

## 3. Prerequisites and Installation

### Install Claude Code

Claude Code is a command-line tool. Open your terminal and run:

```bash
npm install -g @anthropic-ai/claude-code
```

You'll need Node.js 18 or newer installed first. Verify the install worked:

```bash
claude --version
```

### Authenticate

Run `claude` for the first time and it will prompt you to log in to your Anthropic account. You'll need an active Claude subscription (Pro or higher for serious use) or API access.

### Install the GitHub CLI (optional but recommended)

The GitHub CLI makes it much easier to work with issues, PRs, and branches from the terminal, which is where you'll be spending a lot of time.

```bash
# macOS
brew install gh

# Windows (with winget)
winget install GitHub.cli

# Authenticate
gh auth login
```

### Install Node.js and Git

Both are assumed to be present. If you don't have them:

- Node.js: https://nodejs.org (use the LTS version)
- Git: https://git-scm.com

---

## 4. The Three-Phase Methodology Overview

Everything in this guide builds toward three phases that Cole Medin describes as the foundation of reliable AI-assisted development. Understanding the shape of the whole system before setting up the pieces will help you see why each step matters.

**Phase 1: Strategic Planning** turns a raw idea into structured work without you manually creating tickets or writing specs. You describe what you want to build, the agent asks clarifying questions, and the output is a Product Requirements Document (PRD) and a set of GitHub Issues ready to be worked.

**Phase 2: The PIV Loop** is the cycle you run for each GitHub Issue (each ticket). You *prime* the agent by loading the relevant context, *plan* a concrete implementation strategy, *implement* the code in a fresh context window, and *validate* using a layered testing approach. This loop repeats until the issue is done.

**Phase 3: System Evolution** is what separates teams that compound over time from teams that stay flat. Whenever the agent makes a mistake or misunderstands something, instead of just fixing the bug, you also update your CLAUDE.md or commands to prevent the same mistake from happening again. The AI layer improves with every session.

---

## 5. Setting Up Your AI Layer

The AI layer is a folder structure you add to every project. You can copy it from Cole Medin's repo and customize it, or build it from scratch. Here's what it looks like:

```
your-project/
├── CLAUDE.md                    ← Global rules, always loaded
├── CODEBASE-GUIDE.md            ← Deep-dive reference, loaded on demand
├── .mcp.json                    ← MCP server configuration (GitHub, etc.)
├── .claude/
│   ├── CLAUDE-template.md       ← Starter template for new projects
│   └── commands/                ← Your slash commands live here
│       ├── prime.md
│       ├── create-prd.md
│       ├── create-issues.md     ← Replaces create-stories.md (GitHub version)
│       ├── plan.md
│       ├── implement.md
│       ├── validate.md
│       ├── review.md
│       ├── security-review.md
│       └── create-rules.md
└── .agents/
    ├── PRDs/                    ← Generated PRDs land here
    └── plans/                   ← Generated implementation plans land here
```

### Getting the Starter Files

The fastest way to get started is to copy the `.claude/` directory from Cole Medin's repo:

```bash
# In your project root
git clone https://github.com/coleam00/ai-transformation-workshop /tmp/medin-workshop
cp -r /tmp/medin-workshop/.claude .
mkdir -p .agents/PRDs .agents/plans
```

The `.mcp.json` from that repo is configured for Jira/Confluence (Atlassian). You'll replace it with your GitHub configuration in Section 10.

---

## 6. Understanding and Configuring CLAUDE.md

`CLAUDE.md` is the single most important file in your project from the agent's perspective. Every Claude Code session begins by reading it. Everything in this file applies to every interaction.

### What Goes In It

Think of CLAUDE.md as the document you'd write for a skilled new developer joining your team — except that developer has no memory between days. Include everything they'd need on day one:

**Project Overview** — one paragraph describing what the application does and who it's for.

**Tech Stack** — the specific technologies, frameworks, and versions you use. Be explicit. "React" isn't specific enough; "React 19 with the App Router, TypeScript strict mode, Tailwind CSS 4, shadcn/ui components" is.

**Development Commands** — exactly how to run, build, test, and lint the project. The agent will run these commands constantly.

```markdown
## Commands

```bash
npm run dev          # Start dev server at localhost:3000
npm run build        # Production build (includes type checking)
npm run lint         # Check for lint errors
npm run lint:fix     # Auto-fix lint issues
npm test             # Run test suite
npx tsc --noEmit     # Type check without building
```
```

**Architecture** — how your project is organized. A directory tree with brief explanations for each top-level folder. If you use a specific pattern like vertical slice architecture, describe it here.

**Code Patterns** — the actual conventions your codebase follows. Name things explicitly: "Use named exports, not default exports" or "Services contain business logic; repositories contain only database queries." The more specific, the better.

**Self-Correction Workflow** — instruct the agent to run your lint and type checks after every code change and fix any errors before proceeding. This creates a feedback loop that catches most mistakes before you ever see them.

```markdown
## Self-Correction Workflow

After writing or modifying code, always run:

```bash
npm run lint && npx tsc --noEmit
```

Read the errors, fix them, and repeat until the output is clean.
```

**Rules That Will Fail Checks** — spell out the things your linter enforces so the agent knows in advance. "Never use `==`, always use `===`." "Missing `type` keyword on type-only imports will fail." This prevents a whole class of back-and-forth.

### Generating CLAUDE.md with `/create-rules`

If you copy the commands from the workshop repo, you'll have a `/create-rules` command. Run it in a Claude Code session and the agent will analyze your codebase and generate a first draft of CLAUDE.md tailored to your project. You'll still want to review and refine it, but this is dramatically faster than writing it from scratch.

```
/create-rules
```

### What NOT to Put in CLAUDE.md

Keep CLAUDE.md tight. Avoid dumping every piece of project documentation in here — the file is loaded in full for every single interaction, so bloating it with content that's only relevant 5% of the time wastes context.

Reference deep documentation in a separate `CODEBASE-GUIDE.md` file and note it in CLAUDE.md as "on-demand context." The agent can fetch it when it's actually needed.

```markdown
## On-Demand Context

| Topic | File |
|-------|------|
| Database patterns | `CODEBASE-GUIDE.md#database` |
| API design patterns | `docs/api-patterns.md` |
| Component conventions | `docs/component-guide.md` |
```

---

## 7. Understanding and Using Commands (Slash Commands)

Commands are Markdown files that live in `.claude/commands/`. Each one defines a multi-step workflow the agent executes when you type `/command-name` in a session. They're the "standardize *how* you build" piece of the system.

### Anatomy of a Command File

A command file is just Markdown with a brief frontmatter header:

```markdown
---
description: Create a PRD from conversation context
argument-hint: [optional-output-filename]
---

# Create PRD: Generate Product Requirements Document

## Overview
Generate a comprehensive Product Requirements Document...

## Process
### Phase 1: EXTRACT
- Review the entire conversation history
- Identify explicit requirements and implicit needs
...
```

The `description` field tells Claude what the command does. The `argument-hint` shows what arguments it accepts. Everything after the frontmatter is the actual instruction set.

### How to Invoke a Command

In a Claude Code session, type:

```
/create-prd my-feature-name
```

The agent reads the command file and executes whatever is in it. `$ARGUMENTS` in the file gets substituted with whatever you typed after the command name.

### The Core Commands to Know

**`/prime [github-issue-number]`** — Load context before planning or implementing. The agent reads CLAUDE.md, scans the file tree, checks recent git history, and (if you provide an issue number) fetches the corresponding GitHub Issue. Run this at the start of every session and every time you switch tasks. Think of it as "briefing the agent."

**`/create-prd [filename]`** — Turn a brain dump into a structured PRD. You describe your idea, the agent asks clarifying questions, then produces a full Product Requirements Document saved to `.agents/PRDs/`. Review and approve the PRD before moving on.

**`/create-issues`** — Convert a PRD into GitHub Issues. This is the GitHub-adapted version of Cole's `/create-stories` command. The agent reads the PRD and creates one Issue per feature/story via the GitHub MCP, with acceptance criteria, labels, and sizing. (See Section 10 for the command file you'll need to write.)

**`/plan [issue-number or prd-path]`** — Produce a detailed implementation plan before any code is written. The agent explores the codebase to find similar patterns, documents what files need to change, and creates a plan file saved to `.agents/plans/`. Review the plan before implementing.

**`/implement [plan-path]`** — Execute a plan in a fresh context window. Always run this as a *new* Claude Code session (close the current one and start fresh) to avoid context contamination from earlier phases. The plan file contains everything the agent needs.

**`/validate`** — Run the full check suite: type checking, linting, and tests. The agent reads the output, fixes anything that fails, and reports back when everything is clean.

**`/review`** — Perform a code review of the current changes. The agent checks for correctness, pattern adherence, test coverage, and edge cases. Good to run before opening a PR.

**`/security-review`** — Focused review for security issues: injection vulnerabilities, exposed secrets, auth gaps, input validation.

**`/create-rules`** — Generate or update CLAUDE.md by analyzing the existing codebase.

### Focused Primers

For large projects, Cole recommends creating focused `/prime-*` variants that load only the context relevant to a specific layer:

- `/prime-server` — backend/API layer context
- `/prime-client` — frontend/component context
- `/prime-endpoint` — a specific API endpoint's context
- `/prime-components` — UI component conventions

These are useful when your codebase is large and loading everything at once would bloat the context.

### Creating Your Own Commands

Any repeated workflow is a candidate for a command. If you find yourself typing the same multi-step instruction more than twice, write a command file for it. Examples:

- A deployment checklist
- A database migration workflow
- A documentation update command
- An API integration scaffolding command

Create the file, place it in `.claude/commands/`, commit it, and everyone on your team gets the command automatically.

---

## 8. Browser Automation (Skills / Playwright)

> **Note**: This template uses the **Playwright MCP server** for browser automation instead of a local "agent-browser" skill. See [Section 8: Browser Automation with Playwright MCP](#8-browser-automation-with-playwright-mcp) above for setup and usage.
>
> The legacy approach (`.claude/skills/agent-browser/`) required a separate Node.js process and was harder to configure. Playwright MCP is plug-and-play: add it to `.mcp.json` and use `/verify` — no separate skill directory needed.

### What Skills Are

Skills are more complex, self-contained capabilities packaged as command files in `.claude/commands/`. In this template, browser automation is handled through the Playwright MCP (see above), but you can create custom skill-style commands for any repeated complex workflow — presentation generation, database seeding scripts, deployment checklists, etc.

Create a new command file in `.claude/commands/` and it becomes available as a slash command immediately.

---

## (Old §8 reference — moved)

Skills are similar to commands but designed for more complex, self-contained capabilities — often ones that require browser interaction or produce rich output like files.

### Skills vs. Commands

Commands are instructions the agent follows inline during your current session. Skills are more like packaged mini-applications: they may spin up their own environment, interact with a browser, or produce standalone output.

### The Agent-Browser Skill

The most important skill in the workshop repo is `agent-browser`. It gives Claude Code the ability to interact with a live web browser — navigating pages, clicking buttons, filling forms, and taking screenshots. This is used in the validation phase for end-to-end testing: the agent can actually open your app in a browser and walk through user flows.

To use it, you need a browser automation tool like Playwright installed, and the skill file wired up in `.claude/skills/agent-browser/`.

### Practical Use in Validation

Once the agent-browser skill is set up, your `/validate` command can run a sequence like:

1. Run unit tests
2. Run type checking and linting
3. Spin up the dev server
4. Use the browser skill to navigate to your app, perform key user actions, and verify the results
5. Shut down the dev server
6. Report all results

This pushes a significant amount of what would be manual QA into automated validation.

### Installing Skills from the Workshop Repo

```bash
# Copy the skills directory into your project
cp -r /tmp/medin-workshop/.claude/skills .claude/
```

You'll likely need to install Playwright separately for browser automation:

```bash
npm install --save-dev @playwright/test
npx playwright install
```

---

## 8. Browser Automation with Playwright MCP

The Playwright MCP server gives Claude Code the ability to control a real browser — navigating pages, clicking buttons, filling forms, and taking screenshots. This replaces the need for a separate "agent-browser skill" and integrates directly with Claude Code's tool-calling system.

### What It Enables

- **End-to-end verification**: After implementing a feature, run `/verify` to have the agent open your app in a browser and walk through the golden path
- **Automated acceptance testing**: Use Playwright to check that UI components render correctly, forms submit, and error states display properly
- **Visual regression checks**: Take screenshots at key steps and compare states before and after changes

### Setup

Playwright MCP is already included in `.mcp.json.example`. After copying it to `.mcp.json`:

```bash
# Install Playwright browsers (one-time per machine)
npx playwright install --with-deps chromium
```

No other installation is required — the MCP server launches automatically when Claude Code starts.

### Using `/verify`

The `/verify` command uses Playwright to check a feature in the running app:

```
/verify                          # verifies the current issue's acceptance criteria
/verify http://localhost:3000    # targets a specific URL
/verify 42                       # loads Issue #42 acceptance criteria, then tests
```

The agent will:
1. Navigate to the relevant page
2. Walk through the primary user flow
3. Assert the expected outcome is visible
4. Report pass/fail with screenshots

### Integration with `/validate`

`/validate` runs Layers 1–2 (type check, lint, unit tests) automatically. Layer 3 (E2E) runs if Playwright is configured. The validation pyramid is:

```
Layer 5: Manual testing          ← You
Layer 4: Code review             ← /review
Layer 3: E2E / browser           ← /verify (Playwright MCP)
Layer 2: Unit tests              ← /validate (auto)
Layer 1: Type check + lint       ← /validate (auto)
```

### Practical Tips

- Keep the dev server running in a separate terminal while using `/verify`
- Target specific pages rather than crawling the whole app — Playwright sessions are slow and expensive in tokens
- Use `/verify` for the golden path; don't try to cover every edge case through the browser

---

## 9. The Persistent Memory System

One of the biggest differences between a session-by-session Claude Code workflow and a truly compounding one is whether context survives across sessions. The memory system solves this.

### How It Works

The `memory/` directory in your project root contains a small set of Markdown files that persist facts across sessions:

```
memory/
├── MEMORY.md           ← Index — loaded automatically on every session
├── user_profile.md     ← Who is working on this project
├── feedback.md         ← Corrections and confirmed approaches
├── project_context.md  ← Decisions, constraints, active goals
└── references.md       ← GitHub repos, dashboards, external links
```

`MEMORY.md` is the index — a concise list of pointers to the other files. Claude Code reads it at the start of each session to decide which memory files are relevant to the current task, then fetches those files.

### Memory Types

**User profile** — Role, expertise level, working preferences. Helps Claude Code calibrate explanation depth and communication style. Example: "Senior backend engineer, new to React — frame frontend concepts in backend analogues."

**Feedback** — The most important type. Records corrections ("don't do X") and confirmed approaches ("yes, keep doing Y"). Every correction in a session is an opportunity to save a feedback memory so the same guidance doesn't have to be repeated next session.

```markdown
**Rule**: Don't mock the database in tests
**Why**: Prior incident where mocked tests passed but a prod migration failed
**How to apply**: All database tests must use a real test database
```

**Project context** — Decisions, goals, constraints with absolute dates. Use this for things like architecture choices, deadlines, compliance requirements, or active refactors.

```markdown
**Fact**: Auth middleware rewrite driven by legal/compliance requirements
**Why**: Legal flagged session token storage as non-compliant
**How to apply**: Favor compliance over ergonomics in all auth-related decisions
```

**References** — URLs and system pointers so the agent always knows where to look. Your GitHub repo URL belongs here so every `/prime` session starts with the right remote context.

### What NOT to Put in Memory

Memory is for context that would otherwise have to be re-explained across sessions. Don't save:
- Code patterns or conventions — those go in `CLAUDE.md`
- Architecture documentation — that goes in `CODEBASE-GUIDE.md`
- Temporary task state — use tasks within the session
- Git history or who changed what — `git log` is authoritative

### Memory and the System Evolution Loop

Memory feedback entries and System Evolution (Section 15) are complementary. System Evolution updates `CLAUDE.md` and commands to fix repeatable mistakes. Memory feedback records corrections that are too narrow or personal to warrant a `CLAUDE.md` change — things specific to this developer's preferences or this project's quirks.

When in doubt: if the correction should apply to *everyone* working on this project, put it in `CLAUDE.md`. If it's specific to *how you work*, put it in `memory/feedback.md`.

---

## 10. Understanding Sub-Agents


Sub-agents are separate Claude instances that the main agent can spin up during a session. They have their own independent context windows, which is the key benefit.

### Why Sub-Agents Matter

When you're planning a feature, you often need to explore a large codebase to understand what already exists, find analogous patterns, and map out dependencies. If you do all of that in your main session, you consume a lot of context on research — context that you then *also* need for the implementation plan you're writing.

Sub-agents solve this: the main agent delegates research tasks to sub-agents, each of which can explore deeply and independently. Each sub-agent returns a summary back to the main agent. The main agent now has the answers it needs without having burned its own context on the search.

### The Critical Rule: Research Only

Sub-agents in this methodology are **never** used to write code. They're used to read, explore, and summarize. Code writing happens in the main agent's session (during `/implement`), where you can review and control what's happening.

### How Sub-Agents Appear in the Workflow

The `/plan` command uses sub-agents automatically. When it runs, it dispatches several parallel agents to explore different parts of the codebase simultaneously — one might study error handling patterns, another looks at how tests are written, a third finds analogous features. Their findings come back and feed into the implementation plan.

You don't need to configure sub-agents separately. They're invoked through the normal Claude Code agent framework and are governed by your CLAUDE.md rules.

---

## 11. Connecting to GitHub with MCP

MCP (Model Context Protocol) is how Claude Code connects to external services. The workshop repo uses Atlassian MCP for Jira and Confluence. Since you want to use GitHub, you'll replace that with the GitHub MCP server.

### What MCP Enables

With the GitHub MCP connected, the agent can during a session:

- Fetch the full details of a GitHub Issue (title, description, labels, comments)
- Create new Issues from a PRD
- Comment on Issues and PRs
- Read PR diffs during code review
- Update Issue status (open/closed)

### Installing the GitHub MCP Server

The official GitHub MCP server is maintained by GitHub:

```bash
npm install -g @modelcontextprotocol/server-github
```

Or you can run it via Docker (recommended for consistency):

```bash
docker pull ghcr.io/github/github-mcp-server
```

### Creating a GitHub Personal Access Token

You need a token with permissions to read and write Issues and PRs. Go to:

GitHub → Settings → Developer Settings → Personal Access Tokens → Tokens (classic)

Create a new token with these scopes:
- `repo` (full repository access, includes Issues and PRs)

Copy the token — you'll only see it once.

### Configuring .mcp.json

Create or replace `.mcp.json` in your project root:

```json
{
  "mcpServers": {
    "github": {
      "command": "npx",
      "args": ["-y", "@modelcontextprotocol/server-github"],
      "env": {
        "GITHUB_PERSONAL_ACCESS_TOKEN": "YOUR_TOKEN_HERE"
      }
    }
  }
}
```

**Important:** Add `.mcp.json` to your `.gitignore` (or use an `.env` file for the token) so you don't accidentally commit your personal access token.

```bash
echo ".mcp.json" >> .gitignore
```

A better pattern is to reference an environment variable and keep the token in a `.env` file that's also gitignored:

```json
{
  "mcpServers": {
    "github": {
      "command": "npx",
      "args": ["-y", "@modelcontextprotocol/server-github"],
      "env": {
        "GITHUB_PERSONAL_ACCESS_TOKEN": "${GITHUB_PAT}"
      }
    }
  }
}
```

### Adapting the `/prime` Command for GitHub

The workshop's `/prime` command fetches Jira issues. You need to update it to fetch GitHub Issues instead. Edit `.claude/commands/prime.md` and replace the Jira section:

```markdown
## Step 0: Load External Context (if provided)

The argument is an optional GitHub Issue number or comma-separated list (e.g., `42` or `42,43,44`).

If issue numbers are provided:
1. Call `mcp__github__get_issue` with the repository owner, repo name, and issue number to fetch the issue title, body, and any linked issues
2. Use the issue body as your understanding of what work is expected
3. Note the issue number — it will be referenced in the implementation plan
```

### Writing the `/create-issues` Command

This replaces the Jira-based `/create-stories` command. Create `.claude/commands/create-issues.md`:

```markdown
---
description: Convert a PRD into GitHub Issues
argument-hint: path/to/PRD.md
---

# Create GitHub Issues from PRD

**Input**: $ARGUMENTS (path to PRD file)

## Process

1. Read the PRD file at the path provided
2. Identify each user story or MVP feature that represents a unit of work
3. For each story, create a GitHub Issue using the `mcp__github__create_issue` tool with:
   - **title**: A clear, action-oriented title (e.g., "Add user authentication with email/password")
   - **body**: The user story, acceptance criteria, and any technical notes
   - **labels**: Apply `enhancement` for new features, `bug` for fixes
4. Output a summary of all Issues created with their numbers and URLs

## Issue Body Format

```
## User Story
As a [user type], I want to [action], so that [benefit].

## Acceptance Criteria
- [ ] Criterion 1
- [ ] Criterion 2
- [ ] Criterion 3

## Technical Notes
[Any relevant implementation context]
```
```

### Setting Up GitHub Issues for Your Project

If you don't already have Issues enabled on your repo:

1. Go to your GitHub repository
2. Click Settings → General
3. Under "Features," check the Issues box

Consider also enabling GitHub Projects (kanban-style boards) for visual tracking of which issues are in progress, in review, and done.

---

## 12. Establishing Coding Conventions

One of the highest-leverage things you can do is explicitly define and document how code should be written. The agent will follow these conventions on every task, which means the conventions you define on day one propagate through every line of AI-generated code.

### Why Conventions Matter More with AI

When humans write code, conventions drift slowly. When an AI writes code, it takes the path of least resistance — which is whatever pattern it's seen most commonly, across all of its training data, not your specific project. Without explicit conventions, you'll get inconsistent code that combines patterns from dozens of different styles.

### What to Define

**Naming Conventions**

Be explicit about everything: files, variables, functions, components, API endpoints, database tables. For example:

- Files: `kebab-case` for utilities (`user-service.ts`), `PascalCase` for components (`UserCard.tsx`)
- Variables and functions: `camelCase`
- Types and interfaces: `PascalCase`
- Constants: `SCREAMING_SNAKE_CASE`
- Database tables: `snake_case` pluralized (`user_accounts`)
- API endpoints: `/api/resource-name` (plural, kebab-case)

**Import Organization**

Define the order: external dependencies, then internal absolute imports, then relative imports. Many teams automate this with a linter rule, but document it regardless.

**Error Handling**

Define one approach and stick to it. Cole Medin's demo app uses typed custom error classes:

```typescript
export class UserNotFoundError extends AppError {
  constructor(id: string) {
    super(`User not found: ${id}`, "USER_NOT_FOUND", 404);
  }
}
```

Whatever pattern you choose, write it in CLAUDE.md with an actual code example.

**File Responsibility Boundaries**

If you use layered architecture (controllers/services/repositories or similar), define what belongs in each layer and what's explicitly forbidden. "Repositories contain only database queries — no business logic" is a rule the agent can actually follow. "Keep your files clean" is not.

**Export Style**

Named exports vs. default exports is a constant source of inconsistency. Pick one and enforce it. Cole's workshop enforces named exports everywhere except Next.js convention files (page.tsx, layout.tsx, etc.).

### The Self-Correction Loop

Beyond conventions, add an explicit self-correction workflow to CLAUDE.md. This instruction tells the agent what to do after writing code:

```markdown
## Self-Correction Workflow

After every code change:
1. Run `npm run lint && npx tsc --noEmit`
2. Read any errors carefully
3. Fix the errors
4. Re-run until both commands complete with no output
5. Only then report the task as complete

Never report a task as done if type checking or linting fails.
```

This one section alone eliminates a large class of back-and-forth where you accept output that has obvious errors.

### Version Controlling Your Conventions

Because CLAUDE.md lives in your repository, your coding conventions are version-controlled. When you discover that the agent keeps misusing a pattern, you update CLAUDE.md, commit it, and from that point forward every session — for you and everyone on your team — has the corrected convention. This is the compounding effect of the AI layer.

---

## Part I: Starting a Greenfield Project

This section walks you through beginning a brand-new project from nothing, in the order you'd actually do it.

### Step 1: Create and Initialize Your Repository

```bash
# Create your project directory
mkdir my-project && cd my-project

# Initialize git
git init

# Create a .gitignore appropriate to your tech stack
# (Use GitHub's gitignore templates or generate one at gitignore.io)

# Make an initial commit
git add .gitignore
git commit -m "Initial commit"
```

Create the repository on GitHub and push:

```bash
gh repo create my-project --public --source=. --push
# or
git remote add origin https://github.com/yourusername/my-project.git
git push -u origin main
```

### Step 2: Set Up the AI Layer Skeleton

```bash
# Create the directory structure
mkdir -p .claude/commands .agents/PRDs .agents/plans

# Copy the starter commands from the workshop repo (if you cloned it earlier)
cp /tmp/medin-workshop/.claude/commands/*.md .claude/commands/

# Create placeholder files
touch CLAUDE.md CODEBASE-GUIDE.md
```

### Step 3: Start Claude Code and Generate Your CLAUDE.md

Navigate to your project root and start a Claude Code session:

```bash
cd my-project
claude
```

If you have some initial files already (package.json, a README, any scaffolding), run:

```
/create-rules
```

The agent will analyze what exists and generate a first draft of CLAUDE.md. If you're starting from a completely empty project, you can give it a brain dump instead:

```
I'm building a web app for tracking personal fitness goals. 
The stack will be Next.js with TypeScript, PostgreSQL, and Prisma.
Users can create goals, log progress entries, and see charts of their progress.
Can you create a CLAUDE.md for this project?
```

Review the output carefully. Add anything it missed, remove anything that doesn't apply. Commit it once it looks right.

### Step 4: Configure MCP for GitHub

Create your `.mcp.json` (see Section 10 for the format), add it to `.gitignore`, and restart Claude Code so it picks up the new MCP server:

```bash
# Restart Claude Code (exit and reopen)
claude
```

Verify the connection is working by asking Claude Code to list your GitHub Issues (your repo might have none yet, but no error = connection is working).

### Step 5: Do a Brain Dump — Create Your PRD

This is where the actual project work begins. Start a new Claude Code session and run:

```
/create-prd
```

The agent will ask you a series of clarifying questions:

- What problem are you solving?
- Who are your users?
- What must be in the MVP, and what can wait?
- What are the success criteria?
- Are there technical constraints?

Answer as thoroughly as you can. If you're unsure about something, say so — the agent will make a reasonable assumption and flag it. When the questions are done, the agent writes a full PRD to `.agents/PRDs/PRD.md`.

**Read the PRD carefully.** This is the most important review you'll do. The PRD drives everything that comes after. Look for:
- Scope that's too broad for an MVP
- Features you're building for imagined users rather than real ones
- Assumptions that are wrong about your domain
- Technical choices that conflict with your constraints

Edit the PRD directly until it accurately reflects what you want to build.

### Step 6: Convert the PRD into GitHub Issues

With the PRD reviewed and approved, run:

```
/create-issues .agents/PRDs/PRD.md
```

The agent reads each feature in the MVP scope, creates a GitHub Issue for it with acceptance criteria, and saves a manifest of all created issues to `.agents/stories/`. You should now have a set of Issues in your GitHub repository that represents your full project backlog.

Go to GitHub and review the Issues. Adjust labels, add milestones, or edit any Issue that needs more detail.

### Step 7: Pick an Issue and Run the PIV Loop

Now you're ready to build. Pick the first Issue you want to implement (usually a foundational piece like data models or authentication).

**Plan Phase — Start a new Claude Code session:**

```bash
claude
```

```
/prime 1
```

(Where `1` is your GitHub Issue number.) The agent loads your codebase context, reads the Issue, and briefs itself. Then:

```
/plan 1
```

The agent explores the codebase for analogous patterns, documents the files that need to change, and produces an implementation plan at `.agents/plans/feature-name.plan.md`.

Review the plan. Check that:
- The approach makes sense for your architecture
- The agent didn't miss any files that need to change
- The order of tasks is logical
- The validation strategy is appropriate

If the plan is wrong, tell the agent and have it revise before proceeding.

**Implement Phase — Start a fresh Claude Code session:**

Close the current session and open a new one. This context reset is intentional — you don't want planning context mixing into implementation.

```bash
claude
```

```
/implement .agents/plans/feature-name.plan.md
```

The agent reads the plan and executes each task in order. Watch what it does. You can intervene at any point by typing in the session.

After implementation, the agent should automatically run the lint/type check/test cycle (per your CLAUDE.md self-correction instructions). If it doesn't, run:

```
/validate
```

**Validate Phase:**

For features with user-visible behavior, this is also when you do manual testing. Open your browser, run through the key user flows, and verify everything works as expected.

### Step 8: Commit and Update the Issue

Once validation passes:

```bash
git add .
git commit -m "feat: implement [feature name] (#1)

Closes #1"
```

The `Closes #1` syntax automatically closes the GitHub Issue when this commit lands on the default branch (or when a PR containing it merges).

If you're using pull requests (recommended):

```bash
git checkout -b feature/issue-1-feature-name
git add .
git commit -m "feat: implement feature name"
git push origin feature/issue-1-feature-name
gh pr create --title "feat: feature name" --body "Closes #1" --base main
```

Before merging, run a code review:

```
/review
```

### Step 9: Repeat

Go back to your Issues list, pick the next one, and run the PIV loop again. Over time, as the codebase grows, `/prime` becomes more valuable — the agent builds a richer picture of what exists and follows your established patterns more precisely.

---

## Part II: Continuing a Brownfield Project

A brownfield project is an existing codebase — one you've been working on for some time (possibly without an AI layer) and now want to bring into this workflow. The approach is slightly different because you're onboarding the AI to a codebase that already exists and has its own history.

### Step 1: Audit What You Have

Before doing anything with Claude Code, spend 20 minutes mapping your existing project's structure in your head. You need to know:

- What does the project do?
- What tech stack is it on?
- What are the main areas of the code?
- Where do the bodies are buried? (legacy patterns, known tech debt, quirks)

You don't need perfect answers, but walking in blind means the generated CLAUDE.md will be generic.

### Step 2: Generate CLAUDE.md from the Existing Codebase

Start a Claude Code session in your project root:

```bash
claude
```

Run:

```
/create-rules
```

The agent will walk your existing code structure, read key files, examine your package.json, look at existing tests if any, and generate a CLAUDE.md. This is one of the most impressive first-session experiences — it often produces a surprisingly accurate document.

The critical step: **read every line of the generated CLAUDE.md and correct it.** The agent will guess at conventions based on patterns it sees. If your existing code is inconsistent (as most brownfield projects are), the generated rules might reflect the bad habits rather than the ideal conventions you want going forward. Fix those now.

Pay special attention to:
- The commands section — are those the actual commands for your project?
- The architecture section — does it reflect how things actually work?
- Code patterns — do these reflect what the code *should* do, or what it happens to do right now?

### Step 3: Add the AI Layer Skeleton

If it doesn't already exist:

```bash
mkdir -p .claude/commands .agents/PRDs .agents/plans
```

Copy in the starter commands, configure `.mcp.json` for GitHub, and set up `.gitignore` entries as described in Part I.

### Step 4: Write or Update CODEBASE-GUIDE.md

For brownfield projects, `CODEBASE-GUIDE.md` is especially valuable. This is where you document the things that don't fit in a concise CLAUDE.md — the history, the gotchas, the "why is this done this way" explanations:

- Why you chose this ORM instead of the more popular one
- The legacy authentication flow that can't be changed yet
- The specific database query pattern you use everywhere (with examples)
- Technical debt areas the agent should treat carefully
- Integration quirks with third-party APIs

The agent won't load this file in every session, but when you're working in a complex area you can tell it to read it first.

### Step 5: Create GitHub Issues for Known Work

If you have a backlog of known bugs, features, and improvements in your head (or scattered in notes), now is a good time to formalize them as GitHub Issues. You can either:

- Create them manually on GitHub
- Describe them to Claude Code and ask it to create them via MCP: `Can you create a GitHub Issue for each of the following items I want to tackle?`

### Step 6: Run the PIV Loop per Issue

The loop is identical to greenfield from here:

1. Pick an Issue
2. `/prime [issue-number]` — loads context and the Issue
3. `/plan [issue-number]` — produces an implementation plan that accounts for *existing* code
4. Review the plan (especially important in brownfield — the agent must work *with* what exists, not replace it wholesale)
5. Start a fresh session and `/implement [plan-path]`
6. `/validate`
7. Commit and open a PR

### The Brownfield-Specific Prime

In a brownfield project, the `/prime` command is doing heavier lifting than in greenfield. The codebase is larger and has more patterns to understand. Consider creating focused `/prime-*` commands for different areas of your codebase (see Section 7) to keep context lean and relevant.

Also: **commit frequently and descriptively.** Cole Medin calls `git log` the agent's memory. When you prime for a new task, the agent reads recent commits to understand what work has been done recently. Commits like `"fix stuff"` are useless to it. Commits like `"refactor: extract UserService from UserController, move validation to Zod schemas"` tell it exactly where the codebase is and why.

### Handling Existing Code Drift

One of the biggest challenges in brownfield is that the existing code may not follow the conventions you're now establishing in CLAUDE.md. Address this directly:

Add a note in CLAUDE.md like:

```markdown
## Legacy Code Note

Code in `src/old-modules/` predates these conventions. 
When working near that code, follow the new conventions for any code you write.
Do NOT refactor the old code unless a task explicitly asks you to.
```

This prevents the agent from refactoring everything it touches (expensive and risky) while still moving toward consistency on net-new code.

---

## 15. The System Evolution Loop

System Evolution is Phase 3 of the methodology and the piece most people skip. It's also what separates teams that improve over time from teams that stay flat.

The principle: **every mistake the agent makes is an opportunity to improve the AI layer.**

When the agent writes code that violates a pattern, generates the wrong file structure, misunderstands what a "service" should contain, or makes any repeatable mistake:

1. Fix the specific bug (obviously)
2. Identify *why* the agent made that mistake — what was ambiguous or missing from the AI layer?
3. Update CLAUDE.md, a command, or CODEBASE-GUIDE.md to prevent the mistake in the future
4. Commit the AI layer update as part of the same PR

### Concrete Examples

The agent keeps adding business logic to repository files:

```markdown
## Repository vs Service Separation (CLAUDE.md addition)

Repositories ONLY contain database queries. Examples of what must NOT be 
in a repository: validation, access control, logging, error transformation.
If you're about to add a condition like "if user is not admin, throw error" 
in a repository, stop — that belongs in the service layer.
```

The agent generates components that don't use your design system:

```markdown
## UI Components (CLAUDE.md addition)

NEVER use raw HTML elements for interactive UI. Always use components 
from `src/components/ui/`. Check that directory before building any button, 
input, dialog, or form. If a component you need doesn't exist there, 
ask before building it from scratch — it may need to be added to the design system.
```

The agent creates new features in the wrong directory:

Update your Architecture section with more explicit rules and an example of the correct directory creation sequence.

### What This Looks Like Over Time

In the first few weeks, you'll be making frequent AI layer updates as you discover gaps. By month two, the agent has internalized your project's patterns so well that it rarely makes the same class of mistake twice. By month six, a new developer can join the project, clone the repo, run `claude`, and be productive within hours — because the CLAUDE.md they're reading is a deep, battle-tested guide to how the project works.

The AI layer compounds. Every update makes every future session better.

---

## 16. Working with Git Worktrees for Parallel Development

This section is based on Cole Medin's second video on parallel agentic development. Once you're comfortable with the single-agent PIV loop, worktrees let you run multiple agents on different Issues simultaneously.

### What Are Git Worktrees?

A git worktree is a second (or third, or fourth) checkout of your repository that shares the same git history. Instead of having one `/project` directory, you can have `/project-main`, `/project-feature-auth`, and `/project-feature-dashboard` all checked out at the same time, all connected to the same git repo.

This means you can have Claude Code running in each one simultaneously, each working on a different Issue, without the sessions interfering with each other.

### Setting Up a Worktree

```bash
# In your main repo directory
git worktree add ../my-project-feature-auth -b feature/issue-42-auth

# Now navigate there and start Claude Code
cd ../my-project-feature-auth
claude
```

The agent in this session has its own isolated copy of the files. Changes here don't affect the main checkout.

### When Worktrees Are Most Valuable

Worktrees pay off when you have multiple Issues ready to implement and want to run agents in parallel. While one agent is implementing a feature, you can be planning the next one in a different worktree.

### Practical Worktree Workflow

1. Set up one worktree per active GitHub Issue
2. In each worktree, follow the normal PIV loop
3. When implementation is done in a worktree, push the branch and open a PR
4. Clean up the worktree after merging: `git worktree remove ../my-project-feature-auth`

### Challenges to Know About

**Database conflicts**: If multiple agents are running migrations simultaneously against a shared development database, you'll get conflicts. Solutions: give each worktree its own database (use separate .env files with unique DB names), or only run migrations from one session at a time.

**Port conflicts**: If each agent tries to start a dev server on port 3000, only one will succeed. Use environment variables to assign different ports to different worktrees.

**Token cost**: Each parallel agent is consuming tokens simultaneously. Parallel development is faster but more expensive. Plan accordingly.

---

## 17. Command Reference Cheat Sheet

This is a quick reference for the commands you'll use in daily work.

### Session Start
| When | Command |
|------|---------|
| Starting any session | `/prime [issue-number]` |
| Starting work on backend | `/prime-server [issue-number]` |
| Starting work on frontend | `/prime-client [issue-number]` |

### Planning Phase
| When | Command |
|------|---------|
| New feature or project idea | `/create-prd [filename]` |
| Converting PRD to Issues | `/create-issues .agents/PRDs/PRD.md` |
| Planning a feature | `/plan [issue-number or prd-path]` |

### Implementation Phase
| When | Command |
|------|---------|
| Executing a plan | `/implement .agents/plans/feature-name.plan.md` |
| Setting up the project initially | `/install` |
| Parallel feature work | `/worktree [issue-number]` |

### Validation Phase
| When | Command |
|------|---------|
| After any code change | `/validate` |
| Browser-based feature check | `/verify [url or issue#]` |
| Before opening a PR | `/review` |
| Before merging sensitive changes | `/security-review` |

### Setup
| When | Command |
|------|---------|
| New project, or updating conventions | `/create-rules` |

### Key Principles to Remember

**Plan, Implement, and Validate are separate sessions.** Starting `/implement` in the same session as `/plan` mixes contexts and degrades quality. Always start a fresh `claude` session for implementation.

**Questions before code.** The most dangerous thing in AI-assisted development isn't the model making mistakes — it's the model making assumptions. The `/create-prd` command asks questions. The `/plan` command explores before designing. Don't skip these steps.

**Context is king.** A well-maintained `CLAUDE.md`, descriptive git commits, and up-to-date memory files are worth more than any single prompt trick.

**Every bug is a system improvement opportunity.** When the agent makes a repeatable mistake, update `CLAUDE.md` or `memory/feedback.md` before moving on.

**Commit frequently.** `git log` is the agent's short-term memory. `memory/` is its long-term memory. Keep both up to date.

**Use GitHub Issues, not Jira.** This template is wired to GitHub via MCP. All issue creation, fetching, and commenting flows through `mcp__github__*` tools — no Atlassian setup needed.

---

*Based on Cole Medin's "Principles of Agentic Engineering" methodology.*
*Adapted for GitHub (replaces Jira/Confluence), Playwright MCP (replaces agent-browser skill), and project-level persistent memory.*

*Source videos:*
- *[Full Guide to Becoming a Principled Agentic Engineer](https://www.youtube.com/watch?v=luBkbzjo-TA)*
- *[Parallel Claude Code + Git Worktrees](https://www.youtube.com/watch?v=rFGlJ4oIlhw)*
- *[Reference repo: coleam00/ai-transformation-workshop](https://github.com/coleam00/ai-transformation-workshop)*
