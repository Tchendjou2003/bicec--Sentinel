"""
Commande de démonstration — Données temporaires pour les dashboards DG et Audit

Injecte un lot de recommandations réparties sur les directions et statuts
réels, plus un historique synthétique de MetricsSnapshot, pour que les
dashboards DG et Audit soient présentables malgré le faible volume de
données réelles actuellement en base. Purement temporaire : --cleanup
retire tout ce qui a été injecté.

Usage :
    docker compose exec web python manage.py seed_dashboard_demo
    docker compose exec web python manage.py seed_dashboard_demo --count 40 --days 90
    docker compose exec web python manage.py seed_dashboard_demo --cleanup
"""
import random
from datetime import timedelta

from django.core.management.base import BaseCommand
from django.utils import timezone

REF_PREFIX = "DEMO-DASH-"


class Command(BaseCommand):
    help = "Injecte des données de démonstration temporaires pour les dashboards DG/Audit"

    def add_arguments(self, parser):
        parser.add_argument(
            "--count", type=int, default=30,
            help="Nombre de recommandations à créer (défaut : 30)",
        )
        parser.add_argument(
            "--days", type=int, default=90,
            help="Profondeur de l'historique MetricsSnapshot en jours (défaut : 90)",
        )
        parser.add_argument(
            "--cleanup", action="store_true",
            help="Supprime les données de démo précédemment injectées au lieu d'en créer",
        )

    def handle(self, *args, **options):
        from django.conf import settings
        from django.core.management.base import CommandError

        # Garde de production : cette commande écrit des données fictives en
        # base (recos, snapshots, notifications) qui n'ont rien à faire dans
        # un environnement réel.
        if not settings.DEBUG:
            raise CommandError(
                "seed_dashboard_demo est une commande de démonstration : elle crée "
                "des données fictives en base. Exécution refusée hors DEBUG."
            )

        if options["cleanup"]:
            self._cleanup(days=options["days"])
        else:
            self._generate(count=options["count"], days=options["days"])

    # ── Nettoyage ────────────────────────────────────────────────────────

    def _cleanup(self, *, days: int):
        from apps.audit.models import HmacSeal
        from apps.dashboards.models import MetricsSnapshot
        from apps.notifications.models import Notification
        from apps.workflow.models import Recommendation

        recos = Recommendation.all_objects.filter(reference__startswith=REF_PREFIX)
        reco_ids = list(recos.values_list("pk", flat=True))
        count_recos = len(reco_ids)

        deleted_notifs, _ = Notification.objects.filter(
            recommendation_id__in=reco_ids,
        ).delete()

        HmacSeal.objects.filter(recommendation__in=recos).delete()
        recos.delete()

        today = timezone.localdate()
        start = today - timedelta(days=days)
        end = today - timedelta(days=1)
        deleted_snapshots, _ = MetricsSnapshot.objects.filter(
            snapshot_date__gte=start, snapshot_date__lte=end,
        ).delete()

        self.stdout.write(self.style.SUCCESS(
            f"Nettoyage terminé : {count_recos} recommandation(s) DEMO supprimée(s), "
            f"{deleted_notifs} notification(s) associée(s) supprimée(s), "
            f"{deleted_snapshots} ligne(s) MetricsSnapshot ({start} → {end}) supprimée(s).\n"
            f"Les entrées AuditLog liées aux recos DEMO restent en place (append-only) — "
            f"comme pour demo_dg_workflow.py, elles ne sont pas purgées."
        ))

    # ── Génération ───────────────────────────────────────────────────────

    def _generate(self, *, count: int, days: int):
        from apps.users.models import Department, User
        from apps.workflow.models import Recommendation, RecommendationSource
        from apps.workflow.services import create_recommendation, flag_overdue_recommendations

        departments = list(Department.objects.filter(is_active=True)[:8])
        if not departments:
            self.stderr.write(self.style.ERROR(
                "Aucun département actif en base — impossible de générer des données de démo."
            ))
            return

        audit_user = (
            User.objects.filter(role=User.Role.AUDIT, is_superuser=True).first()
            or User.objects.filter(role=User.Role.AUDIT).first()
        )
        if not audit_user:
            self.stderr.write(self.style.ERROR("Aucun utilisateur AUDIT trouvé."))
            return

        dm_users = list(User.objects.filter(role=User.Role.DM, is_active=True))
        dg_users = list(User.objects.filter(role=User.Role.DG, is_active=True))
        # Le DG ne voit sur son dashboard que les recos qui lui sont
        # personnellement assignées (assigned_dm=user — apps/workflow/selectors.py
        # get_recommendations_for_user, règle FR34/Story 3.7, pas une vue macro).
        # Sans lui attribuer une part du pool, ses tableaux « Enlisement »/
        # « À risque de bascule » resteraient vides même avec plein de données
        # ailleurs dans la banque. Le DG est donc dupliqué dans le pool pour
        # obtenir une représentation comparable à un DM individuel.
        assignable_users = dm_users + dg_users * 3

        source, _ = RecommendationSource.objects.get_or_create(
            code="DEMO", defaults={"label": "Démo", "is_external": False},
        )

        run_id = timezone.now().strftime("%H%M%S")
        today = timezone.localdate()
        priorities = [choice[0] for choice in Recommendation.Priority.choices]
        plan = self._build_status_plan(count)

        created_pks = []
        extension_candidates = []

        for i, target_status in enumerate(plan):
            dept = departments[i % len(departments)]
            priority = random.choice(priorities)
            ref = f"{REF_PREFIX}{run_id}-{i:03d}"
            due_in_days = random.randint(5, 60)

            rec = create_recommendation(
                data={
                    "reference": ref,
                    "mission_date": today - timedelta(days=random.randint(10, 400)),
                    "mission_label": f"Mission démo — {dept.name}",
                    "controlled_department": dept,
                    "observations": "Constat généré pour la démonstration du dashboard.",
                    "anomalous_dossiers": "",
                    "description": (
                        "Recommandation de démonstration — donnée temporaire injectée "
                        "pour présentation, à supprimer via --cleanup."
                    ),
                    "source": source,
                    "priority": priority,
                    "department": dept,
                    "due_date": today + timedelta(days=due_in_days),
                },
                deliverables_data=[],
                performed_by=audit_user,
            )
            created_pks.append(rec.pk)

            # Les états ci-dessous sont posés directement en base via .update(),
            # sans rejouer chaque transition FSM — même technique que l'import
            # historique (Story 6.8) pour construire des états variés sans
            # dérouler tout le workflow. Le champ status FSM est protected=True
            # contre l'assignation Python directe, pas contre un UPDATE SQL brut.
            updates = {}
            assigned_dm = random.choice(assignable_users) if assignable_users else None

            if target_status == Recommendation.Status.CLOSED_RESOLVED:
                closed_days_ago = random.randint(1, max(days, 1))
                updates.update(
                    status=target_status,
                    assigned_dm=assigned_dm,
                    closed_at=timezone.now() - timedelta(days=closed_days_ago),
                    closed_by=audit_user,
                )
            elif target_status in (
                Recommendation.Status.ASSIGNED,
                Recommendation.Status.IN_PROGRESS,
                Recommendation.Status.PENDING_DM_REVIEW,
                Recommendation.Status.PENDING_AUDIT_REVIEW,
            ):
                updates.update(status=target_status, assigned_dm=assigned_dm)
                # Une partie des dossiers actifs est délibérément en retard,
                # pour peupler les buckets d'ancienneté (0-30j, 30-90j, 90j+).
                if random.random() < 0.4:
                    overdue_days = random.choice([10, 45, 120])
                    updates["due_date"] = today - timedelta(days=overdue_days)
                    updates["original_due_date"] = today - timedelta(days=overdue_days)
                if assigned_dm is not None:
                    extension_candidates.append(rec.pk)

            if updates:
                Recommendation.all_objects.filter(pk=rec.pk).update(**updates)

        # Recalcule is_overdue comme le ferait le cron nocturne réel — le champ
        # est calculé, pas dérivé à la lecture, donc les due_date backdatées
        # ci-dessus ne suffisent pas seules.
        flag_overdue_recommendations()

        extensions_created = self._create_demo_extensions(extension_candidates[:3])
        stuck_via_extensions = self._create_stuck_via_extensions(
            extension_candidates[3:5], audit_user,
        )
        stuck_via_stale_critical = self._create_stuck_via_stale_critical(
            created_pks, count=2,
        )

        # Les reports approuvés ci-dessus déplacent due_date dans le futur —
        # recalcule is_overdue une seconde fois pour rester cohérent avant
        # de capturer le snapshot du jour.
        flag_overdue_recommendations()

        # Snapshot du jour, capturé sur l'état réel désormais peuplé par la démo.
        from apps.dashboards.services import capture_daily_snapshot
        capture_daily_snapshot()

        snapshots_written = self._backfill_snapshot_history(days=days)

        self.stdout.write(self.style.SUCCESS(
            f"\n{len(created_pks)} recommandation(s) DEMO créée(s) (préfixe {REF_PREFIX}{run_id}).\n"
            f"{extensions_created} demande(s) de report DEMO créée(s) (en attente).\n"
            f"{stuck_via_extensions} reco(s) « enlisée(s) » via 2 reports approuvés.\n"
            f"{stuck_via_stale_critical} reco(s) « enlisée(s) » via priorité critique sans activité 30j+.\n"
            f"{snapshots_written} ligne(s) d'historique MetricsSnapshot injectée(s) sur {days} jours.\n\n"
            f"Pour tout supprimer après la présentation :\n"
            f"  python manage.py seed_dashboard_demo --cleanup --days {days}\n"
        ))

    def _build_status_plan(self, count: int) -> list:
        """Distribution pondérée des statuts — ni tout vert, ni tout rouge."""
        from apps.workflow.models import Recommendation

        weighted = (
            [Recommendation.Status.CLOSED_RESOLVED] * 4
            + [Recommendation.Status.ASSIGNED] * 2
            + [Recommendation.Status.IN_PROGRESS] * 2
            + [Recommendation.Status.PENDING_DM_REVIEW] * 1
            + [Recommendation.Status.PENDING_AUDIT_REVIEW] * 1
        )
        return [random.choice(weighted) for _ in range(count)]

    def _create_demo_extensions(self, candidate_pks: list) -> int:
        """Crée quelques demandes de report PENDING pour peupler la file
        Audit « reports en attente ». Best-effort : une candidate qui ne
        remplit plus les conditions du service (guard RBAC/FSM) est ignorée."""
        from apps.workflow.models import Recommendation
        from apps.workflow.services import request_extension

        created = 0
        today = timezone.localdate()
        for pk in candidate_pks:
            rec = Recommendation.all_objects.select_related("assigned_dm").get(pk=pk)
            if rec.assigned_dm is None:
                continue
            try:
                request_extension(
                    recommendation=rec,
                    requested_date=today + timedelta(days=random.randint(30, 60)),
                    reason="Délai supplémentaire nécessaire — donnée de démonstration.",
                    performed_by=rec.assigned_dm,
                )
                created += 1
            except Exception:
                continue
        return created

    def _create_stuck_via_extensions(self, candidate_pks: list, audit_user) -> int:
        """Force le critère « ≥2 reports approuvés » du tableau Enlisement en
        demandant puis approuvant deux reports successifs sur chaque candidate.
        Best-effort : ignore une candidate qui ne remplit plus les guards du
        service (par exemple une demande PENDING déjà en cours)."""
        from apps.workflow.models import Recommendation
        from apps.workflow.services import approve_extension, request_extension

        created = 0
        for pk in candidate_pks:
            try:
                rec = Recommendation.all_objects.select_related("assigned_dm").get(pk=pk)
                if rec.assigned_dm is None:
                    continue

                # La date demandée doit être postérieure à due_date COURANT
                # (guard du service) — donc relative à rec.due_date, pas à
                # aujourd'hui, sinon la demande est rejetée pour les dossiers
                # dont l'échéance est déjà loin dans le futur.
                ext1 = request_extension(
                    recommendation=rec,
                    requested_date=rec.due_date + timedelta(days=20),
                    reason="Première demande — donnée de démonstration.",
                    performed_by=rec.assigned_dm,
                )
                approve_extension(extension_request=ext1, performed_by=audit_user)

                rec = Recommendation.all_objects.get(pk=pk)
                ext2 = request_extension(
                    recommendation=rec,
                    requested_date=rec.due_date + timedelta(days=20),
                    reason="Seconde demande — donnée de démonstration.",
                    performed_by=rec.assigned_dm,
                )
                approve_extension(extension_request=ext2, performed_by=audit_user)
                created += 1
            except Exception:
                continue
        return created

    def _create_stuck_via_stale_critical(self, pks: list, *, count: int) -> int:
        """Force le second critère du tableau Enlisement : priorité CRITIQUE
        sans activité depuis 30 jours. `updated_at` est auto_now=True, donc
        seul un UPDATE SQL direct (hors save()) permet de le reculer dans le
        passé — même technique que le backdating de due_date plus haut."""
        from apps.workflow.models import Recommendation

        candidates = [
            pk for pk in pks
            if Recommendation.all_objects.filter(
                pk=pk,
            ).exclude(status=Recommendation.Status.CLOSED_RESOLVED).exists()
        ][:count]

        updated = 0
        for pk in candidates:
            Recommendation.all_objects.filter(pk=pk).update(
                priority=Recommendation.Priority.CRITIQUE,
                updated_at=timezone.now() - timedelta(days=35),
            )
            updated += 1
        return updated

    def _backfill_snapshot_history(self, *, days: int) -> int:
        """
        Écrit un historique MetricsSnapshot synthétique pour les `days` jours
        précédant aujourd'hui, en interpolant entre un état de départ dégradé
        et l'état réel d'aujourd'hui (capturé juste avant par
        capture_daily_snapshot()). Il est impossible de recalculer un état
        passé réel depuis les données actuelles — ces valeurs forment une
        courbe plausible pour la présentation, pas une reconstitution
        historique exacte.
        """
        from apps.dashboards import selectors
        from apps.dashboards.models import MetricsSnapshot

        today = timezone.localdate()
        groups, _, _ = selectors._get_breakdown_groups()
        scopes = [None] + list(groups)

        numeric_fields = [
            "total_actives", "overdue", "closed_total", "closed_cumulative",
            "critique_open", "overdue_0_30", "overdue_30_90", "overdue_90_plus",
            "on_time_closed_strict", "on_time_closed_tolerant",
            "regulatory_stock_weighted", "regulatory_aging_index",
            "submissions_total", "rejected_by_dm", "rejected_by_audit",
        ]
        # Multiplicateurs appliqués à la valeur d'aujourd'hui pour obtenir le
        # point de départ, days plus tôt — raconte une amélioration progressive.
        start_multipliers = {
            "total_actives": 0.8, "overdue": 1.8, "closed_total": 0.3,
            "closed_cumulative": 0.2, "critique_open": 1.5,
            "overdue_0_30": 1.3, "overdue_30_90": 1.6, "overdue_90_plus": 2.0,
            "on_time_closed_strict": 0.5, "on_time_closed_tolerant": 0.5,
            "regulatory_stock_weighted": 1.4, "regulatory_aging_index": 1.8,
            "submissions_total": 0.4, "rejected_by_dm": 1.5, "rejected_by_audit": 1.5,
        }

        written = 0
        for scope in scopes:
            today_snapshot = MetricsSnapshot.objects.filter(
                snapshot_date=today, department=scope,
            ).first()
            if today_snapshot is None:
                continue

            end_values = {f: getattr(today_snapshot, f) for f in numeric_fields}
            start_values = {
                f: max(0, int(end_values[f] * start_multipliers[f]) + (1 if start_multipliers[f] > 1 else 0))
                for f in numeric_fields
            }

            for offset in range(days, 0, -1):
                d = today - timedelta(days=offset)
                ratio = 1 - (offset / days)  # 0 → point de départ, ~1 → veille d'aujourd'hui
                defaults = {}
                for field in numeric_fields:
                    start_val = start_values[field]
                    end_val = end_values[field]
                    interpolated = start_val + (end_val - start_val) * ratio
                    jitter = random.randint(-1, 1)
                    defaults[field] = max(0, round(interpolated) + jitter)

                MetricsSnapshot.objects.update_or_create(
                    snapshot_date=d, department=scope, defaults=defaults,
                )
                written += 1

        return written
