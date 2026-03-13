# DetectiveBoard — Issues & Findings

This document lists potential issues in the project, grouped by **Security**, **Missing features**, and **Other**. Each item is ranked by **severity**: Critical, High, Medium, Low, Info.

---

## Severity scale

| Level    | Meaning |
|----------|--------|
| **Critical** | Immediate risk: data breach, full auth bypass, or service compromise. Fix before production. |
| **High**     | Serious vulnerability or missing capability that significantly impacts security or core UX. |
| **Medium**   | Important but manageable risk or feature gap; should be addressed soon. |
| **Low**      | Minor issue or nice-to-have; fix when convenient. |
| **Info**     | Improvement or consistency suggestion, not a defect. |

---

## 1. Security issues

### 1.1 JWT secret key fallback in production — **Critical**

**Location:** `app.py` (line 24)

**Issue:**  
`SECRET_KEY = os.getenv("SECRET_KEY", "dev-secret-key-change-in-production")`  
If `SECRET_KEY` is not set in production, all JWTs are signed with a known default. An attacker can forge valid tokens for any `user_id` and gain full account access without knowing passwords.

**Recommendation:**  
Require `SECRET_KEY` in production; fail startup if unset:

```python
SECRET_KEY = os.getenv("SECRET_KEY")
if not SECRET_KEY:
    raise RuntimeError("SECRET_KEY environment variable must be set")
```

---

### 1.2 No rate limiting on auth endpoints — **High**

**Location:** `app.py` — `/api/auth/login`, `/api/auth/register`

**Issue:**  
No limit on request rate. Enables:
- Brute-force attacks on passwords for known usernames
- Mass account creation (spam/bots)

**Recommendation:**  
Add rate limiting (e.g. Flask-Limiter) on login and register, e.g. 5–10 requests per minute per IP.

---

### 1.3 No account recovery (forgotten password) — **High**

**Location:** Auth design (no email/identifier for recovery)

**Issue:**  
With username-only auth there is no out-of-band channel to verify identity. A forgotten password means the account is permanently unrecoverable. Users cannot be notified in case of a breach.

**Recommendation:**  
Introduce an optional (or recovery-only) email field, used only for password reset via time-limited, single-use tokens. Keep username as the public identifier.

---

### 1.4 Security headers missing — **High**

**Location:** `app.py` — no `after_request` or middleware setting headers

**Issue:**  
Missing standard HTTP security headers increases exposure to:
- Clickjacking (no `X-Frame-Options`)
- MIME sniffing (no `X-Content-Type-Options`)
- XSS / injection (no `Content-Security-Policy`)
- Referrer leakage (no `Referrer-Policy`)

**Recommendation:**  
Add an `after_request` hook to set at least:

- `X-Frame-Options: DENY`
- `X-Content-Type-Options: nosniff`
- `Referrer-Policy: no-referrer` (or strict-origin-when-cross-origin)
- `Content-Security-Policy` (tune for your scripts, styles, images, fonts)

---

### 1.5 File upload: extension-only validation — **Medium**

**Location:** `app.py` — card create/update (e.g. lines 349–354, 407–413)

**Issue:**  
Only the file extension is checked (`.jpg`, `.jpeg`, `.png`). A malicious file (e.g. executable renamed to `.jpg`) can be uploaded. If the server ever executes or serves uploads in an unsafe way, this could lead to RCE or XSS.

**Recommendation:**  
Validate content (magic bytes / MIME), e.g. with `python-magic` or similar, in addition to extension. Reject non-image types.

---

### 1.6 No server-side upload size limit — **Medium**

**Location:** `app.py` — no `MAX_CONTENT_LENGTH`; UI states "max 1MB"

**Issue:**  
The server does not enforce a maximum request body size. Clients can send very large files, leading to disk exhaustion, memory pressure, or DoS.

**Recommendation:**  
Set `app.config["MAX_CONTENT_LENGTH"] = 1 * 1024 * 1024` (1 MB). Flask will return 413 for larger requests.

---

### 1.7 Card color bypass in JSON update — **Medium**

