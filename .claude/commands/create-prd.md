---
description: Create a Product Requirements Document from a brain dump or conversation
argument-hint: [output-filename]
---

# Create PRD: Generate Product Requirements Document

**Output file name**: $ARGUMENTS (default: `PRD.md`)

## Overview

Generate a comprehensive PRD based on the current conversation context and requirements.
Save it to `.agents/PRDs/` when complete.

## Process

### Phase 1: EXTRACT — Ask Clarifying Questions First

Before writing anything, ask the user these questions if the answers aren't already clear
from the conversation. Wait for responses before proceeding.

- What problem does this solve, and for whom?
- Who is the primary user? What is their technical comfort level?
- What MUST be in the MVP? What can wait for later?
- What does success look like in 3 months?
- Are there any hard technical constraints (existing stack, budget, timeline)?
- Are there any features you explicitly do NOT want?

**Wait for the user's answers before writing the PRD.**

### Phase 2: SYNTHESIZE

- Organize requirements into sections below
- Fill in reasonable assumptions where details are missing — flag them clearly
- Ensure MVP scope is realistic and well-defined
- Maintain consistency across sections

### Phase 3: GENERATE

Write the PRD using the structure below. Use clear, professional language.
Use markdown: headings, lists, checkboxes, code blocks where helpful.

---

## PRD Structure

### 1. Executive Summary
- Concise product overview (2–3 paragraphs)
- Core value proposition
- MVP goal statement

### 2. Mission
- Product mission statement
- 3–5 core principles

### 3. Target Users
- Primary user personas
- Technical comfort level
- Key needs and pain points

### 4. MVP Scope

**In Scope** (use checkboxes):
- [ ] Core feature 1
- [ ] Core feature 2

**Out of Scope** (deferred):
- [ ] Future feature 1

### 5. User Stories
5–8 stories in format: "As a [user], I want to [action], so that [benefit]."
Include a concrete example for each.

### 6. Core Architecture & Patterns
- High-level architecture approach
- Directory structure (if applicable)
- Key design patterns

### 7. Technology Stack
- Backend / Frontend with versions
- Key dependencies
- Third-party integrations

### 8. Security & Configuration
- Auth approach
- Environment variables needed
- Security scope (in / out)

### 9. Success Criteria
- MVP success definition
- Functional requirements (checkboxes)
- Quality indicators

### 10. Implementation Phases
Break into 3–4 phases, each with:
- Goal
- Deliverables (checkboxes)
- Validation criteria

### 11. Risks & Mitigations
3–5 risks with specific mitigations.

### 12. Future Considerations
Post-MVP enhancements and integration opportunities.

---

## Phase 4: VALIDATE

Before saving, verify:
- All required sections present
- User stories have clear benefits
- MVP scope is realistic
- Success criteria are measurable
- Assumptions are flagged

## Phase 5: OUTPUT

Save the PRD to `.agents/PRDs/{filename}.md` (default: `PRD.md`).

Then summarize:
```
## PRD Created

**File**: `.agents/PRDs/{filename}.md`
**Product**: {name}
**Problem**: {one line}
**Solution**: {one line}

### Summary
- {N} user stories
- {N} MVP features in scope
- {N} implementation phases

### Assumptions Made
{List, or "None"}

### Next Steps
1. Review and refine the PRD
2. Run `/create-issues .agents/PRDs/{filename}.md` to create GitHub Issues
3. Run `/plan` on the first issue when ready to build
```
