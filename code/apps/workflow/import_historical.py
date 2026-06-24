"""
Workflow App — Import Historique de recommandations clôturées (Story 6.8)

Permet à l'Audit d'importer dans Sentinel des recommandations déjà clôturées issues
des archives physiques/numériques, avec leurs preuves associées (ZIP optionnel).

Les recos arrivent avec status=CLOSED_RESOLVED, import_tag="IMPORTED" et apparaissent
dans l'onglet « Backlog Historique » (filtre import_status="historical").

Architecture découplée :
    build_historical_import_template()      → Workbook            (template Excel)
    parse_historical_workbook()             → list[HistoricalRow] (parse Excel)
    parse_zip_members()                     → list[ZipFileEntry]  (parse ZIP)
    validate_historical_rows()              → HistoricalImportReport (validation pure)
    create_historical_recommendations()     → ImportBatch          (cœur atomique)

Distinctions clés vs import_excel.py (Story 6.5) :
  - Status cible : CLOSED_RESOLVED (non DRAFT)
  - Dates passées autorisées (recos historiques)
  - import_tag = "IMPORTED" systématiquement
  - Preuves ZIP associées via EvidenceSubmission/EvidenceFile
  - HMAC seal systématique (métadonnées + preuves si présentes)
  - created_at forcé via queryset.update() (contourne auto_now_add)
"""
from __future__ import annotations

import hashlib
import io
import os
import zipfile
from dataclasses import dataclass, field
from datetime import date, datetime, timezone as dt_tz
from typing import Any

from django.core.exceptions import ValidationError
from django.core.files.base import ContentFile
from django.db import transaction
from django.db.models import Q
from django.utils import timezone
from django.utils.translation import gettext_lazy as _

from apps.audit.models import AuditLog
from apps.audit.services import generate_recommendation_seal
from apps.users.models import Department

from .models import (
    EvidenceFile,
    EvidenceSubmission,
    ImportBatch,
    Recommendation,
    RecommendationSource,
)
from .validators import (
    compute_sha256,
    detect_mime_type,
    validate_file_size,
    validate_magic_bytes,
)


# ── Constantes ────────────────────────────────────────────────────────────────

MAX_ROWS = 500
MAX_ZIP_DECOMPRESSED_MB = 100
MAX_FILE_SIZE_MB = 10
DATA_SHEET_NAME = "Données"
INSTRUCTIONS_SHEET_NAME = "Instructions"

HEADERS = [
    "Référence",               # 0
    "Source",                  # 1
    "Criticité",               # 2
    "Description",             # 3
    "Date cible originale",    # 4 — original_due_date
    "Date de clôture",         # 5 — closed_at (obligatoire)
    "Date de création",        # 6 — created_at_original (obligatoire)
    "Titre (mission)",         # 7 — mission_label (optionnel)
    "Direction contrôlée",     # 8 — controlled_department (optionnel)
    "Direction concernée",     # 9 — department (optionnel)
    "Observations",            # 10 — optionnel
]

COL_REFERENCE     = 0
COL_SOURCE        = 1
COL_PRIORITY      = 2
COL_DESCRIPTION   = 3
COL_DUE_DATE      = 4
COL_CLOSED_AT     = 5
COL_CREATED_AT    = 6
COL_MISSION_LABEL = 7
COL_CTRL_DEPT     = 8
COL_DEPT          = 9
COL_OBSERVATIONS  = 10

_VALID_PRIORITIES = set(Recommendation.Priority.values)


# ── Structures de données ──────────────────────────────────────────────────────


@dataclass
class HistoricalRow:
    """Ligne normalisée extraite du fichier Excel historique."""
    row_number: int
    reference: str
    source_raw: str
    priority: str
    description: str
    due_date_raw: Any
    closed_at_raw: Any
    created_at_original_raw: Any
    mission_label: str
    controlled_department_raw: str
    department_raw: str
    observations: str


@dataclass
class ValidHistoricalRow:
    """Ligne validée, prête pour la création Recommendation."""
    data: dict           # champs Recommendation sauf closed_at, created_at
    closed_at: date
    created_at_original: date


@dataclass
class ZipFileEntry:
    """Fichier extrait du ZIP, déjà nettoyé et validé."""
    name: str            # nom safe (basename uniquement — Zip Slip)
    data: bytes
    ref_hint: str = ""   # nom du dossier parent immédiat (matching par dossier)


