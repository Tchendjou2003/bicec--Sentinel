"""
Workflow App — Tests Import Excel (Story 6.5 — FR7)

Couvre :
  - parse_workbook    : validateur format, plafond, dates
  - validate_rows     : champs requis, FK, doublons, date passée
  - create_recommendations_bulk : atomicité, ImportBatch, AuditLog, livrables
  - build_import_template : structure .xlsx
  - Vues d'import     : RBAC, workflow preview/confirm
  - Concurrence (AC8) : re-validation entre preview et confirm
"""
import io
import tempfile
import uuid
from datetime import date, timedelta
from unittest import mock

import openpyxl
from django.core.exceptions import ValidationError
from django.core.files.uploadedfile import SimpleUploadedFile
from django.db import IntegrityError
from django.test import TestCase, override_settings
from django.urls import reverse
from django.utils import timezone

from apps.audit.models import AuditLog
from apps.users.models import Department, OrgUnitType, User
from apps.workflow.import_excel import (
    DATA_SHEET_NAME,
    HEADERS,
    MAX_ROWS,
    ImportReport,
    RowDraft,
    ValidRow,
    build_import_template,
    create_recommendations_bulk,
    parse_workbook,
    run_recommendations_import_task,
    validate_rows,
)
from apps.workflow.models import (
    Deliverable,
    ImportBatch,
    Recommendation,
    RecommendationSource,
)


# ── Fixtures partagées ────────────────────────────────────────────────────────


class ImportTestMixin:
    """Données de base partagées entre tous les groupes de tests."""

    @classmethod
    def setUpTestData(cls):
        cls.org_type, _ = OrgUnitType.objects.get_or_create(
            code="DIRECTION", defaults={"name": "Direction", "level": 1},
        )
        cls.dept = Department.objects.create(
            name="Direction des Opérations", code="DOP", type=cls.org_type,
        )
        cls.dept_inactive = Department.objects.create(
            name="Ancienne Direction", code="OLD", type=cls.org_type, is_active=False,
        )
        cls.source_cobac, _ = RecommendationSource.objects.get_or_create(
            code="COBAC", defaults={"label": "COBAC", "is_external": True},
        )
        cls.source_inactive = RecommendationSource.objects.create(
            code="DEFUNCT", label="Defunct Source", is_external=True, is_active=False,
        )
        cls.audit_user = User.objects.create_user(
            username="audit_import", password="TestPass123!", role=User.Role.AUDIT,
        )
        cls.dm_user = User.objects.create_user(
            username="dm_import", password="TestPass123!", role=User.Role.DM,
        )
        cls.etp_user = User.objects.create_user(
            username="etp_import", password="TestPass123!", role=User.Role.ETP,
        )

    def _future(self, days=90) -> date:
        return timezone.now().date() + timedelta(days=days)

    def _past(self, days=10) -> date:
        return timezone.now().date() - timedelta(days=days)

    def _make_xlsx(self, rows: list[list], *, sheet_name: str = DATA_SHEET_NAME) -> io.BytesIO:
        """Construit un .xlsx en mémoire avec le bon en-tête + les lignes fournies."""
        wb = openpyxl.Workbook()
        ws = wb.active
        ws.title = sheet_name
        ws.append(HEADERS)
        for row in rows:
            ws.append(row)
        buf = io.BytesIO()
        wb.save(buf)
        buf.seek(0)
        buf.name = "test.xlsx"
        buf.size = buf.getbuffer().nbytes
        return buf

    def _valid_row_list(self, ref: str = "REC-TEST-001") -> list:
        """Ligne Excel 100 % valide."""
        return [
            ref,                          # Référence
            "COBAC",                      # Source
            "HAUTE",                      # Criticité
            "Description de la reco",     # Description
            self._future(),               # Date cible (date native)
            "Mission Test",               # Titre (mission)
            timezone.now().date(),        # Date de mission
            "DOP",                        # Direction contrôlée
            "DOP",                        # Direction concernée
            "Observations",               # Observations
            "Dossiers",                   # Dossiers en anomalies
            "Livrable A ; Livrable B",    # Livrables
        ]

    def _valid_row_draft(self, ref: str = "REC-TEST-001") -> RowDraft:
        """RowDraft 100 % valide."""
        return RowDraft(
            row_number=2,
            reference=ref,
            source_raw="COBAC",
            priority="HAUTE",
            description="Description de la reco",
            due_date_raw=self._future(),
            mission_label="Mission Test",
            mission_date_raw=timezone.now().date(),
            controlled_department_raw="DOP",
            department_raw="DOP",
            observations="Observations",
            anomalous_dossiers="Dossiers",
            deliverables_raw="Livrable A ; Livrable B",
        )


# ── Tests parse_workbook ──────────────────────────────────────────────────────


