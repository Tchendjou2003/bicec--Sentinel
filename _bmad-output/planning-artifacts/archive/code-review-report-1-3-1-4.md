# BMAD Code Review Report — Stories 1.3 & 1.4

**Reviewer:** BMAD Code Review Workflow (Amelia agent)
**Date:** 2026-05-08
**Scope:** Stories 1.3 (Plateforme Auditeurs Externes) & 1.4 (Gestion Organigramme)
**Method:** Adversarial review — AC validation, task audit, code quality, test quality

---

## Executive Summary

| Story | 🔴 Critical | 🟡 Medium | 🟢 Low | Verdict |
|-------|------------|-----------|--------|---------|
| 1.3 — Auditeurs Externes | 0 | 3 | 2 | ✅ Done (minor fixes) |
| 1.4 — Organigramme | 2 | 5 | 3 | ⚠️ Done with issues |
| **Total** | **2** | **8** | **5** | |

**Story 1.3** is solid — implementation matches claims, tests are real, ACs are met.
**Story 1.4** has 2 critical bugs and inaccurate documentation that must be addressed.

---

## Story 1.3: Plateforme des Auditeurs Externes

### AC Validation

| AC | Status | Evidence |
|----|--------|----------|
| AC1: `is_external=True`, no writes | ✅ IMPLEMENTED | `middleware.py:139-152` — `ExternalIsolationMiddleware` blocks POST/PUT/PATCH/DELETE except `/auth/logout/` |
| AC2: Dedicated login channel / EXT redirection | ✅ IMPLEMENTED | `views.py:54-55` — `SentinelLoginView.get_success_url()` redirects EXT to `auth:external-dashboard` |
| AC3: 403 on internal URLs | ✅ IMPLEMENTED | `middleware.py:154-160` — blocks all paths except `EXTERNAL_ALLOWED_PATHS` |
| AC4: `ExternalMission` model | ✅ IMPLEMENTED | `models.py:244-336` — full model with FK, validation, indexes |

### Task Audit

| Task | Marked | Status |
|------|--------|--------|
| Task 1: ExternalMission model | [x] | ✅ Verified |
| Task 2: Isolated login channel | [x] | ✅ Verified |
| Task 3: Read-only middleware | [x] | ✅ Verified |

### Findings

#### 🟡 MEDIUM

**M-1.3.1: Duplicate `PermissionDenied` imports in middleware**

- **File:** `code/apps/users/middleware.py:148, 156`
- **Issue:** `from django.core.exceptions import PermissionDenied` is imported twice inside the `__call__` method body. It should be a single top-level import.
- **Fix:** Move `from django.core.exceptions import PermissionDenied` to the top of the file (after existing imports) and remove the two inline imports.

**M-1.3.2: Misleading error message for EXT on `/admin/login/`**

- **File:** `code/apps/users/middleware.py:157-159`
- **Issue:** When an EXT user tries to access `/admin/login/`, the error says "section réservée aux utilisateurs internes" which is technically correct but could confuse an auditor who just wants to log in.
- **Fix:** Consider adding `/admin/login/` to `EXTERNAL_ALLOWED_PATHS` or providing a more specific error message.

**M-1.3.3: `ip_address` not captured in AuditLog for external operations**

- **File:** `code/apps/users/services.py` (all functions)
- **Issue:** The `AuditLog` model has an `ip_address` field but services never populate it. For external auditor actions, IP logging is especially important for regulatory compliance (NFR-SEC-05).
- **Fix:** Pass `request.META.get("REMOTE_ADDR")` from views to services and include it in `AuditLog.objects.create(ip_address=...)`. Requires threading the request through to the service layer.

#### 🟢 LOW

**L-1.3.1: English comment in French test file**

- **File:** `code/apps/users/tests/test_external_readonly.py:74`
- **Issue:** `# Should NOT be 403 from the middleware` — inconsistent language with rest of file.

**L-1.3.2: `ExternalMission.__str__` doesn't handle None auditor**

- **File:** `code/apps/users/models.py:325`
- **Issue:** If `auditor` is None (impossible due to FK constraint but defensive coding), `__str__` would fail.
- **Fix:** `return f"{self.organization} — {self.auditor.username if self.auditor else 'N/A'}"`