@dataclass
class HistoricalImportReport:
    """Résultat de la validation Excel + ZIP."""
    total: int
    valid_rows: list[ValidHistoricalRow] = field(default_factory=list)
    errors_by_row: dict[int, list[str]] = field(default_factory=dict)
    zip_total: int = 0
    zip_matched: int = 0
    zip_unmatched: list[str] = field(default_factory=list)
    zip_format_error: str = ""

    @property
    def valid_count(self) -> int:
        return len(self.valid_rows)

    @property
    def error_count(self) -> int:
        return len(self.errors_by_row)

    @property
    def zip_unmatched_count(self) -> int:
        return len(self.zip_unmatched)

    def error_type_summary(self) -> str:
        counts: dict[str, int] = {}
        for errors in self.errors_by_row.values():
            for err in errors:
                lo = err.lower()
                if "obligatoire manquant" in lo:
                    key = "champ(s) obligatoire(s) manquant(s)"
                elif "en doublon" in lo:
                    key = "doublon(s) intra-fichier"
                elif "déjà présente en base" in lo:
                    key = "référence(s) existante(s) en base"
                elif "illisible" in lo:
                    key = "date(s) illisible(s)"
                elif "dans le futur" in lo:
                    key = "date(s) de clôture future(s)"
                elif "postérieure à" in lo:
                    key = "incohérence(s) de dates"
                elif "source" in lo:
                    key = "source(s) inconnue(s)/inactive(s)"
                elif "direction" in lo:
                    key = "direction(s) inexistante(s)/inactive(s)"
                elif "criticité" in lo:
                    key = "criticité(s) invalide(s)"
                else:
                    key = "autre(s) erreur(s)"
                counts[key] = counts.get(key, 0) + 1
        return " ; ".join(f"{v} {k}" for k, v in counts.items())


# ── Génération du modèle Excel historique ─────────────────────────────────────


