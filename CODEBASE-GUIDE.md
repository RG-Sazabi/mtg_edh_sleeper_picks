# Codebase Guide

This file is loaded **on demand** — not automatically on every session.
Reference it in CLAUDE.md under "On-Demand Context" so the agent fetches it
only when working in the relevant area.

Fill in the sections below as your project grows. The goal is to capture
decisions, patterns, and context that would otherwise have to be re-explained
every time a new session starts.

---

## Why This File Exists

CLAUDE.md is kept intentionally concise because it loads in full on every
interaction. This file is where the deeper, longer-form context lives:
architecture decisions, data flow diagrams, complex patterns with annotated
examples, and notes on legacy areas.

---

## Architecture Overview

### High-Level Data Flow

```
{describe how data moves through your system}
{e.g., Client → Server Action → Service → Repository → Database}
```

### Directory Map (Expanded)

```
{expand on the abbreviated version in CLAUDE.md with more detail}
```

### Key Design Decisions

**{Decision 1 — e.g., Why vertical slices instead of layers}**
{Explanation}

**{Decision 2 — e.g., Why this ORM instead of another}**
{Explanation}

**{Decision 3 — e.g., Why server actions instead of API routes}**
{Explanation}

---

## Patterns In Depth

### {Pattern 1 — e.g., Service Layer}

{Annotated example with explanation of what each piece does and why.}

```typescript
// Example from src/features/users/service.ts
export async function getUser(id: string, requesterId: string): Promise<User> {
  logger.info({ userId: id }, "user.get_started");         // log start
  const user = await repository.findById(id);              // delegate to repo
  if (!user) throw new UserNotFoundError(id);              // typed error
  if (user.id !== requesterId) throw new AccessDeniedError(); // access control
  logger.info({ userId: id }, "user.get_completed");       // log completion
  return user;
}
```

### {Pattern 2 — e.g., Error Classes}

```typescript
// Base error
export class AppError extends Error {
  constructor(
    message: string,
    public readonly code: string,
    public readonly statusCode: number
  ) {
    super(message);
    this.name = this.constructor.name;
  }
}

// Feature error
export class UserNotFoundError extends AppError {
  constructor(id: string) {
    super(`User not found: ${id}`, "USER_NOT_FOUND", 404);
  }
}
```

---

## Database Schema

{List your main entities, their key fields, and their relationships.}

### {Entity 1}

| Column | Type | Notes |
|---|---|---|
| `id` | uuid | Primary key |
| `{field}` | {type} | {notes} |

### Relationships

- {Entity 1} has many {Entity 2}
- {Entity 2} belongs to {Entity 1}

---

## API Patterns

### Endpoint Structure

```
{method} /api/{resource}           → list / create
{method} /api/{resource}/{id}      → get / update / delete
```

### Response Format

```json
{
  "data": {},
  "error": null
}
```

### Error Response Format

```json
{
  "data": null,
  "error": {
    "code": "USER_NOT_FOUND",
    "message": "User not found: 123"
  }
}
```

---

## Authentication & Authorization

{Describe your auth approach. Who can do what? Where is auth checked?}

---

## Testing Approach

### Unit Tests

{What gets unit tested? What doesn't? Where do unit test files live?}

### Integration Tests

{What scenarios are covered? What tooling?}

### E2E Tests

{Key user flows that are covered. How to run them.}

---

## Known Technical Debt

| Area | Issue | Impact | Priority |
|---|---|---|---|
| `{path}` | {description} | {low/med/high} | {low/med/high} |

> When working near legacy code, write new code to the current conventions.
> Do NOT refactor legacy code unless a task explicitly says to.

---

## External Integrations

### {Integration 1 — e.g., Stripe}

- **Purpose**: {what it's used for}
- **SDK**: `{package-name}`
- **Key files**: `{paths}`
- **Gotchas**: {anything the agent needs to know}

---

## Deployment

{How does this project get deployed? Environment variables required?}

```bash
# Required environment variables
{VAR_NAME}=   # {description}
{VAR_NAME}=   # {description}
```