class ParseWorkbookTest(ImportTestMixin, TestCase):

    def test_fichier_valide_retourne_liste_row_draft(self):
        buf = self._make_xlsx([self._valid_row_list("REC-PARSE-001")])
        rows = parse_workbook(buf)
        self.assertEqual(len(rows), 1)
        self.assertIsInstance(rows[0], RowDraft)
        self.assertEqual(rows[0].reference, "REC-PARSE-001")
        self.assertEqual(rows[0].row_number, 2)

    def test_lignes_vides_ignorees(self):
        buf = self._make_xlsx([
            self._valid_row_list("REC-PARSE-002"),
            [None] * 12,  # ligne vide
        ])
        rows = parse_workbook(buf)
        self.assertEqual(len(rows), 1)

    def test_onglet_donnees_absent_raise(self):
        buf = self._make_xlsx([], sheet_name="Feuille1")
        with self.assertRaises(ValidationError) as ctx:
            parse_workbook(buf)
        self.assertIn("introuvable", ctx.exception.message.lower())

    def test_date_excel_native_convertie(self):
        row = self._valid_row_list("REC-DATE-001")
        row[4] = date(2026, 12, 31)  # date native
        buf = self._make_xlsx([row])
        rows = parse_workbook(buf)
        self.assertIsInstance(rows[0].due_date_raw, date)
        self.assertEqual(rows[0].due_date_raw, date(2026, 12, 31))

    def test_date_iso_texte_acceptee(self):
        row = self._valid_row_list("REC-DATE-002")
        row[4] = "2026-12-31"
        buf = self._make_xlsx([row])
        rows = parse_workbook(buf)
        self.assertIsInstance(rows[0].due_date_raw, date)

    def test_date_format_ambigu_garde_brut(self):
        row = self._valid_row_list("REC-DATE-003")
        row[4] = "31/12/2026"  # JJ/MM/AAAA — non accepté
        buf = self._make_xlsx([row])
        rows = parse_workbook(buf)
        self.assertIsInstance(rows[0].due_date_raw, str)

    def test_plafond_max_rows_raise(self):
        rows_data = [self._valid_row_list(f"REC-MAX-{i:03d}") for i in range(MAX_ROWS + 1)]
        buf = self._make_xlsx(rows_data)
        with self.assertRaises(ValidationError) as ctx:
            parse_workbook(buf)
        self.assertIn(str(MAX_ROWS), ctx.exception.message)

    def test_fichier_exactement_max_rows_accepte(self):
        rows_data = [self._valid_row_list(f"REC-MAX-{i:03d}") for i in range(MAX_ROWS)]
        buf = self._make_xlsx(rows_data)
        rows = parse_workbook(buf)
        self.assertEqual(len(rows), MAX_ROWS)

    def test_fichier_trop_grand_raise(self):
        buf = self._make_xlsx([self._valid_row_list()])
        # Simuler un fichier > 6 Mo
        buf.size = 7 * 1024 * 1024
        with self.assertRaises(ValidationError) as ctx:
            parse_workbook(buf)
        self.assertIn("6", ctx.exception.message)


# ── Tests validate_rows ───────────────────────────────────────────────────────