def build_historical_import_template():
    """
    Génère le modèle Excel d'import historique.

    Dynamique : sources et directions actives chargées au clic.

    Returns:
        openpyxl.Workbook prêt à être sérialisé en .xlsx.
    """
    import openpyxl
    from openpyxl.styles import Alignment, Font, PatternFill
    from openpyxl.utils import get_column_letter
    from openpyxl.worksheet.datavalidation import DataValidation

    wb = openpyxl.Workbook()

    ws_lists = wb.active
    ws_lists.title = "_Listes"
    ws_lists.sheet_state = "hidden"

    sources = list(RecommendationSource.objects.filter(is_active=True).order_by("code"))
    departments = list(Department.objects.filter(is_active=True, is_system=False).order_by("code"))
    priorities = list(Recommendation.Priority.values)

    for i, src in enumerate(sources, start=1):
        ws_lists.cell(row=i, column=1, value=src.code)
    for i, prio in enumerate(priorities, start=1):
        ws_lists.cell(row=i, column=2, value=prio)
    for i, dept in enumerate(departments, start=1):
        ws_lists.cell(row=i, column=3, value=dept.code)

    ws_data = wb.create_sheet(title=DATA_SHEET_NAME, index=0)

    header_font = Font(bold=True, color="FFFFFF")
    header_fill = PatternFill("solid", fgColor="1A4E6E")  # bleu foncé — historique
    header_align = Alignment(horizontal="center", vertical="center", wrap_text=True)

    col_widths = [22, 16, 14, 44, 20, 20, 20, 32, 26, 26, 44]
    for col_idx, (header, width) in enumerate(zip(HEADERS, col_widths), start=1):
        cell = ws_data.cell(row=1, column=col_idx, value=header)
        cell.font = header_font
        cell.fill = header_fill
        cell.alignment = header_align
        ws_data.column_dimensions[get_column_letter(col_idx)].width = width
    ws_data.row_dimensions[1].height = 22
    ws_data.freeze_panes = "A2"

    date_cols = [COL_DUE_DATE + 1, COL_CLOSED_AT + 1, COL_CREATED_AT + 1]
    for col_num in date_cols:
        col_letter = get_column_letter(col_num)
        for row in range(2, MAX_ROWS + 2):
            ws_data.cell(row=row, column=col_num).number_format = "YYYY-MM-DD"

    n_src = max(len(sources), 1)
    n_dept = max(len(departments), 1)
    n_prio = len(priorities)

    def _dv(col_idx: int, formula: str, error_msg: str, error_title: str):
        from openpyxl.worksheet.datavalidation import DataValidation
        dv = DataValidation(
            type="list",
            formula1=formula,
            allow_blank=True,
            showErrorMessage=True,
            error=error_msg,
            errorTitle=error_title,
        )
        col = get_column_letter(col_idx)
        dv.sqref = f"{col}2:{col}{MAX_ROWS + 1}"
        return dv

    ws_data.add_data_validation(_dv(
        COL_SOURCE + 1,
        f"'_Listes'!$A$1:$A${n_src}",
        "Sélectionnez une source dans la liste.",
        "Source invalide",
    ))
    ws_data.add_data_validation(_dv(
        COL_PRIORITY + 1,
        f"'_Listes'!$B$1:$B${n_prio}",
        "Valeurs acceptées : CRITIQUE, HAUTE, MOYENNE, FAIBLE.",
        "Criticité invalide",
    ))
    ws_data.add_data_validation(_dv(
        COL_CTRL_DEPT + 1,
        f"'_Listes'!$C$1:$C${n_dept}",
        "Sélectionnez une direction.",
        "Direction invalide",
    ))
    ws_data.add_data_validation(_dv(
        COL_DEPT + 1,
        f"'_Listes'!$C$1:$C${n_dept}",
        "Sélectionnez une direction.",
        "Direction invalide",
    ))

    ws_inst = wb.create_sheet(title=INSTRUCTIONS_SHEET_NAME)
    ws_inst.column_dimensions["A"].width = 70
    ws_inst.column_dimensions["B"].width = 50

    title_font = Font(bold=True, size=13, color="1A4E6E")
    section_font = Font(bold=True, size=11)
    header2_font = Font(bold=True)

    row = 1
    ws_inst.cell(row=row, column=1,
                 value="Guide d'utilisation — Modèle d'import historique Sentinel").font = title_font
    row += 2

    ws_inst.cell(row=row, column=1, value="COLONNES OBLIGATOIRES (*)").font = section_font
    row += 1
    for h in ["Référence", "Source", "Criticité", "Description",
              "Date cible originale", "Date de clôture", "Date de création"]:
        ws_inst.cell(row=row, column=1, value=f"  • {h}")
        row += 1
    row += 1

    ws_inst.cell(row=row, column=1, value="CONVENTION ZIP DES PREUVES").font = section_font
    row += 1
    ws_inst.cell(row=row, column=1, value="  MÉTHODE RECOMMANDÉE — un dossier par référence :").font = header2_font
    row += 1
    ws_inst.cell(row=row, column=1, value="    Créez un dossier nommé exactement comme la référence.")
    row += 1
    ws_inst.cell(row=row, column=1, value="    Déposez les fichiers de preuve à l'intérieur (noms libres).")
    row += 1
    ws_inst.cell(row=row, column=1, value="    Zippez tous les dossiers → téléversez l'archive.")
    row += 1
    ws_inst.cell(row=row, column=1,
                 value="    Exemple de structure ZIP :")
    row += 1
    ws_inst.cell(row=row, column=1, value="      RECO-2022-001/rapport-audit.pdf")
    row += 1
    ws_inst.cell(row=row, column=1, value="      RECO-2022-001/pv-recette.pdf")
    row += 1
    ws_inst.cell(row=row, column=1, value="      RECO-2022-002/contrat.docx")
    row += 2
    ws_inst.cell(row=row, column=1, value="  MÉTHODE ALTERNATIVE — préfixe dans le nom du fichier :").font = header2_font
    row += 1
    ws_inst.cell(row=row, column=1,
                 value="    Nommez chaque fichier : {REFERENCE}_{description}.{ext}")
    row += 1
    ws_inst.cell(row=row, column=1,
                 value="    Exemple : RECO-2022-001_rapport.pdf")
    row += 2
    ws_inst.cell(row=row, column=1,
                 value="  • Fichiers non associés à une référence → ignorés (avertissement, non bloquant)")
    row += 2

    ws_inst.cell(row=row, column=1, value="SOURCES VALIDES").font = section_font
    row += 1
    ws_inst.cell(row=row, column=1, value="Code").font = header2_font
    ws_inst.cell(row=row, column=2, value="Libellé").font = header2_font
    row += 1
    for src in sources:
        ws_inst.cell(row=row, column=1, value=src.code)
        ws_inst.cell(row=row, column=2, value=src.label)
        row += 1
    row += 1

    ws_inst.cell(row=row, column=1, value="CRITICITÉS AUTORISÉES").font = section_font
    row += 1
    prio_labels = {
        "CRITIQUE": "Risque critique",
        "HAUTE": "Risque élevé",
        "MOYENNE": "Risque modéré",
        "FAIBLE": "Risque faible",
    }
    for prio in priorities:
        ws_inst.cell(row=row, column=1, value=prio)
        ws_inst.cell(row=row, column=2, value=prio_labels.get(prio, ""))
        row += 1
    row += 1

    ws_inst.cell(row=row, column=1, value="DIRECTIONS VALIDES").font = section_font
    row += 1
    ws_inst.cell(row=row, column=1, value="Code").font = header2_font
    ws_inst.cell(row=row, column=2, value="Nom").font = header2_font
    row += 1
    for dept in departments:
        ws_inst.cell(row=row, column=1, value=dept.code)
        ws_inst.cell(row=row, column=2, value=dept.name)
        row += 1
    row += 1

    ws_inst.cell(row=row, column=1, value="RÈGLES DE SAISIE").font = section_font
    row += 1
    rules = [
        "Format de date : ISO AAAA-MM-JJ (ex : 2021-06-15). Utilisez le type Date Excel OU ce format texte.",
        "Les dates peuvent être dans le passé (recommandations historiques).",
        "Date de clôture doit être antérieure ou égale à aujourd'hui.",
        "Date de création doit être antérieure ou égale à la Date cible originale.",
        "Référence : max 50 caractères, unique dans le système et dans le fichier.",
        "Observations : mentionnez le nom du responsable historique si connu.",
        f"Maximum {MAX_ROWS} recommandations par import.",
    ]
    for rule in rules:
        ws_inst.cell(row=row, column=1, value=f"  • {rule}")
        row += 1

    return wb