**Location:** `app.py` — `update_card()` JSON branch (lines 419–426)

**Issue:**  
When updating a card via JSON (`PUT /api/cards/<id>` with `Content-Type: application/json`), the `color` field is copied from the request without validation. The multipart branch validates against `ALLOWED_CARD_COLORS`, but the JSON branch does not. An attacker can set arbitrary `color` values (e.g. long strings, or values that affect rendering).

**Recommendation:**  
In the JSON branch, validate `color` the same way as in the form branch:

```python
if "color" in data:
    color = data["color"] if data.get("color") in ALLOWED_CARD_COLORS else None
    fields.append("color = %s")
    values.append(color)
```

(And do not add `color` via the generic loop.)

---

### 1.8 Share token has no expiry — **Low**

**Location:** `app.py` — `enable_share()`; DB column `share_token`

**Issue:**  
Share tokens are stored in plain text and never expire. Old links remain valid indefinitely. If the DB is compromised, all active share links are exposed.

**Recommendation:**  
Add an optional `share_expires_at` (or similar) and reject access when expired. Optionally store a hash of the token instead of the token itself.

---

### 1.9 No password complexity policy — **Low**

**Location:** `app.py` — `register()` (e.g. `len(password) < 8`)

**Issue:**  
Only minimum length (8) is enforced. Weak passwords like `12345678` are allowed.

**Recommendation:**  
Require a mix of character types (e.g. upper, lower, number, symbol) and/or check against known breached passwords (e.g. HaveIBeenPwned API with k-anonymity).

---

### 1.10 Username enumeration on register — **Info**

**Location:** `app.py` — register returns "Username already taken" on conflict

**Issue:**  
An attacker can probe whether a username exists. For a username-based system this is often acceptable (usernames are public), but it does leak existence.

**Recommendation:**  
If product policy requires hiding existence of usernames, return a generic message (e.g. "Registration failed") instead of "Username already taken".

---

## 2. Missing features / spec gaps

### 2.1 Server-side 1MB upload limit (spec) — **High**

**Location:** Plan/spec vs implementation

**Issue:**  
The plan states the 1MB limit is an "UI hint" and "non è validato server-side". From a security and reliability perspective, the server must enforce the limit.

**Recommendation:**  
Implement server-side limit (see 1.6) and keep UI hint aligned.

---

### 2.2 Double-click on board to create note — **Low**

**Location:** `plan.md` / UX

**Issue:**  
Double-click on empty board opens the **card** modal. The plan describes double-click for cards; notes are created only via toolbar. Not necessarily wrong, but double-click for a note could improve flow.

**Recommendation:**  
Optional: support a modifier (e.g. Alt+double-click) or a second action to create a note at click position.

---

### 2.3 No “pin position” when creating a card — **Low**

**Location:** `templates/index.html` — card creation modal

**Issue:**  
New cards get default pin position (center). Pin position can be set only in the edit panel after creation. Plan allows pin in three positions; creation UX could expose it.

**Recommendation:**  
Add pin position (e.g. radio group) to the new-card modal so users can set it upfront.

---

### 2.4 No “inactive” when creating a card — **Low**

**Location:** Card creation form

**Issue:**  
New cards are always active. "Inactive" can only be set when editing. Minor UX gap if users often create inactive cards.

**Recommendation:**  
Optional checkbox "Inactive" in the create-card modal.

---

### 2.5 Shared board: no explicit “link invalid” state — **Low**

**Location:** `shared.js` — `initBoard()` on non-OK response

**Issue:**  
If `/api/share/<token>` returns 404, the client redirects to `/`. User may not understand that the link is invalid or expired.

**Recommendation:**  
Redirect to a dedicated "Link invalid or expired" page (or show a message on `/`) instead of the generic home.

---

## 3. Other issues

### 3.1 Italian error message in API — **Low**

**Location:** `app.py` — `update_note()` returns `"Niente da aggiornare"`

**Issue:**  
Rest of API and UI use English. Inconsistent language and harder for non-Italian clients to handle.

**Recommendation:**  
Use English, e.g. `"Nothing to update"`, consistent with other endpoints.