class ValidateRowsTest(ImportTestMixin, TestCase):

    def _report(self, rows, extra_refs=None):
        existing = set(extra_refs or [])
        return validate_rows(rows, existing_refs=existing)

    def test_ligne_valide_aucune_erreur(self):
        report = self._report([self._valid_row_draft()])
        self.assertEqual(report.error_count, 0)
        self.assertEqual(report.valid_count, 1)

    def test_total_correspond_au_nombre_de_lignes(self):
        rows = [self._valid_row_draft(f"REC-V-{i:03d}") for i in range(3)]
        report = self._report(rows)
        self.assertEqual(report.total, 3)

    def test_reference_manquante(self):
        row = self._valid_row_draft()
        row.reference = ""
        report = self._report([row])
        self.assertIn(2, report.errors_by_row)
        self.assertTrue(any("obligatoire" in e.lower() for e in report.errors_by_row[2]))

    def test_description_manquante(self):
        row = self._valid_row_draft()
        row.description = ""
        report = self._report([row])
        self.assertIn(2, report.errors_by_row)

    def test_source_inconnue_erreur(self):
        row = self._valid_row_draft()
        row.source_raw = "XXXX_INCONNU"
        report = self._report([row])
        self.assertIn(2, report.errors_by_row)
        self.assertTrue(any("source" in e.lower() for e in report.errors_by_row[2]))

    def test_source_inactive_erreur(self):
        row = self._valid_row_draft()
        row.source_raw = "DEFUNCT"
        report = self._report([row])
        self.assertIn(2, report.errors_by_row)

    def test_criticite_invalide(self):
        row = self._valid_row_draft()
        row.priority = "ULTRA"
        report = self._report([row])
        self.assertIn(2, report.errors_by_row)
        self.assertTrue(any("criticité" in e.lower() for e in report.errors_by_row[2]))

    def test_date_passee_rejetee(self):
        row = self._valid_row_draft()
        row.due_date_raw = self._past()
        report = self._report([row])
        self.assertIn(2, report.errors_by_row)
        self.assertTrue(any("passé" in e for e in report.errors_by_row[2]))

    def test_date_illisible_rejetee(self):
        row = self._valid_row_draft()
        row.due_date_raw = "31/12/2026"  # brut (non ISO)
        report = self._report([row])
        self.assertIn(2, report.errors_by_row)
        self.assertTrue(any("illisible" in e for e in report.errors_by_row[2]))

    def test_doublon_intra_fichier_bidirectionnel(self):
        r1 = self._valid_row_draft("REC-DUP-001")
        r2 = RowDraft(
            row_number=3, reference="REC-DUP-001", source_raw="COBAC",
            priority="HAUTE", description="Desc 2", due_date_raw=self._future(),
            mission_label="", mission_date_raw=None, controlled_department_raw="",
            department_raw="", observations="", anomalous_dossiers="", deliverables_raw="",
        )
        report = self._report([r1, r2])
        # Les deux lignes doivent être en erreur
        self.assertIn(2, report.errors_by_row)
        self.assertIn(3, report.errors_by_row)
        # Chaque erreur cite l'autre ligne
        self.assertTrue(any("3" in e for e in report.errors_by_row[2]))
        self.assertTrue(any("2" in e for e in report.errors_by_row[3]))

    def test_collision_base_signalée(self):
        row = self._valid_row_draft("REC-BASE-001")
        report = self._report([row], extra_refs={"REC-BASE-001"})
        self.assertIn(2, report.errors_by_row)
        self.assertTrue(any("en base" in e for e in report.errors_by_row[2]))

    def test_direction_inactive_rejetee(self):
        row = self._valid_row_draft()
        row.controlled_department_raw = "OLD"  # département inactif
        report = self._report([row])
        self.assertIn(2, report.errors_by_row)
        self.assertTrue(any("direction" in e.lower() for e in report.errors_by_row[2]))

    def test_reference_trop_longue(self):
        row = self._valid_row_draft()
        row.reference = "R" * 51
        report = self._report([row])
        self.assertIn(2, report.errors_by_row)

    def test_multiple_erreurs_meme_ligne_collectees(self):
        row = RowDraft(
            row_number=2, reference="", source_raw="", priority="",
            description="", due_date_raw=None,
            mission_label="", mission_date_raw=None, controlled_department_raw="",
            department_raw="", observations="", anomalous_dossiers="", deliverables_raw="",
        )
        report = self._report([row])
        # Au moins 5 erreurs (5 champs obligatoires)
        self.assertGreaterEqual(len(report.errors_by_row[2]), 5)

    def test_livrables_split_sur_point_virgule(self):
        row = self._valid_row_draft()
        row.deliverables_raw = "Livrable A ; Livrable B ; Livrable C"
        report = self._report([row])
        self.assertEqual(report.error_count, 0)
        self.assertEqual(len(report.valid_rows[0].deliverables_data), 3)

    def test_livrables_vides_ignores(self):
        row = self._valid_row_draft()
        row.deliverables_raw = "Livrable A ;  ; Livrable C"
        report = self._report([row])
        self.assertEqual(len(report.valid_rows[0].deliverables_data), 2)


# ── Tests create_recommendations_bulk ────────────────────────────────────────


