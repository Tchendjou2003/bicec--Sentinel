# BMAD Code Review Report — Stories 1.2, 1.3 & 1.4

**Reviewer:** BMAD Code Review Workflow (Amelia agent)
**Date:** 2026-05-08
**Scope:** Stories 1.2 (Authentification), 1.3 (Auditeurs Externes), 1.4 (Organigramme)
**Method:** Adversarial review — AC validation, task audit, code quality, test quality

---

## Executive Summary

| Story | Status | 🔴 Critical | 🟡 Medium | 🟢 Low | Verdict |
|-------|--------|------------|-----------|--------|---------|
| 1.2 — Authentification | in-progress | 1 | 4 | 2 | ⚠️ NOT done |
| 1.3 — Auditeurs Externes | done | 0 | 3 | 2 | ✅ Done (minor fixes) |
| 1.4 — Organigramme | done | 2 | 5 | 3 | ⚠️ Done with issues |
| **Total** | | **3** | **12** | **7** | |

---

## Story 1.2: Authentification des Utilisateurs Internes

**Story file says:** `in-progress` (header), `done` (conclusion) — **INCONSISTENCY**
**Sprint status says:** `in-progress`
**Previous review:** Approved (2026-05-02) with 1 fix applied, 4 follow-up action items created — **ALL UNRESOLVED**

### AC Validation

| AC | Status | Evidence |
|----|--------|----------|
| AC1: Login → redirect to home/`?next=` | ✅ | `test_smoke.py:29-37` — verified |
| AC2: Idle timeout 30 min | ⚠️ PARTIAL | `middleware.py:14-53` implemented, **NO TESTS** |
| AC3: Anonymous → 302 to login | ✅ | `test_smoke.py:19-22` — verified |
| AC4: Logout POST CSRF-protected | ✅ | `test_smoke.py:48-52` — verified |
| AC5: Brute force protection (5 attempts) | ⚠️ PARTIAL | `base.py:165-168` configured, **NO TESTS** |

### Task Audit

| Task | Marked | Status |
|------|--------|--------|
| Task 1: Vues et URLs d'authentification | [x] | ✅ Verified |
| Task 2: Interface utilisateur (templates) | [x] | ⚠️ Verified — widget_tweaks not used |
| Task 3: Sécurisation sessions | [x] | ⚠️ Verified — no idle timeout tests |

### Unresolved Action Items (from 2026-05-02 review)

| ID | Severity | Description | File | Status |
|----|----------|-------------|------|--------|
| AI-Review-H1 | 🔴 HIGH | Tests IdleTimeoutMiddleware (AC2) | `tests/test_middleware.py` | ❌ NOT DONE |
| AI-Review-H2 | 🔴 HIGH | Tests django-axes brute force (AC5) | `apps/users/tests/` | ❌ NOT DONE |
| AI-Review-H3 | 🔴 HIGH | Inputs → django-widget-tweaks | `templates/auth/login.html` | ❌ NOT DONE |
| AI-Review-M1 | 🟡 MEDIUM | Template axes/lockout.html | `templates/axes/lockout.html` | ❌ NOT DONE |

### Findings

#### 🔴 CRITICAL

**C-1.2.1: Story marked "done" with 4 unresolved HIGH action items**

- **File:** `1-2-authentification-utilisateurs-internes.md:74`
- **Issue:** The conclusion says `Status: done` and `58/58 tests OK`, but 4 `[AI-Review]` follow-up items are unchecked. The sprint-status correctly says `in-progress` but the story file contradicts itself.
- **Impact:** Story cannot be considered complete without test coverage for AC2 and AC5.
- **Fix:** Revert story status to `in-progress`, complete the 4 action items, then re-review.

#### 🟡 MEDIUM

**M-1.2.1: Login template uses manual HTML instead of django-widget-tweaks**

- **File:** `code/templates/auth/login.html:92-116`
- **Issue:** Story requires `django-widget-tweaks` but template uses manual `<input>` with hardcoded Tailwind classes. Inconsistent with other project forms.
- **Fix:** Refactor to `{% load widget_tweaks %}` and `{{ form.username|add_class:"..." }}`.

**M-1.2.2: No axes/lockout.html template**

- **File:** Missing `code/templates/axes/lockout.html`
- **Issue:** django-axes renders default 403 on account lockout. No branded Sentinel template exists.
- **Fix:** Create `templates/axes/lockout.html` extending `base.html`.

**M-1.2.3: No IdleTimeoutMiddleware tests**

- **File:** `code/apps/users/tests/test_middleware.py`
- **Issue:** Only `RoleRequiredMiddleware` tested. Missing: session timeout, public path exclusion, static/media exclusion, `_last_activity` tracking.
- **Fix:** Add `IdleTimeoutMiddlewareTest` class.

