---
description: Security-focused review of current changes
---

# Security Review

## Objective

Perform a security-focused review of all current changes. This is a complement
to `/review`, not a replacement — run both before merging sensitive changes.

## Process

### Step 1: Get the Diff

```bash
git diff main...HEAD
```

### Step 2: Check Each Category

**Input Validation**
- Are all user-supplied inputs validated before use?
- Is validation happening at the right layer (API boundary, not just UI)?
- Are there any places where unvalidated input reaches a database query or shell command?

**Authentication & Authorization**
- Are protected routes actually protected?
- Are authorization checks in place for every sensitive operation?
- Is there any place where a user could access another user's data?

**Injection Vulnerabilities**
- SQL injection: are all queries parameterized? No string concatenation in queries.
- XSS: is user content escaped before rendering in HTML?
- Path traversal: are file paths validated and sandboxed?
- Command injection: are shell commands avoiding user input?

**Secrets & Sensitive Data**
- Are there any hardcoded secrets, API keys, passwords, or tokens?
- Are sensitive values coming from environment variables?
- Is sensitive data being logged?
- Are secrets excluded from error messages returned to clients?

**Session & Cookie Security**
- Are session tokens properly scoped and short-lived?
- Are cookies using `HttpOnly`, `Secure`, and `SameSite` flags?
- Is there CSRF protection on state-changing operations?

**Error Handling**
- Do error responses leak internal implementation details?
- Are stack traces hidden from end users?
- Are errors logged internally but sanitized externally?

**Dependencies**
- Were any new dependencies added? If so, note them for manual review.

### Step 3: Output

```
## Security Review

### ❌ Critical — Fix Before Merge
- {issue with file:line and explanation}

### ⚠️ High — Fix Soon
- {issue}

### 💡 Low / Informational
- {observation}

### New Dependencies Added
- {package name} — review for known vulnerabilities (`npm audit`)

### Verdict
PASS / FAIL / NEEDS DISCUSSION
```
