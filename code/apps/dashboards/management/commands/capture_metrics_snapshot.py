"""
Commande de management : capture manuelle d'un snapshot métriques.

Usage :
    python manage.py capture_metrics_snapshot
    python manage.py capture_metrics_snapshot --date 2026-06-01
"""

import datetime

from django.core.management.base import BaseCommand, CommandError

from apps.dashboards.services import capture_daily_snapshot


class Command(BaseCommand):
    help = "Capture un snapshot MetricsSnapshot pour la date donnée (défaut : aujourd'hui)."

    def add_arguments(self, parser):
        parser.add_argument(
            "--date",
            type=str,
            default=None,
            help="Date au format YYYY-MM-DD (défaut : aujourd'hui).",
        )

    def handle(self, *args, **options):
        raw_date = options["date"]
        if raw_date:
            try:
                snapshot_date = datetime.date.fromisoformat(raw_date)
            except ValueError:
                raise CommandError(
                    f"Date invalide : '{raw_date}'. Format attendu : YYYY-MM-DD."
                )
        else:
            snapshot_date = None

        result = capture_daily_snapshot(snapshot_date=snapshot_date)
        self.stdout.write(
            self.style.SUCCESS(
                f"Snapshot capturé pour {result['date']} : "
                f"{result['created']} créés, {result['updated']} mis à jour."
            )
        )
