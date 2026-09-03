"""
Champs de formulaire partagés — affichage organisationnel (Users App)

Centralise les libellés et regroupements (« optgroups ») des sélecteurs
d'utilisateurs et de départements, avec leur contexte organisationnel
(type d'unité, code), SANS toucher aux ``__str__`` des modèles — ceux-ci
sont consommés par l'admin Django, les logs d'audit (append-only) et les
exports, et ne doivent pas changer de format.

Conventions d'affichage (décision produit) :
    - Option utilisateur : « NOM Prénom (username) — CODE_UNITÉ »
    - Groupe par unité   : « [TYPE] Nom de l'unité (CODE) »
    - Option département : « Nom (CODE) »
    - Groupe par type    : « [TYPE] Libellé du type »

``OrgUnitType`` est un catalogue dynamique (l'Audit Admin peut créer de
nouveaux types) : aucun comportement ne doit dépendre d'un code de type
en dur — seul ``level`` sert à ordonner les groupes.
"""
from django import forms
from django.forms.models import ModelChoiceIterator
from django.utils.translation import gettext_lazy as _


# ── Libellés ──────────────────────────────────────────────────────────


def user_org_label(user) -> str:
    """« NOM Prénom (username) — CODE_UNITÉ » (fallbacks progressifs)."""
    name = f"{(user.last_name or '').upper()} {user.first_name or ''}".strip()
    label = f"{name} ({user.username})" if name else user.username
    if user.department_id and user.department.code:
        label = f"{label} — {user.department.code}"
    return label


def department_option_label(dept) -> str:
    """« Nom (CODE) » pour une option de département."""
    return f"{dept.name} ({dept.code})" if dept.code else dept.name


def department_group_label(dept) -> str:
    """« [TYPE] Nom de l'unité (CODE) » pour un en-tête d'optgroup."""
    if dept is None:
        return str(_("Sans rattachement"))
    label = department_option_label(dept)
    if dept.type_id and dept.type.code:
        label = f"[{dept.type.code}] {label}"
    return label


# ── Itérateurs groupés (optgroups) ────────────────────────────────────


class GroupedByDepartmentIterator(ModelChoiceIterator):
    """
    Options utilisateur groupées par unité d'affectation.

    Les groupes sont ordonnés par niveau hiérarchique du type d'unité
    (``OrgUnitType.level``) puis par nom ; l'ordre des membres suit
    celui du queryset (nom, prénom). Nécessite un queryset avec
    ``select_related("department__type")`` pour éviter le N+1.
    """

    def __iter__(self):
        if self.field.empty_label is not None:
            yield ("", self.field.empty_label)
        groups: dict = {}
        for obj in self.queryset:
            dept = obj.department if obj.department_id else None
            key = dept.pk if dept is not None else None
            if key not in groups:
                groups[key] = (dept, [])
            groups[key][1].append(self.choice(obj))

        def sort_key(key):
            dept = groups[key][0]
            if dept is None:
                return (9999, "")
            level = dept.type.level if dept.type_id else 9998
            return (level, dept.name.lower())

        for key in sorted(groups, key=sort_key):
            dept, choices = groups[key]
            yield (department_group_label(dept), choices)


class GroupedByTypeIterator(ModelChoiceIterator):
    """
    Options département groupées par type d'unité organisationnelle.

    Groupes ordonnés par ``OrgUnitType.level`` (Direction → Agence) ;
    l'ordre des options suit celui du queryset. Nécessite un queryset
    avec ``select_related("type")``.
    """

    def __iter__(self):
        if self.field.empty_label is not None:
            yield ("", self.field.empty_label)
        groups: dict = {}
        for dept in self.queryset:
            key = dept.type_id
            if key not in groups:
                groups[key] = (dept.type if key else None, [])
            groups[key][1].append(self.choice(dept))

        def sort_key(key):
            unit_type = groups[key][0]
            if unit_type is None:
                return (9999, "")
            return (unit_type.level, unit_type.name.lower())

        for key in sorted(groups, key=sort_key):
            unit_type, choices = groups[key]
            if unit_type is not None:
                label = f"[{unit_type.code}] {unit_type.name}"
            else:
                label = str(_("Autres"))
            yield (label, choices)


# ── Champs ────────────────────────────────────────────────────────────


class OrgScopedUserChoiceField(forms.ModelChoiceField):
    """
    ``ModelChoiceField`` d'utilisateurs avec libellé organisationnel.

    ``group_by_department=True`` active les optgroups par unité
    d'affectation (à réserver aux listes longues, ex. délégation ETP).
    La validation reste celle du queryset — l'affichage seul change.
    """

    def __init__(self, *args, group_by_department: bool = False, **kwargs):
        # L'itérateur doit être posé AVANT super().__init__ : le setter de
        # queryset fige widget.choices avec l'itérateur courant.
        if group_by_department:
            self.iterator = GroupedByDepartmentIterator
        super().__init__(*args, **kwargs)

    def label_from_instance(self, obj):
        return user_org_label(obj)