---

## Story 1.4: Gestion de l'Organigramme et Création des Comptes

### AC Validation

| AC | Status | Evidence |
|----|--------|----------|
| AC1: Admin redirected to dedicated dashboard | ✅ IMPLEMENTED | `views.py:57-58` — redirects ADMIN to `auth:admin-dashboard` |
| AC2: Multi-level hierarchy DG→DIRECTION→... | ⚠️ PARTIAL | Model supports it, but new departments are created inactive (see C-1.4.1) |
| AC3: REGION→AGENCE hierarchy | ✅ IMPLEMENTED | `test_admin_it.py:139-150` — test proves persistence |
| AC4: Shell account creation (no role fields) | ✅ IMPLEMENTED | `forms.py:30` — fields exclude role/is_external/is_audit_admin |

### Task Audit

| Task | Marked | Status |
|------|--------|--------|
| Task 0: Data model alignment | [x] | ✅ Verified — migration 0004 exists |
| Task 1: Admin dashboard + navigation | [x] | ✅ Verified |
| Task 2: Organigramme UI | [x] | ⚠️ Verified with issues (C-1.4.1, M-1.4.4) |
| Task 3: User creation UI | [x] | ✅ Verified |
| Task 4: Shell account redirection | [x] | ✅ Verified |

### Findings

#### 🔴 CRITICAL

**C-1.4.1: New departments created as INACTIVE — form bug**

- **File:** `code/templates/admin_it/partials/department_form.html:101-109`
- **Issue:** The `is_active` checkbox is only rendered when `is_edit` is `True`. In create mode, the checkbox is absent from the HTML. Django's `BooleanField` treats missing POST data as `False`. **Every new department is created with `is_active=False`** and doesn't appear in the organigramme list (which filters `is_active=True`).
- **Impact:** AC2 is partially broken — departments are saved but invisible.
- **Fix:**
  ```html
  {# department_form.html — replace lines 101-109 #}
  {% if is_edit %}
  <div class="flex items-center gap-3 p-3 rounded-xl bg-gray-50 border border-gray-100">
    {{ form.is_active }}
    <label for="{{ form.is_active.id_for_label }}" class="text-sm text-gray-700 font-medium cursor-pointer select-none">
      Structure active
    </label>
  </div>
  {% else %}
  <input type="hidden" name="is_active" value="on">
  {% endif %}
  ```

**C-1.4.2: Story File List references wrong filenames**

- **File:** `_bmad-output/implementation-artifacts/1-4-gestion-organigramme-institutionnel.md:101-103`
- **Issue:** The File List says:
  - `templates/admin_it/partials/organigramme_tree.html` — "MODIFIÉ: récursivité"
  - `templates/admin_it/partials/organigramme_node.html` — "NOUVEAU"

  But the actual implementation uses:
  - `templates/admin_it/partials/organigramme_content.html`
  - `templates/admin_it/partials/department_card.html`
- **Impact:** Documentation integrity — future developers can't find the files.
- **Fix:** Update the story File List with correct filenames.

#### 🟡 MEDIUM

**M-1.4.1: Missing `department-search` URL — template references undefined route**

- **File:** `code/templates/admin_it/organigramme_list.html:30`
- **Issue:** The search input has `hx-get="{% url 'auth:department-search' %}"` but no such URL pattern exists in `code/apps/users/urls.py`. This would cause a `NoReverseMatch` error when the search input is rendered.
- **Fix:** Either add the URL pattern and view, or remove the search functionality from the template until it's implemented.

**M-1.4.2: `DepartmentForm.clean_parent()` only validates cycles in edit mode**

- **File:** `code/apps/users/forms.py:117-150`
- **Issue:** The circular reference check uses `if self.instance and self.instance.pk` — on creation (no PK yet), the cycle check is skipped entirely. While Django prevents self-reference at the DB level, a manipulated form could set a parent that creates a 2-level cycle.
- **Fix:** Add a creation-mode check that validates the parent is not the same as the new department (though this is partially mitigated by the queryset excluding self).

**M-1.4.3: Forms imported inside view methods**