**M-1.2.4: No django-axes lockout tests**

- **File:** No test file for axes
- **Issue:** No tests verify lockout after 5 attempts, cooloff, reset on success.
- **Fix:** Add `AxesLockoutTest` class.

#### 🟢 LOW

**L-1.2.1: External Google Fonts CDN**

- **File:** `code/templates/auth/login.html:10-11`
- **Issue:** Loads fonts from Google CDN. Banking security policies may require self-hosted fonts.

**L-1.2.2: Dead "Mot de passe oublié ?" link**

- **File:** `code/templates/auth/login.html:105`
- **Issue:** `<a href="#">` — points nowhere.

---

## Story 1.3: Plateforme des Auditeurs Externes

**Status:** done | **Previous review:** This session

### AC Validation

| AC | Status | Evidence |
|----|--------|----------|
| AC1: is_external=True, no writes | ✅ | `middleware.py:139-152` |
| AC2: Dedicated login / EXT redirection | ✅ | `views.py:54-55` |
| AC3: 403 on internal URLs | ✅ | `middleware.py:154-160` |
| AC4: ExternalMission model | ✅ | `models.py:244-336` |

### Findings

#### 🟡 MEDIUM

**M-1.3.1:** Duplicate `PermissionDenied` imports in middleware (`middleware.py:148, 156`)

**M-1.3.2:** Misleading error message for EXT on `/admin/login/`

**M-1.3.3:** `ip_address` not captured in AuditLog for external operations

#### 🟢 LOW

**L-1.3.1:** English comment in French test file (`test_external_readonly.py:74`)

**L-1.3.2:** `ExternalMission.__str__` doesn't handle None auditor

---

## Story 1.4: Gestion de l'Organigramme et Création des Comptes

**Status:** done | **Previous review:** This session

### AC Validation

| AC | Status | Evidence |
|----|--------|----------|
| AC1: Admin redirected to dashboard | ✅ | `views.py:57-58` |
| AC2: Multi-level hierarchy | ⚠️ PARTIAL | Departments created inactive (C-1.4.1) |
| AC3: REGION→AGENCE hierarchy | ✅ | `test_admin_it.py:139-150` |
| AC4: Shell account creation | ✅ | `forms.py:30` |

### Findings

#### 🔴 CRITICAL

**C-1.4.1:** New departments created as INACTIVE — `department_form.html` missing hidden `is_active` input in create mode

**C-1.4.2:** Story File List references wrong filenames (`organigramme_tree.html` / `organigramme_node.html` vs actual `organigramme_content.html` / `department_card.html`)

#### 🟡 MEDIUM

**M-1.4.1:** Missing `department-search` URL — template references undefined route

**M-1.4.2:** `DepartmentForm.clean_parent()` only validates cycles in edit mode

**M-1.4.3:** Forms imported inside view methods instead of module level

**M-1.4.4:** `AdminRequiredMixin` in views.py instead of mixins.py

**M-1.4.5:** Conflicting z-index `z-50` + `z-10` on sidebars

#### 🟢 LOW

**L-1.4.1:** Dashboard KPI cards don't use `kpi_card.html` component

**L-1.4.2:** No negative test cases for form validation

**L-1.4.3:** `get_department_tree()` returns `list` not `QuerySet`

---

## Recommended Actions (Priority Order)

### P0 — Must Fix

1. **C-1.2.1:** Revert story 1.2 to `in-progress`, complete 4 action items
2. **C-1.4.1:** Fix `department_form.html` — add hidden `is_active` input
3. **C-1.4.2:** Fix story File List with correct filenames

### P1 — Should Fix

4. **M-1.2.1:** Refactor login template to use `widget_tweaks`
5. **M-1.2.2:** Create `axes/lockout.html` template
6. **M-1.2.3:** Add IdleTimeoutMiddleware tests
7. **M-1.2.4:** Add django-axes tests
8. **M-1.4.1:** Add `department-search` URL or remove from template
9. **M-1.3.1:** Consolidate PermissionDenied imports

### P2 — Nice to Have

10. **M-1.3.3:** Add IP capture in AuditLog
11. **M-1.4.3-4:** Refactor imports and mixin location
12. **L-1.2.1:** Self-host fonts
13. **L-1.4.1:** Use kpi_card component

---

## Sprint Status Recommendation

| Story | Current | Recommended |
|-------|---------|-------------|
| 1.2 | in-progress | **in-progress** (correct — 4 action items pending) |
| 1.3 | done | **done** (minor issues only) |
| 1.4 | done | **in-progress** (C-1.4.1 is a functional bug) |

---

*Generated by BMAD Code Review Workflow — Adversarial Review Mode*