# ── Helpers internes ──────────────────────────────────────────────────────────


def _normalize_str(value: Any) -> str:
    if value is None:
        return ""
    return str(value).strip()


def _parse_date_cell(value: Any) -> date | str | None:
    if isinstance(value, datetime):
        return value.date()
    if isinstance(value, date):
        return value
    if value is None:
        return None
    raw = str(value).strip()
    if not raw:
        return None
    try:
        return date.fromisoformat(raw)
    except (ValueError, TypeError):
        return raw


def _get_existing_references(rows: list[HistoricalRow]) -> set[str]:
    file_refs = [r.reference for r in rows if r.reference]
    if not file_refs:
        return set()
    q = Q()
    for ref in file_refs:
        q |= Q(reference__iexact=ref)
    return set(
        Recommendation.all_objects.filter(q).values_list("reference", flat=True)
    )


# ── Parser Excel ──────────────────────────────────────────────────────────────


def parse_historical_workbook(file) -> list[HistoricalRow]:
    """
    Lit le fichier Excel historique et retourne les HistoricalRow normalisées.

    Raises:
        ValidationError: Erreur de format (XLSM, >6 Mo, corrompu, onglet manquant, >MAX_ROWS).
    """
    import openpyxl

    validate_file_size(file)
    validate_magic_bytes(file, original_filename=getattr(file, "name", ""))

    file.seek(0)
    try:
        wb = openpyxl.load_workbook(file, read_only=True, data_only=True)
    except Exception:
        raise ValidationError(
            _("Format de fichier non reconnu — déposez le modèle historique .xlsx Sentinel.")
        )

    if DATA_SHEET_NAME not in wb.sheetnames:
        raise ValidationError(
            _(
                f'L\'onglet « {DATA_SHEET_NAME} » est introuvable. '
                "Utilisez le modèle historique fourni par Sentinel."
            )
        )

    ws = wb[DATA_SHEET_NAME]
    rows: list[HistoricalRow] = []

    for row_idx, row_cells in enumerate(ws.iter_rows(min_row=2, values_only=True), start=2):
        if all(cell is None or str(cell).strip() == "" for cell in row_cells):
            continue

        if len(rows) >= MAX_ROWS:
            raise ValidationError(
                _(
                    f"Le modèle accepte au maximum {MAX_ROWS} recommandations par import historique. "
                    "Votre fichier en contient davantage. Découpez en plusieurs fichiers."
                )
            )

        def _col(idx: int) -> Any:
            try:
                return row_cells[idx]
            except IndexError:
                return None

        rows.append(HistoricalRow(
            row_number=row_idx,
            reference=_normalize_str(_col(COL_REFERENCE)),
            source_raw=_normalize_str(_col(COL_SOURCE)),
            priority=_normalize_str(_col(COL_PRIORITY)).upper(),
            description=_normalize_str(_col(COL_DESCRIPTION)),
            due_date_raw=_parse_date_cell(_col(COL_DUE_DATE)),
            closed_at_raw=_parse_date_cell(_col(COL_CLOSED_AT)),
            created_at_original_raw=_parse_date_cell(_col(COL_CREATED_AT)),
            mission_label=_normalize_str(_col(COL_MISSION_LABEL)),
            controlled_department_raw=_normalize_str(_col(COL_CTRL_DEPT)),
            department_raw=_normalize_str(_col(COL_DEPT)),
            observations=_normalize_str(_col(COL_OBSERVATIONS)),
        ))

    wb.close()
    return rows