- **File:** `code/apps/users/views.py:296, 304, 328, 338`
- **Issue:** `from .forms import DepartmentForm` is imported inside `get()` and `post()` methods of `DepartmentCreateView` and `DepartmentEditView`. This is unnecessary — should be at module level.
- **Fix:** Move `from .forms import DepartmentForm, ITUserCreationForm` to the top of the file with other imports.

**M-1.4.4: `AdminRequiredMixin` defined in views.py instead of mixins.py**

- **File:** `code/apps/users/views.py:234-248`
- **Issue:** `AdminRequiredMixin` is in `views.py` while `AuditAdminRequiredMixin` is in `mixins.py`. Both are security mixins — they should be co-located.
- **Fix:** Move `AdminRequiredMixin` to `code/apps/users/mixins.py` and import it in `views.py`.

**M-1.4.5: Conflicting z-index on sidebar**

- **File:** `code/templates/partials/sidebar_admin.html:3` (and other sidebars)
- **Issue:** `class="... z-50 lg:static w-72 ... z-10 ..."` — both `z-50` and `z-10` on the same element. `z-50` takes precedence, making `z-10` dead code.
- **Fix:** Remove `z-10` from the class list.

#### 🟢 LOW

**L-1.4.1: Dashboard KPI cards don't use the `kpi_card.html` component**

- **File:** `code/templates/admin_it/dashboard.html:17-59`
- **Issue:** Three inline KPI card blocks when `code/templates/components/kpi_card.html` exists. DRY violation.
- **Fix:** Refactor to use `{% include "components/kpi_card.html" %}` with appropriate variables.

**L-1.4.2: No test for form validation errors**

- **File:** `code/apps/users/tests/test_admin_it.py`
- **Issue:** Tests cover happy-path CRUD but no test for: duplicate department code, self-parent reference, missing required fields in department creation.
- **Fix:** Add negative test cases.

**L-1.4.3: `selectors.py:get_department_tree()` returns `list` not `QuerySet`**

- **File:** `code/apps/users/selectors.py:56-64`
- **Issue:** Returns `list(Department.objects.filter(...))` which forces immediate evaluation. Other selectors return `QuerySet`. Inconsistent pattern.
- **Fix:** Return the `QuerySet` directly unless caching is intentional.

---

## Recommended Actions (Priority Order)

### P0 — Must Fix Now

1. **Fix C-1.4.1:** Add hidden `is_active` input in `department_form.html` create branch
2. **Fix C-1.4.2:** Update story File List with correct filenames
3. **Fix M-1.4.1:** Add `department-search` URL or remove broken search reference

### P1 — Should Fix Soon

4. **Fix M-1.3.1:** Consolidate `PermissionDenied` imports in middleware
5. **Fix M-1.4.3:** Move form imports to module level in views.py
6. **Fix M-1.4.4:** Move `AdminRequiredMixin` to mixins.py
7. **Fix M-1.4.5:** Remove conflicting `z-10` from sidebar classes

### P2 — Nice to Have

8. **Fix M-1.3.3:** Add IP address capture in AuditLog for compliance
9. **Fix M-1.4.2:** Strengthen cycle validation in DepartmentForm for creation mode
10. **Fix L-1.4.1:** Refactor dashboard to use kpi_card component
11. **Fix L-1.4.2:** Add negative test cases for form validation

---

## Files Requiring Changes

| Priority | File | Changes Needed |
|----------|------|----------------|
| P0 | `code/templates/admin_it/partials/department_form.html` | Add hidden `is_active` input |
| P0 | `_bmad-output/implementation-artifacts/1-4-gestion-organigramme-institutionnel.md` | Fix File List |
| P0 | `code/templates/admin_it/organigramme_list.html` | Fix or remove search reference |
| P1 | `code/apps/users/middleware.py` | Consolidate PermissionDenied import |
| P1 | `code/apps/users/views.py` | Move form imports to top |
| P1 | `code/apps/users/mixins.py` | Add AdminRequiredMixin |
| P1 | `code/templates/partials/sidebar_*.html` | Remove `z-10` |
| P2 | `code/apps/users/services.py` | Add ip_address parameter |
| P2 | `code/templates/admin_it/dashboard.html` | Refactor to use kpi_card component |

---

*Generated by BMAD Code Review Workflow — Adversarial Review Mode*
