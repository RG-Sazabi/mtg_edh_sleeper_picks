---
description: Install dependencies and start the development server
---

# Install: Project Setup

## Objective

Get the project running locally from a clean clone. Read CLAUDE.md first to
use the exact commands for this project.

## Process

1. Read `CLAUDE.md` — identify the package manager (npm, pnpm, bun, yarn, pip, etc.)
   and the exact dev command

2. Install dependencies:
   ```bash
   # npm
   npm install
   # pnpm
   pnpm install
   # bun
   bun install
   ```

3. Set up environment:
   - Check for `.env.example` and copy it: `cp .env.example .env`
   - Note any required environment variables and prompt the user to fill them in

4. Set up the database (if applicable):
   - Run migrations or schema push per CLAUDE.md instructions
   - Seed with test data if a seed script exists

5. Verify the setup:
   - Run the type check command
   - Run the test suite
   - Start the dev server

6. Report:
   ```
   ## Setup Complete

   - Dependencies: installed
   - Environment: .env created (review required values)
   - Database: {migrated / seeded / N/A}
   - Type check: PASS / FAIL
   - Tests: PASS / FAIL
   - Dev server: running at {url}

   ### Required Environment Variables
   {List any variables in .env.example with empty values}
   ```