# ── Parser ZIP ────────────────────────────────────────────────────────────────


def parse_zip_members(zip_file) -> list[ZipFileEntry]:
    """
    Valide et extrait les fichiers de l'archive ZIP.

    Gardes de sécurité :
    - Taille max conteneur : 100 Mo (validate_file_size)
    - Zip Bomb : total décompressé ≤ MAX_ZIP_DECOMPRESSED_MB
    - Zip Slip : os.path.basename() sur chaque nom de fichier
    - Chaque fichier extrait : validate_magic_bytes + validate_file_size (10 Mo max)

    Raises:
        ValidationError: ZIP invalide, trop grand, ou fichier interne interdit.
    """
    validate_file_size(zip_file, max_size_mb=100)

    zip_file.seek(0)
    if not zipfile.is_zipfile(zip_file):
        raise ValidationError(_("Le fichier n'est pas une archive ZIP valide."))

    zip_file.seek(0)
    try:
        with zipfile.ZipFile(zip_file, "r") as zf:
            # Garde Zip Bomb — somme des tailles décompressées
            total_uncompressed = sum(zi.file_size for zi in zf.infolist())
            if total_uncompressed > MAX_ZIP_DECOMPRESSED_MB * 1024 * 1024:
                raise ValidationError(
                    _(
                        f"L'archive ZIP contient plus de {MAX_ZIP_DECOMPRESSED_MB} Mo de données "
                        "décompressées. Découpez le lot en plusieurs archives."
                    )
                )

            entries: list[ZipFileEntry] = []
            for member in zf.infolist():
                if member.is_dir():
                    continue
                # Garde Zip Slip — basename uniquement pour le nom de fichier
                safe_name = os.path.basename(member.filename)
                if not safe_name:
                    continue

                # Extraire le dossier parent immédiat pour le matching par dossiers.
                # Utilisé uniquement comme clé de lookup (jamais pour reconstruire un
                # chemin). Les composants de traversée (. et ..) sont exclus défensivement.
                parts = member.filename.replace("\\", "/").rstrip("/").split("/")
                raw_parent = parts[-2] if len(parts) >= 2 else ""
                parent_dir = raw_parent if raw_parent not in ("", ".", "..") else ""

                raw_bytes = zf.read(member.filename)

                # Valider chaque fichier extrait (magic bytes + taille)
                buf = io.BytesIO(raw_bytes)
                buf.name = safe_name
                try:
                    validate_file_size(buf, max_size_mb=MAX_FILE_SIZE_MB)
                    buf.seek(0)
                    validate_magic_bytes(buf, original_filename=safe_name)
                except ValidationError as exc:
                    msg = exc.message if hasattr(exc, "message") else str(exc)
                    raise ValidationError(
                        _(f"Fichier « {safe_name} » invalide dans le ZIP : {msg}")
                    )

                entries.append(ZipFileEntry(name=safe_name, data=raw_bytes, ref_hint=parent_dir))

    except zipfile.BadZipFile:
        raise ValidationError(_("L'archive ZIP est corrompue ou invalide."))

    return entries


def _match_zip_to_refs(
    entries: list[ZipFileEntry], valid_refs: list[str]
) -> tuple[dict[str, list[ZipFileEntry]], list[str]]:
    """
    Mappe les fichiers ZIP aux références validées (insensible à la casse).

    Deux méthodes supportées, par ordre de priorité :

    1. **Par dossier (recommandée)** : le fichier se trouve dans un sous-dossier
       dont le nom correspond exactement à une référence.
       Exemple : ``RECO-2022-001/rapport.pdf`` → reco ``RECO-2022-001``

    2. **Par préfixe (fallback)** : le nom du fichier commence par ``{reference}_``.
       Exemple : ``RECO-2022-001_rapport.pdf`` → reco ``RECO-2022-001``

    Returns:
        (matched_by_ref, unmatched_names)
    """
    matched: dict[str, list[ZipFileEntry]] = {ref: [] for ref in valid_refs}
    unmatched: list[str] = []

    ref_lower_to_ref = {ref.lower(): ref for ref in valid_refs}

    for entry in entries:
        found = False

        # Priorité 1 : dossier parent = référence (UX dossiers — aucun renommage requis)
        if entry.ref_hint:
            ref_key = entry.ref_hint.lower()
            if ref_key in ref_lower_to_ref:
                matched[ref_lower_to_ref[ref_key]].append(entry)
                found = True

        # Priorité 2 : préfixe dans le nom du fichier (convention historique fallback)
        if not found:
            name_lower = entry.name.lower()
            for ref_lower, ref in ref_lower_to_ref.items():
                if name_lower.startswith(ref_lower + "_"):
                    matched[ref].append(entry)
                    found = True
                    break

        if not found:
            unmatched.append(entry.name)

    return matched, unmatched


