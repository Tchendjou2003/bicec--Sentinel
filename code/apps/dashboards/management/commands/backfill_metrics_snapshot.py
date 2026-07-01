"""
Commande de management : backfill des snapshots métriques sur ~90 jours.

Les volumes (actives, clôturées) sont exacts depuis created_at/closed_at.
Les buckets d'aging historiques sont APPROXIMATIFS : is_overdue est le flag
actuel (recalculé par le cron) et non la valeur passée — les recos passées
en retard puis clôturées entre-temps ne sont plus comptées dans les buckets.
Cette limite est documentée dans la section "Reddition" du dashboard.

Usage :
    python manage.py backfill_metrics_snapshot
    python manage.py backfill_metrics_snapshot --days 60
    python manage.py backfill_metrics_snapshot --from 2026-01-01 --to 2026-03-31
"""

import datetime

from django.core.management.base import BaseCommand, CommandError
from django.utils import timezone

from apps.dashboards.services import capture_daily_snapshot


class Command(BaseCommand):
    help = "Reconstitue les snapshots métriques sur une fenêtre passée (défaut : 90 jours)."

    def add_arguments(self, parser):
        parser.add_argument(
            "--days",
            type=int,
            default=90,
            help="Nombre de jours en arrière depuis aujourd'hui (défaut : 90).",
        )
        parser.add_argument(
            "--from",
            dest="date_from",
            type=str,
            default=None,
            help="Date de début YYYY-MM-DD (remplace --days si fourni avec --to).",
        )
        parser.add_argument(
            "--to",
            dest="date_to",
            type=str,
            default=None,
            help="Date de fin YYYY-MM-DD (incluse, défaut : aujourd'hui).",
        )

    def handle(self, *args, **options):
        today = timezone.localdate()

        if options["date_from"]:
            try:
                date_from = datetime.date.fromisoformat(options["date_from"])
            except ValueError:
                raise CommandError(
                    f"Date de début invalide : '{options['date_from']}'."
                )
        else:
            date_from = today - datetime.timedelta(days=options["days"])

        if options["date_to"]:
            try:
                date_to = datetime.date.fromisoformat(options["date_to"])
            except ValueError:
                raise CommandError(f"Date de fin invalide : '{options['date_to']}'.")
        else:
            date_to = today

        if date_from > date_to:
            raise CommandError(
                "La date de début doit être antérieure à la date de fin."
            )

        current = date_from
        total_created = total_updated = 0
        days_processed = 0

        while current <= date_to:
            result = capture_daily_snapshot(snapshot_date=current)
            total_created += result["created"]
            total_updated += result["updated"]
            days_processed += 1
            current += datetime.timedelta(days=1)

        self.stdout.write(
            self.style.SUCCESS(
                f"Backfill terminé : {days_processed} jours traités "
                f"({date_from} → {date_to}). "
                f"{total_created} snapshots créés, {total_updated} mis à jour.\n"
                "Note : buckets d'aging historiques approximatifs (is_overdue = état actuel)."
            )
        )