class CreateRecommendationsBulkTest(ImportTestMixin, TestCase):

    def _fake_file(self, name="test.xlsx") -> SimpleUploadedFile:
        xlsx_ct = "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
        return SimpleUploadedFile(name, b"fake-xlsx", content_type=xlsx_ct)

    def _create_bulk(self, rows, file_name="test.xlsx"):
        return create_recommendations_bulk(
            rows=rows,
            performed_by=self.audit_user,
            uploaded_file=self._fake_file(file_name),
            file_name=file_name,
            ip_address="127.0.0.1",
        )

    def test_import_valide_cree_les_recos(self):
        rows = [
            self._valid_row_draft("REC-BULK-001"),
            self._valid_row_draft("REC-BULK-002"),
        ]
        batch = self._create_bulk(rows)
        self.assertEqual(Recommendation.objects.filter(import_batch=batch).count(), 2)

    def test_import_batch_cree_avec_file_name(self):
        rows = [self._valid_row_draft("REC-BATCH-001")]
        batch = self._create_bulk(rows, file_name="mes-recos.xlsx")
        self.assertEqual(batch.file_name, "mes-recos.xlsx")
        self.assertEqual(batch.recommendation_count, 1)
        self.assertEqual(batch.created_by, self.audit_user)

    def test_audit_log_import_cree(self):
        rows = [self._valid_row_draft("REC-LOG-001")]
        batch = self._create_bulk(rows)
        log = AuditLog.objects.filter(
            action=AuditLog.Action.IMPORT,
            content_type="ImportBatch",
            object_id=batch.pk,
        ).first()
        self.assertIsNotNone(log)
        self.assertEqual(log.user, self.audit_user)
        self.assertEqual(log.changes["count"], 1)

    def test_original_due_date_egal_due_date(self):
        future = self._future()
        row = self._valid_row_draft("REC-DATE-OK")
        row.due_date_raw = future
        batch = self._create_bulk([row])
        reco = Recommendation.objects.get(import_batch=batch)
        self.assertEqual(reco.due_date, future)
        self.assertEqual(reco.original_due_date, future)

    def test_livrables_split_et_crees(self):
        row = self._valid_row_draft("REC-LIV-001")
        row.deliverables_raw = "Livrable X ; Livrable Y ; Livrable Z"
        batch = self._create_bulk([row])
        reco = Recommendation.objects.get(import_batch=batch)
        self.assertEqual(reco.deliverables.count(), 3)

    def test_import_tag_reste_null(self):
        batch = self._create_bulk([self._valid_row_draft("REC-TAG-001")])
        reco = Recommendation.objects.get(import_batch=batch)
        self.assertFalse(bool(reco.import_tag))

    def test_statut_draft_apres_import(self):
        batch = self._create_bulk([self._valid_row_draft("REC-DRAFT-001")])
        reco = Recommendation.objects.get(import_batch=batch)
        self.assertEqual(reco.status, Recommendation.Status.DRAFT)

    def test_assigned_null_apres_import(self):
        batch = self._create_bulk([self._valid_row_draft("REC-ASSIGN-001")])
        reco = Recommendation.objects.get(import_batch=batch)
        self.assertIsNone(reco.assigned_dm)
        self.assertIsNone(reco.assigned_etp)

    def test_created_by_est_auditeur_connecte(self):
        batch = self._create_bulk([self._valid_row_draft("REC-CB-001")])
        reco = Recommendation.objects.get(import_batch=batch)
        self.assertEqual(reco.created_by, self.audit_user)

    def test_atomicite_zero_reco_si_erreur(self):
        row_valide = self._valid_row_draft("REC-ATOM-OK")
        row_invalide = RowDraft(
            row_number=3, reference="REC-ATOM-ERR", source_raw="", priority="",
            description="", due_date_raw=self._past(),  # date passée
            mission_label="", mission_date_raw=None, controlled_department_raw="",
            department_raw="", observations="", anomalous_dossiers="", deliverables_raw="",
        )
        initial_count = Recommendation.objects.count()
        with self.assertRaises(ValidationError):
            self._create_bulk([row_valide, row_invalide])
        self.assertEqual(Recommendation.objects.count(), initial_count)

    def test_concurrence_ref_creee_entre_preview_et_confirm(self):
        ref = "REC-CONCUR-001"
        # Créer la reco "entre preview et confirm"
        Recommendation.objects.create(
            reference=ref,
            source=self.source_cobac,
            priority=Recommendation.Priority.HAUTE,
            description="Reco créée en concurrence",
            due_date=self._future(),
            original_due_date=self._future(),
            created_by=self.audit_user,
        )
        row = self._valid_row_draft(ref)
        with self.assertRaises(ValidationError) as ctx:
            self._create_bulk([row])
        self.assertIn("prévisualisation", ctx.exception.message)

    def test_integrity_error_au_save_converti_en_validation_error(self):
        """Course non visible à la re-validation : la contrainte unique fire au
        save() → IntegrityError convertie en ValidationError gracieuse (finding #1)."""
        row = self._valid_row_draft("REC-RACE-001")
        with mock.patch.object(
            Recommendation, "save", side_effect=IntegrityError("duplicate key")
        ):
            with self.assertRaises(ValidationError) as ctx:
                self._create_bulk([row])
        self.assertIn("prévisualisation", ctx.exception.message)

    @override_settings(MEDIA_ROOT=tempfile.mkdtemp())
    def test_fichier_source_supprime_si_rollback(self):
        """Le fichier archivé ne doit pas rester orphelin si la transaction
        rollback (finding #2)."""
        from django.core.files.storage import default_storage

        row_valide = self._valid_row_draft("REC-ORPH-OK")
        # full_clean lève sur la 2e ligne → rollback après écriture du fichier
        with mock.patch.object(
            Recommendation,
            "full_clean",
            side_effect=ValidationError("forçage échec"),
        ):
            with self.assertRaises(ValidationError):
                self._create_bulk([row_valide], file_name="orphelin.xlsx")

        # Aucun fichier orphelin ne doit subsister dans imports/
        if default_storage.exists("imports"):
            _, files = default_storage.listdir("imports")
            self.assertEqual(files, [], f"Fichier(s) orphelin(s) : {files}")

    # Note: le plafond MAX_ROWS est appliqué dans parse_workbook, pas dans
    # create_recommendations_bulk (qui reçoit des RowDraft déjà parsés).
    # Ce cas est couvert par ParseWorkbookTest.test_plafond_max_rows_raise.

    def test_batch_fourni_est_reutilise(self):
        """Mode async : un ImportBatch déjà créé en PENDING est réutilisé,
        pas recréé (non-régression du chemin sans batch=)."""
        batch = ImportBatch.objects.create(
            source_file=self._fake_file(),
            file_name="reuse.xlsx",
            created_by=self.audit_user,
            status=ImportBatch.Status.PENDING,
        )
        rows = [self._valid_row_draft("REC-REUSE-001")]
        returned = create_recommendations_bulk(
            rows=rows,
            performed_by=self.audit_user,
            uploaded_file=None,
            file_name="reuse.xlsx",
            ip_address="127.0.0.1",
            batch=batch,
        )
        self.assertEqual(returned.pk, batch.pk)
        self.assertEqual(ImportBatch.objects.count(), 1)
        self.assertEqual(returned.recommendation_count, 1)