# ── Validation (pure, sans écriture) ─────────────────────────────────────────


def validate_historical_rows(
    rows: list[HistoricalRow],
    zip_entries: list[ZipFileEntry] | None = None,
) -> HistoricalImportReport:
    """
    Valide les lignes Excel et construit le rapport de preview.

    Différences vs validate_rows (Story 6.5) :
    - Dates passées autorisées (recos historiques)
    - closed_at obligatoire et doit être ≤ aujourd'hui
    - created_at_original obligatoire et ≤ closed_at
    - Pas de champ `due_date` futur obligatoire (original_due_date peut être passé)

    Args:
        rows: Lignes parsées par parse_historical_workbook.
        zip_entries: Fichiers ZIP extraits (optionnel).

    Returns:
        HistoricalImportReport avec valid_rows et errors_by_row.
    """
    today = timezone.now().date()
    report = HistoricalImportReport(total=len(rows))

    src_by_key: dict[str, RecommendationSource] = {}
    for s in RecommendationSource.objects.filter(is_active=True).order_by("code"):
        src_by_key.setdefault(s.code.lower(), s)
        src_by_key.setdefault(s.label.lower(), s)
    dept_by_key: dict[str, Department] = {}
    for d in Department.objects.filter(is_active=True, is_system=False).order_by("code"):
        dept_by_key.setdefault(d.code.lower(), d)
        dept_by_key.setdefault(d.name.lower(), d)

    existing_refs_lower = {r.lower() for r in _get_existing_references(rows)}

    ref_to_lines: dict[str, list[int]] = {}
    for row in rows:
        if row.reference:
            ref_to_lines.setdefault(row.reference.lower(), []).append(row.row_number)
    duplicate_lines = {r: ls for r, ls in ref_to_lines.items() if len(ls) > 1}

    for row in rows:
        errors: list[str] = []
        data: dict = {}
        closed_at_date: date | None = None
        created_at_date: date | None = None

        # ── Référence ──────────────────────────────────────────────────────────
        if not row.reference:
            errors.append("Référence : champ obligatoire manquant.")
        elif len(row.reference) > 50:
            errors.append(f"Référence : dépasse 50 caractères ({len(row.reference)} car.).")
        else:
            ref_lower = row.reference.lower()
            if ref_lower in duplicate_lines:
                other = [ln for ln in duplicate_lines[ref_lower] if ln != row.row_number]
                if other:
                    errors.append(f"Référence « {row.reference} » en doublon avec la ligne {other[0]}.")
            if ref_lower in existing_refs_lower:
                errors.append(f"Référence « {row.reference} » déjà présente en base.")
            data["reference"] = row.reference

        # ── Source ─────────────────────────────────────────────────────────────
        if not row.source_raw:
            errors.append("Source : champ obligatoire manquant.")
        else:
            source = src_by_key.get(row.source_raw.lower())
            if source is None:
                errors.append(f"Source « {row.source_raw} » inconnue ou inactive.")
            else:
                data["source"] = source

        # ── Criticité ─────────────────────────────────────────────────────────
        if not row.priority:
            errors.append("Criticité : champ obligatoire manquant.")
        elif row.priority not in _VALID_PRIORITIES:
            errors.append(f"Criticité « {row.priority} » invalide. Valeurs : CRITIQUE, HAUTE, MOYENNE, FAIBLE.")
        else:
            data["priority"] = row.priority

        # ── Description ───────────────────────────────────────────────────────
        if not row.description:
            errors.append("Description : champ obligatoire manquant.")
        else:
            data["description"] = row.description

        # ── Date cible originale (passée autorisée) ───────────────────────────
        if row.due_date_raw is None or row.due_date_raw == "":
            errors.append("Date cible originale : champ obligatoire manquant.")
        elif isinstance(row.due_date_raw, str):
            errors.append(f"Date cible originale « {row.due_date_raw} » illisible. Format : AAAA-MM-JJ.")
        else:
            data["due_date"] = row.due_date_raw
            data["original_due_date"] = row.due_date_raw

        # ── Date de clôture (obligatoire, doit être ≤ aujourd'hui) ───────────
        if row.closed_at_raw is None or row.closed_at_raw == "":
            errors.append("Date de clôture : champ obligatoire manquant.")
        elif isinstance(row.closed_at_raw, str):
            errors.append(f"Date de clôture « {row.closed_at_raw} » illisible. Format : AAAA-MM-JJ.")
        else:
            if row.closed_at_raw > today:
                errors.append(f"Date de clôture {row.closed_at_raw.isoformat()} dans le futur.")
            else:
                closed_at_date = row.closed_at_raw

        # ── Date de création (obligatoire, doit être ≤ closed_at) ────────────
        if row.created_at_original_raw is None or row.created_at_original_raw == "":
            errors.append("Date de création : champ obligatoire manquant.")
        elif isinstance(row.created_at_original_raw, str):
            errors.append(f"Date de création « {row.created_at_original_raw} » illisible. Format : AAAA-MM-JJ.")
        else:
            if closed_at_date and row.created_at_original_raw > closed_at_date:
                errors.append(
                    f"Date de création {row.created_at_original_raw.isoformat()} "
                    f"postérieure à la date de clôture {closed_at_date.isoformat()}."
                )
            else:
                created_at_date = row.created_at_original_raw

        # ── Champs optionnels ─────────────────────────────────────────────────
        if row.mission_label:
            data["mission_label"] = row.mission_label

        if row.controlled_department_raw:
            dept_ctrl = dept_by_key.get(row.controlled_department_raw.lower())
            if dept_ctrl is None:
                errors.append(f"Direction contrôlée « {row.controlled_department_raw} » inexistante ou inactive.")
            else:
                data["controlled_department"] = dept_ctrl

        if row.department_raw:
            dept = dept_by_key.get(row.department_raw.lower())
            if dept is None:
                errors.append(f"Direction concernée « {row.department_raw} » inexistante ou inactive.")
            else:
                data["department"] = dept

        if row.observations:
            data["observations"] = row.observations

        # ── Résultat ──────────────────────────────────────────────────────────
        if errors:
            report.errors_by_row[row.row_number] = errors
        elif closed_at_date and created_at_date:
            report.valid_rows.append(ValidHistoricalRow(
                data=data,
                closed_at=closed_at_date,
                created_at_original=created_at_date,
            ))
        else:
            # Dates manquantes déjà capturées en erreur
            report.errors_by_row[row.row_number] = errors or ["Dates obligatoires manquantes."]

    # ── Matching ZIP ──────────────────────────────────────────────────────────
    if zip_entries:
        valid_refs = [vr.data["reference"] for vr in report.valid_rows if "reference" in vr.data]
        _, unmatched = _match_zip_to_refs(zip_entries, valid_refs)
        report.zip_total = len(zip_entries)
        matched_count = report.zip_total - len(unmatched)
        report.zip_matched = matched_count
        report.zip_unmatched = unmatched

    return report