---

### 3.2 CLAUDE.md outdated — **Low**

**Location:** `CLAUDE.md`

**Issue:**  
Docs state "local-only", "no authentication", "requires no authentication". The app now has JWT auth, multi-user boards, and share links.

**Recommendation:**  
Update CLAUDE.md to describe auth, multi-tenancy, and sharing.

---

### 3.3 Duplicate auth/modal markup — **Info**

**Location:** `home.html` vs `index.html` / `shared.html`

**Issue:**  
Login and register modals are duplicated across templates. Changes (e.g. labels, validation) must be done in multiple places.

**Recommendation:**  
Extract modals into a shared partial (e.g. `_auth_modals.html`) and include it where needed.

---

### 3.4 No explicit CORS policy — **Info**

**Location:** `app.py`

**Issue:**  
No CORS headers are set. If the frontend is later served from another origin (e.g. SPA on different host), API calls may be blocked unless CORS is configured.

**Recommendation:**  
If you plan to split frontend/backend origins, add Flask-CORS or manual CORS headers with a strict origin list.

---

### 3.5 DB connection per request, no pooling — **Info**

**Location:** `app.py` — `get_db()`

**Issue:**  
Each request opens a new PostgreSQL connection. Under high concurrency this can exhaust DB connections or cause latency.

**Recommendation:**  
For production, consider connection pooling (e.g. PgBouncer, or SQLAlchemy pool if you introduce an ORM).

---

### 3.6 Possible migration ordering / history — **Info**

**Location:** `migrations/versions/`

**Issue:**  
Migration chain is 001 → 002 → 003 → 004 → 005 → 006 → 007. If 004 (users) was applied to a DB that already had boards, those boards would have `user_id = NULL`. No data migration is present to assign or purge them.

**Recommendation:**  
If you have pre-auth boards in production, add a data migration to assign or remove them. New deployments from scratch are fine.

---

## 4. Summary table

| #   | Category   | Issue                                      | Severity  |
|-----|------------|--------------------------------------------|-----------|
| 1.1 | Security   | JWT secret key fallback                     | Critical  |
| 1.2 | Security   | No rate limiting on auth                   | High      |
| 1.3 | Security   | No account recovery                        | High      |
| 1.4 | Security   | Security headers missing                   | High      |
| 1.5 | Security   | Upload: extension-only validation          | Medium    |
| 1.6 | Security   | No server-side upload size limit           | Medium    |
| 1.7 | Security   | Card color bypass in JSON update            | Medium    |
| 1.8 | Security   | Share token has no expiry                  | Low       |
| 1.9 | Security   | No password complexity policy              | Low       |
| 1.10| Security   | Username enumeration on register           | Info      |
| 2.1 | Missing    | Server-side 1MB upload limit               | High      |
| 2.2 | Missing    | Double-click to create note                | Low       |
| 2.3 | Missing    | Pin position in create-card modal          | Low       |
| 2.4 | Missing    | Inactive checkbox in create-card modal     | Low       |
| 2.5 | Missing    | Clear “link invalid” for shared board       | Low       |
| 3.1 | Other      | Italian message in API                     | Low       |
| 3.2 | Other      | CLAUDE.md outdated                         | Low       |
| 3.3 | Other      | Duplicate auth modal markup                | Info      |
| 3.4 | Other      | No CORS policy                             | Info      |
| 3.5 | Other      | No DB connection pooling                   | Info      |
| 3.6 | Other      | Pre-auth boards migration                  | Info      |

---

## 5. Recommended order of fixes

1. **Immediate (before production):** 1.1 (SECRET_KEY), 1.6 + 2.1 (upload limit).
2. **Short term:** 1.2 (rate limiting), 1.4 (security headers), 1.5 (upload validation), 1.7 (color validation).
3. **Next:** 1.3 (account recovery design), 1.8 (share expiry), 1.9 (password policy).
4. **As needed:** 2.2–2.5 (UX), 3.1–3.6 (consistency, CORS, pooling, migrations).

This list reflects the codebase and docs as of the analysis date; re-validate after changes.
