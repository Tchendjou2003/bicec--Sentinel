"""
Users App — Signal handlers d'authentification (HackSoft Styleguide)

Thin wrappers : extraient les données HTTP du signal et délèguent
la logique métier aux services de l'app audit.
"""
from django.contrib.auth.signals import (
    user_logged_in,
    user_logged_out,
    user_login_failed,
)
from django.dispatch import receiver


@receiver(user_logged_in)
def on_user_logged_in(sender, request, user, **kwargs):
    from apps.audit.services import log_user_login
    log_user_login(
        user=user,
        ip_address=request.META.get("REMOTE_ADDR") if request else None,
    )


@receiver(user_logged_out)
def on_user_logged_out(sender, request, user, **kwargs):
    if user is None or not getattr(user, "is_authenticated", False):
        return
    from apps.audit.services import log_user_logout
    log_user_logout(
        user=user,
        ip_address=request.META.get("REMOTE_ADDR") if request else None,
    )


@receiver(user_login_failed)
def on_user_login_failed(sender, credentials, request, **kwargs):
    from apps.audit.services import log_login_failed
    log_login_failed(
        username=credentials.get("username", "?"),
        ip_address=request.META.get("REMOTE_ADDR") if request else None,
    )