# ── Création atomique ─────────────────────────────────────────────────────────


def create_historical_recommendations(
    *,
    rows: list[HistoricalRow],
    zip_entries: list[ZipFileEntry] | None = None,
    performed_by,
    uploaded_file,
    file_name: str,
    provenance: str = "",
    ip_address: str | None = None,
) -> ImportBatch:
    """
    Crée atomiquement toutes les recommandations historiques et leurs preuves.

    Re-valide DANS la transaction pour couvrir la concurrence.
    Tout-ou-rien : toute erreur déclenche un rollback complet.

    Pour chaque reco :
    1. Crée la Recommendation (CLOSED_RESOLVED + IMPORTED)
    2. Force created_at via queryset.update() (contourne auto_now_add)
    3. Crée EvidenceSubmission (ACCEPTED) + EvidenceFile pour les preuves ZIP matchées
    4. Génère le sceau HMAC (allow_empty_files=True — protège les métadonnées)

    Args:
        rows: Lignes parsées par parse_historical_workbook.
        zip_entries: Fichiers ZIP extraits (optionnel).
        performed_by: Auditeur connecté (created_by, closed_by, sealed_by).
        uploaded_file: Fichier Excel Django (archivé dans ImportBatch).
        file_name: Nom original du fichier Excel.
        provenance: Origine des données (ex: "Archives papier numérisées").
        ip_address: IP client pour AuditLog.

    Returns:
        ImportBatch: Le lot créé.

    Raises:
        ValidationError: Si re-validation échoue (concurrence, données invalides).
    """
    batch_file = None
    try:
        with transaction.atomic():
            # Re-validation dans la transaction (concurrence)
            current_refs = _get_existing_references(rows)
            report = validate_historical_rows(rows, zip_entries)

            if report.errors_by_row:
                error_lines = ", ".join(str(ln) for ln in sorted(report.errors_by_row.keys()))
                raise ValidationError(
                    _(
                        f"La validation a échoué sur {report.error_count} ligne(s) "
                        f"(lignes {error_lines}). Corrigez le fichier et réessayez."
                    )
                )

            # Préparer le matching ZIP
            valid_refs = [vr.data["reference"] for vr in report.valid_rows if "reference" in vr.data]
            matched_by_ref: dict[str, list[ZipFileEntry]] = {ref: [] for ref in valid_refs}
            unmatched: list[str] = []
            if zip_entries:
                matched_by_ref, unmatched = _match_zip_to_refs(zip_entries, valid_refs)

            batch = ImportBatch.objects.create(
                source_file=uploaded_file,
                file_name=file_name,
                created_by=performed_by,
                recommendation_count=len(report.valid_rows),
            )
            batch_file = batch.source_file

            for vrow in report.valid_rows:
                row_data = dict(vrow.data)
                row_data["status"] = Recommendation.Status.CLOSED_RESOLVED
                row_data["import_tag"] = "IMPORTED"
                row_data["import_batch"] = batch
                row_data["created_by"] = performed_by
                row_data["closed_by"] = performed_by
                row_data["closed_at"] = timezone.make_aware(
                    datetime.combine(vrow.closed_at, datetime.min.time())
                )
                # assigned_dm = None (null=True, blank=True — pas de migration nécessaire)

                reco = Recommendation(**row_data)
                reco.full_clean(exclude=["status"])
                reco.save()

                # Forcer la date de création historique (contourne auto_now_add=True).
                # Stocké à midi UTC pour éviter tout décalage DST/fuseau (heure locale
                # pourrait décaler minuit UTC en J-1, faussant .date() en lecture).
                Recommendation.objects.filter(pk=reco.pk).update(
                    created_at=datetime.combine(
                        vrow.created_at_original,
                        datetime.min.time().replace(hour=12),
                    ).replace(tzinfo=dt_tz.utc)
                )

                # Preuves ZIP
                proof_entries = matched_by_ref.get(vrow.data.get("reference", ""), [])
                if proof_entries:
                    sub = EvidenceSubmission.objects.create(
                        recommendation=reco,
                        status=EvidenceSubmission.SubmissionStatus.ACCEPTED,
                        submitted_by=performed_by,
                        comment="Import historique — archives numériques",
                    )
                    for entry in proof_entries:
                        content_file = ContentFile(entry.data, name=entry.name)
                        sha256 = hashlib.sha256(entry.data).hexdigest()
                        mime = detect_mime_type(content_file, original_filename=entry.name)
                        EvidenceFile.objects.create(
                            submission=sub,
                            file=content_file,
                            original_filename=entry.name,
                            file_size=len(entry.data),
                            mime_type=mime,
                            sha256_hash=sha256,
                            uploaded_by=performed_by,
                            tag=EvidenceFile.Tag.JUSTIFICATIF,
                        )

                # Scellement HMAC systématique (métadonnées + preuves si présentes)
                generate_recommendation_seal(
                    recommendation=reco,
                    sealed_by=performed_by,
                    allow_empty_files=True,
                )

                AuditLog.objects.create(
                    action=AuditLog.Action.CREATE,
                    user=performed_by,
                    content_type="Recommendation",
                    object_id=reco.pk,
                    changes={
                        "reference": reco.reference,
                        "source": reco.source.code if reco.source else None,
                        "status": reco.status,
                        "import_tag": reco.import_tag,
                        "import_batch": str(batch.pk),
                        "proof_files": len(proof_entries),
                    },
                    description=(
                        f"Import historique — recommandation clôturée {reco.reference} "
                        f"(lot {batch.pk})"
                    ),
                    ip_address=ip_address,
                )

            prov_label = provenance or "Non précisée"
            AuditLog.objects.create(
                action=AuditLog.Action.IMPORT,
                user=performed_by,
                content_type="ImportBatch",
                object_id=batch.pk,
                changes={
                    "file": file_name,
                    "count": len(report.valid_rows),
                    "batch": str(batch.pk),
                    "provenance": prov_label,
                    "zip_total": report.zip_total,
                    "zip_matched": report.zip_matched,
                    "zip_unmatched": len(unmatched),
                },
                description=(
                    f"Import historique (Provenance : {prov_label}) — "
                    f"{len(report.valid_rows)} recommandations clôturées. "
                    f"ZIP : {report.zip_matched} fichiers associés, "
                    f"{len(unmatched)} ignorés."
                ),
                ip_address=ip_address,
            )

        return batch

    except Exception:
        if batch_file:
            batch_file.delete(save=False)
        raise