# ── Tests run_recommendations_import_task (Django-Q2 async) ──────────────────


class RunRecommendationsImportTaskTest(ImportTestMixin, TestCase):

    def _make_pending_batch(self, rows_data: list[list], file_name="async.xlsx") -> ImportBatch:
        buf = self._make_xlsx(rows_data)
        buf.name = file_name
        batch = ImportBatch.objects.create(
            source_file=SimpleUploadedFile(
                file_name, buf.read(),
                content_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
            ),
            file_name=file_name,
            created_by=self.audit_user,
            status=ImportBatch.Status.PENDING,
            kind=ImportBatch.Kind.EXCEL,
        )
        return batch

    def test_traitement_reussi_passe_par_processing_puis_done(self):
        batch = self._make_pending_batch([self._valid_row_list("REC-TASK-001")])
        result = run_recommendations_import_task(
            batch_id=str(batch.pk), performed_by_id=self.audit_user.pk, ip_address="127.0.0.1",
        )
        batch.refresh_from_db()
        self.assertEqual(result, "done")
        self.assertEqual(batch.status, ImportBatch.Status.DONE)
        self.assertEqual(batch.recommendation_count, 1)
        self.assertEqual(Recommendation.objects.filter(import_batch=batch).count(), 1)

    def test_notification_emise_sur_succes(self):
        from apps.notifications.models import Notification

        batch = self._make_pending_batch([self._valid_row_list("REC-TASK-NOTIF")])
        run_recommendations_import_task(
            batch_id=str(batch.pk), performed_by_id=self.audit_user.pk,
        )
        self.assertTrue(
            Notification.objects.filter(
                recipient=self.audit_user,
                notification_type=Notification.Type.IMPORT_COMPLETED,
            ).exists()
        )

    def test_retry_sur_batch_deja_done_ne_duplique_pas(self):
        """Idempotence : un retry Django-Q2 après un succès déjà déclaré ne
        recrée aucune recommandation (protection contre le double run)."""
        batch = self._make_pending_batch([self._valid_row_list("REC-TASK-RETRY")])
        run_recommendations_import_task(batch_id=str(batch.pk), performed_by_id=self.audit_user.pk)
        count_after_first_run = Recommendation.objects.filter(import_batch=batch).count()

        result = run_recommendations_import_task(
            batch_id=str(batch.pk), performed_by_id=self.audit_user.pk,
        )
        self.assertIn("skip", result)
        self.assertEqual(
            Recommendation.objects.filter(import_batch=batch).count(), count_after_first_run,
        )

    def test_annulation_empeche_le_traitement(self):
        batch = self._make_pending_batch([self._valid_row_list("REC-TASK-CANCEL")])
        ImportBatch.objects.filter(pk=batch.pk).update(status=ImportBatch.Status.CANCELLED)

        result = run_recommendations_import_task(
            batch_id=str(batch.pk), performed_by_id=self.audit_user.pk,
        )
        self.assertIn("skip", result)
        self.assertEqual(Recommendation.objects.filter(import_batch=batch).count(), 0)

    def test_echec_marque_failed_avec_audit_log_hors_transaction(self):
        """Le rollback de create_recommendations_bulk efface ses propres AuditLog —
        la tâche doit en recréer un hors transaction pour tracer l'échec."""
        row_invalide = RowDraft(
            row_number=2, reference="REC-TASK-FAIL", source_raw="", priority="",
            description="", due_date_raw=self._past(), mission_label="",
            mission_date_raw=None, controlled_department_raw="", department_raw="",
            observations="", anomalous_dossiers="", deliverables_raw="",
        )
        batch = self._make_pending_batch([self._valid_row_list("REC-TASK-VALID-SIDE")])
        with mock.patch(
            "apps.workflow.import_excel.parse_workbook", return_value=[row_invalide],
        ):
            with self.assertRaises(ValidationError):
                run_recommendations_import_task(
                    batch_id=str(batch.pk), performed_by_id=self.audit_user.pk,
                )
        batch.refresh_from_db()
        self.assertEqual(batch.status, ImportBatch.Status.FAILED)
        self.assertTrue(batch.error_message)
        self.assertTrue(
            AuditLog.objects.filter(
                action=AuditLog.Action.SYSTEM,
                content_type="ImportBatch",
                object_id=batch.pk,
            ).exists()
        )
        self.assertEqual(Recommendation.objects.filter(import_batch=batch).count(), 0)

    def test_processed_rows_finalise_meme_sous_25_lignes(self):
        """Le compteur périodique (tous les 25) sautait la finalisation pour un
        lot de moins de 25 lignes — processed_rows devait rester bloqué à 0."""
        batch = self._make_pending_batch([
            self._valid_row_list("REC-TASK-PROG-1"),
            self._valid_row_list("REC-TASK-PROG-2"),
        ])
        run_recommendations_import_task(batch_id=str(batch.pk), performed_by_id=self.audit_user.pk)
        batch.refresh_from_db()
        self.assertEqual(batch.processed_rows, 2)


