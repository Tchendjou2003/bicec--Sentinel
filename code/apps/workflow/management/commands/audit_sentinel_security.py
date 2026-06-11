"""
Commande d'audit de sécurité & fonctionnel — Sentinel

Audite l'intégralité des règles métier, transitions FSM, permissions RBAC par rôle
et tentatives de contournement, de la connexion jusqu'à la clôture + notifications.

ISOLATION : tout s'exécute dans une transaction.atomic() annulée à la fin
→ la BDD de dev reste STRICTEMENT inchangée. Chaque probe HTTP est encapsulée
dans un savepoint rollback (isolation + auto-réparation des erreurs DB).

Usage :
    python manage.py audit_sentinel_security
    python manage.py audit_sentinel_security --chapter 5
    python manage.py audit_sentinel_security --output /app/doc/security_audit_report.md
"""
import time
from datetime import timedelta

from django.core.management.base import BaseCommand
from django.db import transaction
from django.test import Client
from django.utils import timezone


class Command(BaseCommand):
    help = "Audit de sécurité & fonctionnel complet de Sentinel (rollback, sans effet sur la BDD)"

    def add_arguments(self, parser):
        parser.add_argument("--chapter", type=str, default=None,
                            help="Numéro de chapitre à exécuter seul (0-10)")
        parser.add_argument("--output", type=str,
                            default="doc/security_audit_report.md",
                            help="Chemin du rapport Markdown")

    # ════════════════════════════════════════════════════════════════════
    #  Infrastructure
    # ════════════════════════════════════════════════════════════════════
    def handle(self, *args, **options):
        self.results = []          # [{chapter, label, method, url, role, expected, actual, ok, remediation}]
        self.only_chapter = options["chapter"]
        self.output_path = options["output"]
        # Client qui propage les exceptions non gérées → détectées comme FAIL.
        # SERVER_NAME=localhost car ALLOWED_HOSTS ne contient pas 'testserver'.
        self.client = Client(raise_request_exception=True, SERVER_NAME="localhost")

        self.stdout.write("\n" + "═" * 64)
        self.stdout.write(self.style.MIGRATE_HEADING(
            "  SENTINEL — AUDIT DE SÉCURITÉ & FONCTIONNEL"))
        self.stdout.write("═" * 64)

        # Tout dans une transaction annulée — la dev DB est intacte à la fin.
        try:
            with transaction.atomic():
                self._setup_fixtures()

                chapters = [
                    ("1", "Authentification & Session", self._chapter_1_auth),
                    ("2", "RBAC — Accès aux pages par rôle", self._chapter_2_rbac),
                    ("3", "Isolation cross-département / cross-user", self._chapter_3_isolation),
                    ("4", "Transitions FSM invalides", self._chapter_4_fsm),
                    ("5", "Règles métier (guards de service)", self._chapter_5_business),
                    ("6", "Auditeur Externe (EXT) — Isolation", self._chapter_6_ext),
                    ("7", "Immutabilité post-soumission", self._chapter_7_immutable),
                    ("8", "Sceau HMAC & Intégrité", self._chapter_8_seal),
                    ("9", "Notifications", self._chapter_9_notifs),
                    ("10", "Pages Admin & IT", self._chapter_10_admin),
                ]
                for num, title, fn in chapters:
                    if self.only_chapter and self.only_chapter != num:
                        continue
                    self.stdout.write("")
                    self.stdout.write(self.style.HTTP_INFO(f"┌─ Chapitre {num} — {title}"))
                    self._current_chapter = (num, title)
                    fn()

                # Annulation explicite → aucune écriture conservée.
                transaction.set_rollback(True)
        except Exception as exc:  # pragma: no cover - filet de sécurité
            self.stderr.write(self.style.ERROR(f"\n❌ Erreur fatale durant l'audit : {exc}"))
            import traceback
            traceback.print_exc()

        self._print_summary()
        self._write_report()

    # ── Probe HTTP isolée (savepoint rollback systématique) ──────────────
    def _probe(self, method, url, *, user, expected, label, remediation="",
               data=None, follow=False):
        """Exécute une requête HTTP et compare le code de statut attendu."""
        role = self._role_of(user)
        actual = None
        sid = transaction.savepoint()
        try:
            if user is None:
                self.client.logout()
            else:
                self.client.force_login(user)
            fn = getattr(self.client, method.lower())
            resp = fn(url, data=data or {}, follow=follow)
            actual = resp.status_code
        except Exception as e:
            actual = f"EXC:{type(e).__name__}"
        finally:
            transaction.savepoint_rollback(sid)

        ok = (actual == expected)
        self._record(label=label, method=method, url=url, role=role,
                     expected=expected, actual=actual, ok=ok, remediation=remediation)
        return ok

    # ── Probe service-layer (pour règles métier / sceau) ─────────────────
    def _probe_callable(self, fn, *, expect_exc, label, remediation="", exc_match=None):
        """Exécute un appel service et vérifie qu'il lève (ou non) une exception."""
        actual = "OK (aucune exception)"
        ok = (expect_exc is None)
        sid = transaction.savepoint()
        try:
            fn()
            if expect_exc is not None:
                ok = False  # on attendait une exception, rien levé
        except Exception as e:  # noqa: BLE001
            actual = f"{type(e).__name__}: {str(e)[:60]}"
            if expect_exc is not None and isinstance(e, expect_exc):
                ok = True
                if exc_match and exc_match not in str(e):
                    ok = False
            else:
                ok = False
        finally:
            transaction.savepoint_rollback(sid)

        self._record(label=label, method="SERVICE", url="-", role="-",
                     expected=("exception " + expect_exc.__name__) if expect_exc else "succès",
                     actual=actual, ok=ok, remediation=remediation)
        return ok

    def _record(self, **kw):
        kw["chapter"] = self._current_chapter
        self.results.append(kw)
        icon = self.style.SUCCESS("  ✅") if kw["ok"] else self.style.ERROR("  ❌")
        detail = f"{kw['method']} {kw['url']} [{kw['role']}] → attendu {kw['expected']}, reçu {kw['actual']}"
        self.stdout.write(f"{icon} {kw['label']}")
        if not kw["ok"]:
            self.stdout.write(self.style.WARNING(f"       {detail}"))

    def _role_of(self, user):
        if user is None:
            return "anonyme"
        return user.role or "shell"

    # ════════════════════════════════════════════════════════════════════
    #  Chapitre 0 — Fixtures (persistées dans la transaction annulée)
    # ════════════════════════════════════════════════════════════════════
    def _setup_fixtures(self):
        from apps.users.models import Department, OrgUnitType, User
        from apps.workflow.models import RecommendationSource

        self.stdout.write(self.style.HTTP_INFO("┌─ Chapitre 0 — Création des fixtures de test (en mémoire)"))

        otype, _ = OrgUnitType.objects.get_or_create(
            code="AUDIT_DIR", defaults={"name": "Direction (audit)", "level": 1})

        self.dept_a = Department.objects.create(
            name="AUDIT Dept A (parent)", code="ADA", type=otype)
        self.dept_b = Department.objects.create(
            name="AUDIT Dept B (enfant)", code="ADB", type=otype, parent=self.dept_a)
        self.dept_other = Department.objects.create(
            name="AUDIT Dept Autre", code="ADX", type=otype)

        def mk(username, role="", dept=None, **extra):
            u = User.objects.create_user(
                username=username, password="AuditProbe123!", role=role,
                department=dept, **extra)
            return u

        self.u_audit = mk("AUDIT_audit", User.Role.AUDIT, self.dept_a)
        self.u_audit_admin = mk("AUDIT_auditadmin", User.Role.AUDIT, self.dept_a,
                                is_audit_admin=True)
        self.u_dm = mk("AUDIT_dm", User.Role.DM, self.dept_a)
        self.u_dm_other = mk("AUDIT_dm_other", User.Role.DM, self.dept_other)
        self.u_etp = mk("AUDIT_etp", User.Role.ETP, self.dept_a)
        self.u_dg = mk("AUDIT_dg", User.Role.DG, self.dept_a)
        self.u_ext = mk("AUDIT_ext", User.Role.EXT, self.dept_a, is_external=True)
        self.u_admin = mk("AUDIT_admin", User.Role.ADMIN, self.dept_a)
        self.u_shell = mk("AUDIT_shell", "", self.dept_a)  # coquille vide

        self.source, _ = RecommendationSource.objects.get_or_create(
            code="AUDITSRC", defaults={"label": "Audit Source", "is_external": False})

        self.all_roles = [
            ("AUDIT", self.u_audit), ("DM", self.u_dm), ("ETP", self.u_etp),
            ("DG", self.u_dg), ("EXT", self.u_ext), ("ADMIN", self.u_admin),
            ("shell", self.u_shell),
        ]
        self.stdout.write(self.style.SUCCESS("  ✅ 9 utilisateurs + 3 départements + 1 source créés"))

    # ── Helpers de construction d'état métier ────────────────────────────
    def _new_reco(self, *, dept=None, priority=None):
        from apps.workflow.models import Recommendation
        from apps.workflow.services import create_recommendation
        from apps.workflow.models import Recommendation as R
        dept = dept or self.dept_a
        return create_recommendation(
            data={
                "reference": f"AUDIT-{timezone.now().strftime('%H%M%S')}-{R.objects.count()}",
                "mission_date": timezone.now().date(),
                "mission_label": "Audit sécurité — reco test",
                "controlled_department": dept,
                "observations": "obs", "anomalous_dossiers": "",
                "description": "Description de test pour l'audit sécurité.",
                "source": self.source,
                "priority": priority or Recommendation.Priority.HAUTE,
                "department": dept,
                "due_date": timezone.now().date() + timedelta(days=30),
            },
            deliverables_data=[], performed_by=self.u_audit,
        )

    def _pdf(self, name="preuve.pdf"):
        from django.core.files.uploadedfile import SimpleUploadedFile
        return SimpleUploadedFile(
            name, b"%PDF-1.4 1 0 obj<</Type /Catalog>> endobj test",
            content_type="application/pdf")

    def _reco_pending_audit_via_dg(self, dg=None):
        """Crée une reco amenée en PENDING_AUDIT_REVIEW via soumission DG (avec fichier)."""
        from apps.workflow.services import (
            assign_recommendation_to_dg, get_or_create_draft_submission,
            add_file_to_draft, save_draft_comment, submit_evidence_by_dg)
        dg = dg or self.u_dg
        rec = self._new_reco()
        rec = assign_recommendation_to_dg(recommendation=rec, dg=dg, performed_by=self.u_audit)
        draft, _ = get_or_create_draft_submission(recommendation=rec, user=dg)
        add_file_to_draft(submission=draft, file=self._pdf(), user=dg)
        save_draft_comment(submission=draft, comment="Preuves de test soumises.", user=dg)
        rec = submit_evidence_by_dg(recommendation=rec, performed_by=dg)
        return rec

    # ════════════════════════════════════════════════════════════════════
    #  Chapitre 1 — Authentification & Session
    # ════════════════════════════════════════════════════════════════════
    def _chapter_1_auth(self):
        from axes.utils import reset

        # Page de login publique
        self._probe("GET", "/auth/login/", user=None, expected=200,
                    label="Page de login accessible sans authentification")

        # Accès protégé sans session → redirection login
        self._probe("GET", "/audit/recommandations/", user=None, expected=302,
                    label="Accès workflow sans session → redirection login",
                    remediation="Vérifier LoginRequiredMixin / LOGIN_URL.")

        # Compte shell (sans rôle) → redirigé vers pending
        self._probe("GET", "/audit/recommandations/", user=self.u_shell, expected=302,
                    label="Compte shell (sans rôle) → redirection /auth/pending/",
                    remediation="RoleRequiredMiddleware doit rediriger les coquilles vides.")

        # Brute-force Axes : 5 échecs → lockout au 6ᵉ
        probe_user = "AUDIT_brute_probe"
        reset(username=probe_user)
        sid = transaction.savepoint()
        try:
            locked = False
            for i in range(6):
                r = self.client.post("/auth/login/",
                                     {"username": probe_user, "password": "WRONG"})
                if r.status_code == 403 or (hasattr(r, "context") and r.status_code == 429):
                    locked = True
            self._record(label="Brute-force : lockout Axes après 5 échecs",
                         method="POST", url="/auth/login/", role="anonyme",
                         expected="lockout (403)", actual=("lockout" if locked else "PAS de lockout"),
                         ok=locked,
                         remediation="Vérifier AXES_FAILURE_LIMIT=5 et AxesMiddleware après AuthenticationMiddleware.")
        finally:
            transaction.savepoint_rollback(sid)
            reset(username=probe_user)

        # Idle timeout : _last_activity ancien → déconnexion
        sid = transaction.savepoint()
        try:
            self.client.force_login(self.u_audit)
            s = self.client.session
            s["_last_activity"] = time.time() - 2000  # > 1800s
            s.save()
            r = self.client.get("/audit/recommandations/")
            ok = (r.status_code == 302)
            self._record(label="Session idle > 30 min → déconnexion automatique",
                         method="GET", url="/audit/recommandations/", role="AUDIT",
                         expected=302, actual=r.status_code, ok=ok,
                         remediation="IdleTimeoutMiddleware doit déconnecter si _last_activity dépassé.")
        finally:
            transaction.savepoint_rollback(sid)

    # ════════════════════════════════════════════════════════════════════
    #  Chapitre 2 — RBAC par rôle
    # ════════════════════════════════════════════════════════════════════
    def _chapter_2_rbac(self):
        rec = self._new_reco()

        # Liste : workflow roles OK, EXT/ADMIN 403, shell 302
        for role, u in self.all_roles:
            exp = 200 if role in ("AUDIT", "DM", "ETP", "DG") else (302 if role == "shell" else 403)
            self._probe("GET", "/audit/recommandations/", user=u, expected=exp,
                        label=f"Liste recommandations — {role}",
                        remediation="WorkflowAccessMixin : AUDIT/DM/ETP/DG seulement ; EXT bloqué middleware ; ADMIN 403.")

        # Création : AUDIT seulement
        for role, u in self.all_roles:
            exp = 200 if role == "AUDIT" else (302 if role == "shell" else 403)
            self._probe("GET", "/audit/recommandations/create/", user=u, expected=exp,
                        label=f"Page création reco — {role}",
                        remediation="AuditRequiredMixin : seul AUDIT/superuser.")

        # Assignation DM (POST) : AUDIT seulement — autres 403
        for role, u in [("DM", self.u_dm), ("ETP", self.u_etp), ("DG", self.u_dg),
                        ("EXT", self.u_ext), ("ADMIN", self.u_admin)]:
            exp = 403
            self._probe("POST", f"/audit/recommandations/{rec.pk}/assign/", user=u, expected=exp,
                        label=f"POST assign DM — {role} (doit être refusé)",
                        remediation="AuditRequiredMixin sur RecommendationAssignView.")

        # Clôture (POST) sur reco non éligible : tous sauf AUDIT → 403
        for role, u in [("DM", self.u_dm), ("DG", self.u_dg), ("ETP", self.u_etp)]:
            self._probe("POST", f"/audit/recommandations/{rec.pk}/close-audit/", user=u, expected=403,
                        label=f"POST close-audit — {role} (doit être refusé)",
                        remediation="AuditRequiredMixin sur RecommendationCloseByAuditView.")

    # ════════════════════════════════════════════════════════════════════
    #  Chapitre 3 — Isolation cross-département / cross-user
    # ════════════════════════════════════════════════════════════════════
    def _chapter_3_isolation(self):
        # Reco du dept_a ; DM d'un autre département ne doit pas la voir → 404
        rec = self._new_reco(dept=self.dept_a)
        from apps.workflow.services import assign_recommendation_to_dm
        rec = assign_recommendation_to_dm(recommendation=rec, dm=self.u_dm,
                                          performed_by=self.u_audit)
        detail = f"/audit/recommandations/{rec.pk}/"

        self._probe("GET", detail, user=self.u_dm_other, expected=404,
                    label="DM d'un autre département → reco invisible (404)",
                    remediation="get_recommendations_for_user() filtre par hiérarchie de département.")

        self._probe("GET", detail, user=self.u_dm, expected=200,
                    label="DM assigné (même dept) → accès reco (200)")

        # ETP non assigné → 404
        self._probe("GET", detail, user=self.u_etp, expected=404,
                    label="ETP non assigné → reco invisible (404)",
                    remediation="ETP ne voit que assigned_etp == user.")

        # DG non assigné → 404
        self._probe("GET", detail, user=self.u_dg, expected=404,
                    label="DG non assigné → reco invisible (404)",
                    remediation="DG ne voit que assigned_dm == user (assignation personnelle).")

    # ════════════════════════════════════════════════════════════════════
    #  Chapitre 4 — Transitions FSM invalides
    # ════════════════════════════════════════════════════════════════════
    def _chapter_4_fsm(self):
        from apps.workflow.models import Recommendation

        # submit-evidence sur DRAFT par un ETP non-AUDIT → 404
        # (une reco DRAFT est invisible aux non-AUDIT : on ne révèle pas son existence —
        # comportement plus sûr que 403, le selector renvoie 404 avant la garde FSM).
        draft_rec = self._new_reco()
        self._probe("POST", f"/audit/recommandations/{draft_rec.pk}/submit-evidence/",
                    user=self.u_etp, expected=404,
                    label="submit-evidence sur DRAFT (ETP) → 404 (reco invisible, non révélée)",
                    remediation="OK : selector RBAC renvoie 404 pour les DRAFT aux non-AUDIT (ne fuit pas l'existence).")

        # close-audit sur reco IN_PROGRESS → 422
        from apps.workflow.services import assign_recommendation_to_dg
        ip_rec = self._new_reco()
        ip_rec = assign_recommendation_to_dg(recommendation=ip_rec, dg=self.u_dg,
                                             performed_by=self.u_audit)  # → IN_PROGRESS
        self._probe("POST", f"/audit/recommandations/{ip_rec.pk}/close-audit/",
                    user=self.u_audit, expected=422,
                    label="close-audit sur IN_PROGRESS → 422 (état invalide)",
                    remediation="Garde FSM dans close_recommendation_by_audit().")

        # reject-audit sur reco IN_PROGRESS → 422
        self._probe("POST", f"/audit/recommandations/{ip_rec.pk}/reject-audit/",
                    user=self.u_audit, expected=422, data={"reason": "motif suffisant ok"},
                    label="reject-audit sur IN_PROGRESS → 422 (état invalide)",
                    remediation="Garde FSM dans reject_recommendation_by_audit().")

        # Double soumission DG : reco déjà PENDING_AUDIT_REVIEW → 422
        pa_rec = self._reco_pending_audit_via_dg()
        self._probe("POST", f"/audit/recommandations/{pa_rec.pk}/submit-dg/",
                    user=self.u_dg, expected=422,
                    label="Double soumission DG (déjà PENDING_AUDIT_REVIEW) → 422",
                    remediation="Garde FSM ASSIGNED/IN_PROGRESS dans submit_evidence_by_dg().")

        # Double clôture : clôturer puis re-clôturer → 422
        from apps.workflow.services import close_recommendation_by_audit
        sid = transaction.savepoint()
        try:
            close_recommendation_by_audit(recommendation=pa_rec, performed_by=self.u_audit)
            # 2ᵉ tentative via HTTP
        except Exception:
            pass
        finally:
            transaction.savepoint_rollback(sid)
        # (vérifié via _ensure_not_closed au chapitre 7)

    # ════════════════════════════════════════════════════════════════════
    #  Chapitre 5 — Règles métier (guards de service)
    # ════════════════════════════════════════════════════════════════════
    def _chapter_5_business(self):
        from apps.workflow.services import (
            assign_recommendation_to_dg, get_or_create_draft_submission,
            add_file_to_draft, save_draft_comment, submit_evidence_by_dg,
            reject_recommendation_by_audit, request_extension)

        # F1 — DG soumet sans fichier (commentaire seul) → ValueError
        def dg_no_file():
            rec = self._new_reco()
            rec = assign_recommendation_to_dg(recommendation=rec, dg=self.u_dg, performed_by=self.u_audit)
            draft, _ = get_or_create_draft_submission(recommendation=rec, user=self.u_dg)
            save_draft_comment(submission=draft, comment="commentaire seul sans fichier", user=self.u_dg)
            submit_evidence_by_dg(recommendation=rec, performed_by=self.u_dg)
        self._probe_callable(dg_no_file, expect_exc=ValueError,
                             label="F1 — DG soumet sans fichier → refusé",
                             exc_match="fichier",
                             remediation="Garde dans submit_evidence_by_dg : fichier obligatoire.")

        # F1bis — DG soumet sans commentaire → ValueError
        def dg_no_comment():
            rec = self._new_reco()
            rec = assign_recommendation_to_dg(recommendation=rec, dg=self.u_dg, performed_by=self.u_audit)
            draft, _ = get_or_create_draft_submission(recommendation=rec, user=self.u_dg)
            add_file_to_draft(submission=draft, file=self._pdf(), user=self.u_dg)
            submit_evidence_by_dg(recommendation=rec, performed_by=self.u_dg)
        self._probe_callable(dg_no_comment, expect_exc=ValueError,
                             label="DG soumet sans commentaire → refusé",
                             remediation="Garde commentaire obligatoire dans submit_evidence_by_dg.")

        # Cas positif — DG soumet fichier + commentaire → succès
        def dg_ok():
            self._reco_pending_audit_via_dg()
        self._probe_callable(dg_ok, expect_exc=None,
                             label="DG soumet fichier + commentaire → succès")

        # Rejet Audit motif trop court → ValueError
        def reject_short():
            rec = self._reco_pending_audit_via_dg()
            reject_recommendation_by_audit(recommendation=rec, reason="court", performed_by=self.u_audit)
        self._probe_callable(reject_short, expect_exc=ValueError,
                             label="Rejet Audit motif < 10 chars → refusé",
                             remediation="Garde longueur motif dans reject_recommendation_by_audit.")

        # F2 — clôture sans fichier (soumission ACCEPTED sans EvidenceFile) → ValueError
        def close_no_file():
            from apps.workflow.models import EvidenceSubmission, Recommendation
            from apps.workflow.services import close_recommendation_by_audit
            rec = self._new_reco()
            rec = assign_recommendation_to_dg(recommendation=rec, dg=self.u_dg, performed_by=self.u_audit)
            # Forcer une soumission ACCEPTED SANS fichier + statut PENDING_AUDIT_REVIEW
            EvidenceSubmission.objects.create(
                recommendation=rec, submitted_by=self.u_dg,
                status=EvidenceSubmission.SubmissionStatus.ACCEPTED, comment="sans fichier")
            Recommendation.all_objects.filter(pk=rec.pk).update(status="PENDING_AUDIT_REVIEW")
            rec = Recommendation.all_objects.get(pk=rec.pk)
            close_recommendation_by_audit(recommendation=rec, performed_by=self.u_audit)
        self._probe_callable(close_no_file, expect_exc=ValueError,
                             label="F2 — clôture sans preuve fichier → refusé",
                             exc_match="preuve",
                             remediation="Garde has_evidence_files dans close_recommendation_by_audit.")

        # Report avec date <= due_date → erreur
        def ext_bad_date():
            rec = self._new_reco()
            rec = assign_recommendation_to_dg(recommendation=rec, dg=self.u_dg, performed_by=self.u_audit)
            request_extension(recommendation=rec,
                              requested_date=rec.due_date - timedelta(days=1),
                              reason="motif de report suffisant", performed_by=self.u_dg)
        self._probe_callable(ext_bad_date, expect_exc=Exception,
                             label="Report avec date antérieure → refusé",
                             remediation="Validation requested_date > due_date dans request_extension.")

    # ════════════════════════════════════════════════════════════════════
    #  Chapitre 6 — EXT (Auditeur Externe)
    # ════════════════════════════════════════════════════════════════════
    def _chapter_6_ext(self):
        rec = self._new_reco()
        self._probe("GET", "/audit/recommandations/", user=self.u_ext, expected=403,
                    label="EXT → liste workflow refusée (403)",
                    remediation="ExternalIsolationMiddleware AC3 : vues internes bloquées.")
        self._probe("GET", f"/audit/recommandations/{rec.pk}/", user=self.u_ext, expected=403,
                    label="EXT → détail reco refusé (403)",
                    remediation="ExternalIsolationMiddleware AC3.")
        self._probe("POST", "/audit/recommandations/create/", user=self.u_ext, expected=403,
                    label="EXT → écriture (POST) refusée (403)",
                    remediation="ExternalIsolationMiddleware AC1 : écritures bloquées.")
        self._probe("GET", "/auth/external/dashboard/", user=self.u_ext, expected=200,
                    label="EXT → dashboard externe autorisé (200)")

    # ════════════════════════════════════════════════════════════════════
    #  Chapitre 7 — Immutabilité post-clôture
    # ════════════════════════════════════════════════════════════════════
    def _chapter_7_immutable(self):
        from apps.workflow.models import Recommendation
        from apps.workflow.services import close_recommendation_by_audit

        # Clôturer une reco puis tenter des mutations → 422 _ensure_not_closed
        rec = self._reco_pending_audit_via_dg()
        sid = transaction.savepoint()
        try:
            close_recommendation_by_audit(recommendation=rec, performed_by=self.u_audit)
            pk = rec.pk
            # Re-clôture
            self._probe("POST", f"/audit/recommandations/{pk}/close-audit/",
                        user=self.u_audit, expected=422,
                        label="Mutation sur reco CLOSED : re-clôture → 422",
                        remediation="_ensure_not_closed() doit bloquer toute mutation post-clôture.")
            # Tentative de soumission DG sur reco clôturée
            self._probe("POST", f"/audit/recommandations/{pk}/submit-dg/",
                        user=self.u_dg, expected=422,
                        label="Mutation sur reco CLOSED : submit-dg → 422",
                        remediation="_ensure_not_closed() sur EvidenceDGDirectSubmitView.")
            # Lecture toujours possible
            self._probe("GET", f"/audit/recommandations/{pk}/",
                        user=self.u_audit, expected=200,
                        label="Lecture d'une reco CLOSED → 200 (toujours consultable)")
        finally:
            transaction.savepoint_rollback(sid)

    # ════════════════════════════════════════════════════════════════════
    #  Chapitre 8 — Sceau HMAC & Intégrité
    # ════════════════════════════════════════════════════════════════════
    def _chapter_8_seal(self):
        from apps.audit.services import verify_recommendation_seal, generate_recommendation_seal
        from apps.workflow.models import Recommendation
        from apps.workflow.services import close_recommendation_by_audit

        # Clôture avec preuves → sceau valide
        def seal_valid():
            rec = self._reco_pending_audit_via_dg()
            rec = close_recommendation_by_audit(recommendation=rec, performed_by=self.u_audit)
            rec = Recommendation.all_objects.select_related("hmac_seal").get(pk=rec.pk)
            assert getattr(rec, "hmac_seal", None) is not None, "Sceau non généré"
            assert verify_recommendation_seal(rec) is True, "verify() != True"
        self._probe_callable(seal_valid, expect_exc=None,
                             label="Clôture avec preuves → sceau généré + verify=True")

        # Altération post-clôture → verify=False
        def seal_tampered():
            rec = self._reco_pending_audit_via_dg()
            rec = close_recommendation_by_audit(recommendation=rec, performed_by=self.u_audit)
            Recommendation.all_objects.filter(pk=rec.pk).update(description="ALTÉRÉ APRÈS SCELLEMENT")
            rec = Recommendation.all_objects.select_related("hmac_seal").get(pk=rec.pk)
            assert verify_recommendation_seal(rec) is False, "Altération NON détectée"
        self._probe_callable(seal_tampered, expect_exc=None,
                             label="Altération post-clôture → verify=False (détectée)",
                             remediation="Si échoue : le payload HMAC n'inclut pas le champ altéré.")

        # F3 — sceau sur dossier sans fichier → ValueError
        def seal_no_file():
            from apps.workflow.models import EvidenceSubmission
            rec = self._new_reco()
            EvidenceSubmission.objects.create(
                recommendation=rec, submitted_by=self.u_dg,
                status=EvidenceSubmission.SubmissionStatus.ACCEPTED, comment="x")
            generate_recommendation_seal(recommendation=rec, sealed_by=self.u_audit)
        self._probe_callable(seal_no_file, expect_exc=ValueError,
                             label="F3 — scellement sans fichier probatoire → refusé",
                             exc_match="fichier",
                             remediation="Garde file_hashes non vide dans generate_recommendation_seal.")

    # ════════════════════════════════════════════════════════════════════
    #  Chapitre 9 — Notifications
    # ════════════════════════════════════════════════════════════════════
    def _chapter_9_notifs(self):
        from apps.notifications.models import Notification
        from apps.notifications.services import emit_notification

        # Dropdown sans auth → 302
        self._probe("GET", "/notifications/dropdown/", user=None, expected=302,
                    label="Dropdown notifications sans auth → 302")
        # Dropdown avec auth → 200
        self._probe("GET", "/notifications/dropdown/", user=self.u_dm, expected=200,
                    label="Dropdown notifications avec auth → 200")

        # Notif d'un autre user : mark-read → 404
        notif = emit_notification(
            recipient=self.u_audit, notification_type=Notification.Type.ASSIGNED,
            title="probe", idempotency_key="AUDIT_PROBE_NOTIF")
        self._probe("POST", f"/notifications/{notif.pk}/mark-read/", user=self.u_dm, expected=404,
                    label="mark-read sur notif d'un autre user → 404",
                    remediation="Filtrer recipient=request.user dans NotificationMarkReadView.")

        # Idempotence emit
        def emit_dup():
            n1 = emit_notification(recipient=self.u_dm, notification_type=Notification.Type.CLOSED,
                                   title="dup", idempotency_key="AUDIT_PROBE_DUP")
            n2 = emit_notification(recipient=self.u_dm, notification_type=Notification.Type.CLOSED,
                                   title="dup", idempotency_key="AUDIT_PROBE_DUP")
            assert n1 is not None and n2 is None, "Doublon de notification créé"
        self._probe_callable(emit_dup, expect_exc=None,
                             label="emit_notification idempotent (même clé → pas de doublon)")

    # ════════════════════════════════════════════════════════════════════
    #  Chapitre 10 — Pages Admin & IT
    # ════════════════════════════════════════════════════════════════════
    def _chapter_10_admin(self):
        # Gestion utilisateurs IT : ADMIN seulement
        for role, u in self.all_roles:
            exp = 200 if role == "ADMIN" else (302 if role == "shell" else 403)
            self._probe("GET", "/auth/admin/utilisateurs/", user=u, expected=exp,
                        label=f"Gestion utilisateurs IT — {role}",
                        remediation="AdminRequiredMixin : ADMIN/staff/superuser seulement.")

        # Habilitation : Audit Admin seulement (AUDIT simple → 403)
        self._probe("GET", "/audit/habilitation/", user=self.u_audit, expected=403,
                    label="Habilitation — AUDIT simple (sans is_audit_admin) → 403",
                    remediation="AuditAdminRequiredMixin : can_manage_users = AUDIT + is_audit_admin.")
        self._probe("GET", "/audit/habilitation/", user=self.u_audit_admin, expected=200,
                    label="Habilitation — Audit Admin → 200")
        self._probe("GET", "/audit/habilitation/", user=self.u_dm, expected=403,
                    label="Habilitation — DM → 403")

        # Sources admin : Audit Admin seulement
        self._probe("GET", "/audit/sources-admin/", user=self.u_audit_admin, expected=200,
                    label="Sources admin — Audit Admin → 200")
        self._probe("GET", "/audit/sources-admin/", user=self.u_dm, expected=403,
                    label="Sources admin — DM → 403",
                    remediation="AuditAdminRequiredMixin.")

        # Organigramme : Audit Admin seulement
        self._probe("GET", "/auth/admin/organigramme/", user=self.u_audit_admin, expected=200,
                    label="Organigramme — Audit Admin → 200")
        self._probe("GET", "/auth/admin/organigramme/", user=self.u_etp, expected=403,
                    label="Organigramme — ETP → 403")

        # Dashboard externe : EXT seulement
        self._probe("GET", "/auth/external/dashboard/", user=self.u_dm, expected=403,
                    label="Dashboard externe — DM (non-EXT) → 403/redirect",
                    remediation="Vue réservée aux EXT.")

    # ════════════════════════════════════════════════════════════════════
    #  Rapport
    # ════════════════════════════════════════════════════════════════════
    def _print_summary(self):
        total = len(self.results)
        passed = sum(1 for r in self.results if r["ok"])
        failed = total - passed
        self.stdout.write("\n" + "─" * 64)
        style = self.style.SUCCESS if failed == 0 else self.style.ERROR
        self.stdout.write(style(f"  RÉSULTAT : {passed}/{total} PASS  |  {failed} FAIL"))
        self.stdout.write("─" * 64)
        if failed:
            self.stdout.write(self.style.WARNING("\n  Failles / écarts détectés :"))
            for r in self.results:
                if not r["ok"]:
                    self.stdout.write(f"   ❌ [Ch{r['chapter'][0]}] {r['label']}")

    def _write_report(self):
        from collections import OrderedDict
        total = len(self.results)
        passed = sum(1 for r in self.results if r["ok"])
        failed = total - passed
        now = timezone.localtime().strftime("%Y-%m-%d %H:%M:%S (%Z)")

        by_chap = OrderedDict()
        for r in self.results:
            by_chap.setdefault(r["chapter"], []).append(r)

        lines = []
        lines.append("# Rapport d'Audit Sécurité & Fonctionnel — Sentinel\n")
        lines.append(f"**Date** : {now}  ")
        lines.append(f"**Résultat global** : {passed}/{total} PASS — **{failed} FAIL**\n")
        lines.append("> Audit généré par `manage.py audit_sentinel_security` "
                     "(transaction annulée, BDD de dev inchangée).\n")

        # Résumé exécutif
        lines.append("## Résumé exécutif\n")
        lines.append("| Chapitre | PASS | FAIL |")
        lines.append("|----------|------|------|")
        for (num, title), rs in by_chap.items():
            p = sum(1 for r in rs if r["ok"])
            lines.append(f"| {num} — {title} | {p}/{len(rs)} | {len(rs)-p} |")
        lines.append("")

        # Failles
        if failed:
            lines.append("## ⚠️ Failles / écarts détectés\n")
            for (num, title), rs in by_chap.items():
                fails = [r for r in rs if not r["ok"]]
                if not fails:
                    continue
                lines.append(f"### Chapitre {num} — {title}\n")
                for r in fails:
                    lines.append(f"- **❌ {r['label']}**")
                    lines.append(f"  - Requête : `{r['method']} {r['url']}` — rôle `{r['role']}`")
                    lines.append(f"  - Attendu : `{r['expected']}` — Reçu : `{r['actual']}`")
                    if r.get("remediation"):
                        lines.append(f"  - **Correction suggérée** : {r['remediation']}")
                    lines.append("")
        else:
            lines.append("## ✅ Aucune faille détectée\n")
            lines.append("Toutes les règles métier, transitions et permissions sont respectées.\n")

        # Détail PASS par chapitre
        lines.append("## Détail complet\n")
        for (num, title), rs in by_chap.items():
            lines.append(f"### Chapitre {num} — {title}\n")
            for r in rs:
                icon = "✅" if r["ok"] else "❌"
                lines.append(f"- {icon} {r['label']} "
                             f"(`{r['method']} {r['url']}` [{r['role']}] → "
                             f"attendu {r['expected']}, reçu {r['actual']})")
            lines.append("")

        content = "\n".join(lines)
        import os
        os.makedirs(os.path.dirname(self.output_path), exist_ok=True)
        with open(self.output_path, "w", encoding="utf-8") as f:
            f.write(content)
        self.stdout.write(self.style.SUCCESS(f"\n  📄 Rapport écrit : {self.output_path}"))
