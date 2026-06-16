"""
Commande de bootstrap du premier administrateur Sentinel (Story 7.2).

Remplace l'usage de Django Admin pour amorcer les comptes administrateurs :

    python manage.py bootstrap_admin --username sentinel1 --email s1@bicec.cm

- 1er appel  → Administrateur Sentinel « Checker » (membre du groupe approbateur).
- 2e appel   → Administrateur Sentinel « Maker » (hors groupe).
- 3e appel+  → refusé : le bootstrap est terminé, basculer sur le flux Maker/Checker.

Le mot de passe peut être passé via --password (non interactif) ou saisi de
façon masquée si omis.
"""
from getpass import getpass

from django.contrib.auth.password_validation import validate_password
from django.core.exceptions import PermissionDenied, ValidationError
from django.core.management.base import BaseCommand, CommandError

from apps.users.services import bootstrap_create_admin


class Command(BaseCommand):
    help = (
        "Crée un administrateur Sentinel en mode bootstrap (1er = Checker, "
        "2e = Maker, verrou au-delà). Évite Django Admin pour l'amorçage."
    )

    def add_arguments(self, parser):
        parser.add_argument("--username", required=True, help="Identifiant de connexion.")
        parser.add_argument("--email", required=True, help="E-mail professionnel.")
        parser.add_argument(
            "--password",
            help="Mot de passe initial. Si omis, saisie masquée interactive.",
        )
        parser.add_argument("--first-name", default="", help="Prénom (optionnel).")
        parser.add_argument("--last-name", default="", help="Nom (optionnel).")

    def handle(self, *args, **options):
        username = options["username"].strip()
        email = options["email"].strip()
        password = options.get("password")

        if not password:
            password = getpass("Mot de passe initial (min. 8 caractères) : ")
            confirm = getpass("Confirmer le mot de passe : ")
            if password != confirm:
                raise CommandError("Les mots de passe ne correspondent pas.")
        if len(password) < 8:
            raise CommandError("Le mot de passe doit faire au moins 8 caractères.")
        try:
            validate_password(password)
        except ValidationError as exc:
            raise CommandError("; ".join(exc.messages))

        try:
            user = bootstrap_create_admin(
                username=username,
                email=email,
                password=password,
                first_name=options.get("first_name", ""),
                last_name=options.get("last_name", ""),
                performed_by=None,
            )
        except PermissionDenied as exc:
            raise CommandError(str(exc))
        except ValidationError as exc:
            raise CommandError("; ".join(exc.messages))

        is_checker = user.groups.filter(name="Administrateurs Sentinel").exists()
        role_label = "Checker (approbateur)" if is_checker else "Maker"
        self.stdout.write(self.style.SUCCESS(
            f"✓ Administrateur Sentinel créé : {user.username} — rôle {role_label}, "
            f"rattaché à « {user.department.name} »."
        ))
        if is_checker:
            self.stdout.write(
                "  → Ce compte peut valider les demandes de provisioning. "
                "Créez un 2e administrateur (Maker) pour soumettre les demandes."
            )
        else:
            self.stdout.write(
                "  → Bootstrap terminé. Les comptes suivants passent par le flux "
                "Maker/Checker dans l'application."
            )