class ReconcileStaleProcessingBatchesTest(ImportTestMixin, TestCase):
    """Un worker qui crashe entre PENDING→PROCESSING et DONE ne doit pas
    bloquer l'utilisateur indéfiniment (voir _has_active_import_batch)."""

    def _make_batch(self, *, status, updated_delta):
        from django.utils import timezone as tz
        batch = ImportBatch.objects.create(
            file_name="stale.xlsx",
            created_by=self.audit_user,
            status=status,
            kind=ImportBatch.Kind.EXCEL,
        )
        ImportBatch.objects.filter(pk=batch.pk).update(
            updated_at=tz.now() + updated_delta,
        )
        return ImportBatch.objects.get(pk=batch.pk)

    def test_batch_processing_stale_est_marque_failed(self):
        from datetime import timedelta
        from apps.workflow.services import reconcile_stale_processing_batches

        batch = self._make_batch(
            status=ImportBatch.Status.PROCESSING, updated_delta=-timedelta(seconds=700),
        )
        count = reconcile_stale_processing_batches()
        batch.refresh_from_db()
        self.assertEqual(count, 1)
        self.assertEqual(batch.status, ImportBatch.Status.FAILED)
        self.assertTrue(batch.error_message)

    def test_batch_processing_recent_nest_pas_touche(self):
        from datetime import timedelta
        from apps.workflow.services import reconcile_stale_processing_batches

        batch = self._make_batch(
            status=ImportBatch.Status.PROCESSING, updated_delta=-timedelta(seconds=5),
        )
        count = reconcile_stale_processing_batches()
        batch.refresh_from_db()
        self.assertEqual(count, 0)
        self.assertEqual(batch.status, ImportBatch.Status.PROCESSING)

    def test_guard_import_actif_liberee_apres_reconciliation(self):
        """_has_active_import_batch ne bloque plus une fois le batch orphelin réconcilié."""
        from datetime import timedelta
        from apps.workflow.views import _has_active_import_batch

        self._make_batch(
            status=ImportBatch.Status.PROCESSING, updated_delta=-timedelta(seconds=700),
        )
        self.assertFalse(_has_active_import_batch(self.audit_user))


# ── Tests build_import_template ───────────────────────────────────────────────


class BuildImportTemplateTest(ImportTestMixin, TestCase):

    def _get_wb(self):
        return build_import_template()

    def test_onglet_donnees_present(self):
        wb = self._get_wb()
        self.assertIn(DATA_SHEET_NAME, wb.sheetnames)

    def test_12_colonnes_en_tete(self):
        wb = self._get_wb()
        ws = wb[DATA_SHEET_NAME]
        headers = [ws.cell(1, c).value for c in range(1, 13)]
        self.assertEqual(headers, HEADERS)

    def test_onglet_instructions_present(self):
        wb = self._get_wb()
        self.assertIn("Instructions", wb.sheetnames)

    def test_sources_actives_dans_listes(self):
        wb = self._get_wb()
        ws = wb["_Listes"]
        sources_in_sheet = [ws.cell(r, 1).value for r in range(1, 100) if ws.cell(r, 1).value]
        self.assertIn("COBAC", sources_in_sheet)

    def test_source_inactive_absente_des_listes(self):
        wb = self._get_wb()
        ws = wb["_Listes"]
        sources_in_sheet = [ws.cell(r, 1).value for r in range(1, 100) if ws.cell(r, 1).value]
        self.assertNotIn("DEFUNCT", sources_in_sheet)

    def test_directions_actives_dans_listes(self):
        wb = self._get_wb()
        ws = wb["_Listes"]
        depts_in_sheet = [ws.cell(r, 3).value for r in range(1, 100) if ws.cell(r, 3).value]
        self.assertIn("DOP", depts_in_sheet)

    def test_direction_inactive_absente_des_listes(self):
        wb = self._get_wb()
        ws = wb["_Listes"]
        depts_in_sheet = [ws.cell(r, 3).value for r in range(1, 100) if ws.cell(r, 3).value]
        self.assertNotIn("OLD", depts_in_sheet)

    def test_xlsx_serialisable(self):
        wb = self._get_wb()
        buf = io.BytesIO()
        wb.save(buf)
        self.assertGreater(buf.tell(), 0)


# ── Tests RBAC (vues) ─────────────────────────────────────────────────────────


class ImportViewRbacTest(ImportTestMixin, TestCase):

    def _get(self, url, user):
        self.client.force_login(user)
        return self.client.get(url)

    def test_audit_peut_acceder_page_import(self):
        response = self._get(reverse("workflow:recommendation-import"), self.audit_user)
        self.assertEqual(response.status_code, 200)

    def test_dm_bloque_sur_page_import(self):
        response = self._get(reverse("workflow:recommendation-import"), self.dm_user)
        self.assertEqual(response.status_code, 403)

    def test_etp_bloque_sur_page_import(self):
        response = self._get(reverse("workflow:recommendation-import"), self.etp_user)
        self.assertEqual(response.status_code, 403)

    def test_audit_peut_telecharger_template(self):
        response = self._get(reverse("workflow:recommendation-import-template"), self.audit_user)
        self.assertEqual(response.status_code, 200)
        self.assertIn("spreadsheetml", response["Content-Type"])

    def test_dm_bloque_sur_template(self):
        response = self._get(reverse("workflow:recommendation-import-template"), self.dm_user)
        self.assertEqual(response.status_code, 403)


# ── Tests vue POST preview (AC3) ─────────────────────────────────────────────


class ImportPreviewViewTest(ImportTestMixin, TestCase):

    def _post_preview(self, xlsx_buf):
        self.client.force_login(self.audit_user)
        xlsx_buf.seek(0)
        return self.client.post(
            reverse("workflow:recommendation-import"),
            {"import_file": xlsx_buf},
            HTTP_HX_REQUEST="true",
        )

    def test_preview_fichier_valide(self):
        buf = self._make_xlsx([self._valid_row_list("REC-PREV-001")])
        response = self._post_preview(buf)
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "REC-PREV-001")
        # Aucune reco créée
        self.assertEqual(Recommendation.objects.count(), 0)

    def test_preview_pas_de_creation(self):
        buf = self._make_xlsx([self._valid_row_list("REC-NOCREATE-001")])
        self._post_preview(buf)
        self.assertEqual(Recommendation.objects.count(), 0)

    def test_preview_erreur_format_non_excel(self):
        buf = io.BytesIO(b"ce n'est pas un excel")
        buf.name = "test.txt"
        buf.size = 22
        response = self._post_preview(buf)
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "format")


# ── Tests vue POST confirm (AC5, AC6) ────────────────────────────────────────


class ImportConfirmViewTest(ImportTestMixin, TestCase):

    def _make_xlsx_buf(self, row_list):
        buf = self._make_xlsx([row_list])
        buf.name = "confirm_test.xlsx"
        buf.size = buf.getbuffer().nbytes
        return buf

    def _post_confirm(self, xlsx_buf):
        self.client.force_login(self.audit_user)
        xlsx_buf.seek(0)
        return self.client.post(
            reverse("workflow:recommendation-import-confirm"),
            {"import_file": xlsx_buf},
            HTTP_HX_REQUEST="true",
        )

    def test_confirm_valide_cree_recos(self):
        buf = self._make_xlsx_buf(self._valid_row_list("REC-CONF-001"))
        response = self._post_confirm(buf)
        self.assertEqual(response.status_code, 200)
        self.assertEqual(Recommendation.objects.filter(reference="REC-CONF-001").count(), 1)

    def test_confirm_cree_import_batch(self):
        buf = self._make_xlsx_buf(self._valid_row_list("REC-CONF-002"))
        self._post_confirm(buf)
        self.assertEqual(ImportBatch.objects.count(), 1)
        batch = ImportBatch.objects.first()
        self.assertEqual(batch.recommendation_count, 1)
        self.assertEqual(batch.created_by, self.audit_user)

    def test_confirm_ecrit_audit_log_import(self):
        buf = self._make_xlsx_buf(self._valid_row_list("REC-CONF-003"))
        self._post_confirm(buf)
        batch = ImportBatch.objects.first()
        log = AuditLog.objects.filter(action=AuditLog.Action.IMPORT).first()
        self.assertIsNotNone(log)
        self.assertEqual(log.object_id, batch.pk)

    def test_confirm_affiche_ecran_attente(self):
        """La confirmation enqueue la tâche Django-Q2 et affiche l'écran de
        suivi (import_pending.html) — le traitement réel se fait en tâche
        de fond, pas synchrone dans la requête HTTP."""
        buf = self._make_xlsx_buf(self._valid_row_list("REC-CONF-004"))
        response = self._post_confirm(buf)
        self.assertContains(response, "Import en attente")

    def test_filtre_batch_dans_url_succes(self):
        buf = self._make_xlsx_buf(self._valid_row_list("REC-CONF-005"))
        response = self._post_confirm(buf)
        batch = ImportBatch.objects.first()
        self.assertContains(response, str(batch.pk))

    def test_refuse_second_import_pendant_que_le_premier_tourne(self):
        """Garde-fou : un seul import actif à la fois par utilisateur."""
        ImportBatch.objects.create(
            file_name="deja_en_cours.xlsx",
            created_by=self.audit_user,
            status=ImportBatch.Status.PROCESSING,
        )
        buf = self._make_xlsx_buf(self._valid_row_list("REC-CONF-006"))
        response = self._post_confirm(buf)
        self.assertContains(response, "déjà en cours")
        self.assertEqual(Recommendation.objects.filter(reference="REC-CONF-006").count(), 0)

    def test_race_condition_double_soumission_ne_cree_pas_deux_batches(self):
        """Le check-then-act de _has_active_import_batch n'est pas atomique :
        c'est la contrainte DB (uniq_active_import_batch_per_user) qui protège
        réellement contre un double clic ou une requête dupliquée."""
        buf = self._make_xlsx_buf(self._valid_row_list("REC-CONF-RACE"))
        with mock.patch(
            "apps.workflow.views._has_active_import_batch", return_value=False,
        ):
            # Un premier batch existe déjà en PENDING (simulation de la fenêtre
            # de course : le garde a répondu False juste avant sa création).
            ImportBatch.objects.create(
                file_name="course.xlsx",
                created_by=self.audit_user,
                status=ImportBatch.Status.PENDING,
            )
            response = self._post_confirm(buf)

        self.assertContains(response, "déjà en cours")
        self.assertEqual(
            ImportBatch.objects.filter(created_by=self.audit_user).count(), 1,
        )
        self.assertEqual(Recommendation.objects.filter(reference="REC-CONF-RACE").count(), 0)


class ImportBatchStatusViewTest(ImportTestMixin, TestCase):

    def test_batch_pending_affiche_ecran_attente(self):
        batch = ImportBatch.objects.create(
            file_name="s.xlsx", created_by=self.audit_user, status=ImportBatch.Status.PENDING,
        )
        self.client.force_login(self.audit_user)
        response = self.client.get(reverse("workflow:import-batch-status", args=[batch.pk]))
        self.assertContains(response, "Import en attente")

    def test_batch_done_affiche_ecran_succes(self):
        batch = ImportBatch.objects.create(
            file_name="s.xlsx", created_by=self.audit_user, status=ImportBatch.Status.DONE,
        )
        self.client.force_login(self.audit_user)
        response = self.client.get(reverse("workflow:import-batch-status", args=[batch.pk]))
        self.assertContains(response, batch.file_name)

    def test_batch_failed_affiche_ecran_erreur(self):
        batch = ImportBatch.objects.create(
            file_name="s.xlsx", created_by=self.audit_user,
            status=ImportBatch.Status.FAILED, error_message="Fichier corrompu",
        )
        self.client.force_login(self.audit_user)
        response = self.client.get(reverse("workflow:import-batch-status", args=[batch.pk]))
        self.assertContains(response, "Fichier corrompu")

    def test_refuse_acces_a_un_autre_utilisateur(self):
        other = User.objects.create_user(
            username="autre_audit", password="TestPass123!", role=User.Role.AUDIT,
        )
        batch = ImportBatch.objects.create(
            file_name="s.xlsx", created_by=other, status=ImportBatch.Status.PENDING,
        )
        self.client.force_login(self.audit_user)
        response = self.client.get(reverse("workflow:import-batch-status", args=[batch.pk]))
        self.assertEqual(response.status_code, 404)


class ImportBatchCancelViewTest(ImportTestMixin, TestCase):

    def test_annule_batch_pending(self):
        batch = ImportBatch.objects.create(
            file_name="c.xlsx", created_by=self.audit_user, status=ImportBatch.Status.PENDING,
        )
        self.client.force_login(self.audit_user)
        response = self.client.post(reverse("workflow:import-batch-cancel", args=[batch.pk]))
        batch.refresh_from_db()
        self.assertEqual(response.status_code, 200)
        self.assertEqual(batch.status, ImportBatch.Status.CANCELLED)

    def test_refuse_annulation_si_deja_en_cours(self):
        batch = ImportBatch.objects.create(
            file_name="c.xlsx", created_by=self.audit_user, status=ImportBatch.Status.PROCESSING,
        )
        self.client.force_login(self.audit_user)
        response = self.client.post(reverse("workflow:import-batch-cancel", args=[batch.pk]))
        batch.refresh_from_db()
        self.assertEqual(response.status_code, 409)
        self.assertEqual(batch.status, ImportBatch.Status.PROCESSING)
