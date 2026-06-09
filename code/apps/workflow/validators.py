"""
Workflow App — Validators de fichiers (Story 3.3)

Validation sécurisée des pièces justificatives :
- Inspection des magic bytes (pas de confiance sur l'extension)
- Protection contre les Zip Bombs lors de l'inspection XLSM (NFR-SEC-04)
- Limite de taille à 6 Mo par fichier (NFR-SCA-01)
- Calcul de hash SHA-256 pour intégrité
- Détection du type MIME réel

Spécifications couvertes :
    - AC1 : Formats autorisés PDF, DOCX, XLSX, JPEG, PNG, CSV, MSG, EML — refus XLSM
    - NFR-SEC-04 : Validation par contenu, jamais par extension seule
    - PRD v2 FR15 : "validation sécurisée adaptative"
"""
import hashlib
import zipfile

from django.core.exceptions import ValidationError
from django.utils.translation import gettext_lazy as _


# ── Signatures Magic Bytes ────────────────────────────────────────────

_MAGIC_PDF = b"%PDF"
_MAGIC_ZIP = b"PK\x03\x04"          # DOCX, XLSX, XLSM partagent cette signature
_MAGIC_JPEG = b"\xff\xd8\xff"
_MAGIC_PNG = b"\x89PNG\r\n\x1a\n"
_MAGIC_OLE2 = b"\xd0\xcf\x11\xe0\xa1\xb1\x1a\xe1"  # MSG (Outlook), DOC, XLS legacy

_XLSM_MARKER = b"vnd.ms-excel.sheet.macroEnabled"

_MAX_CONTENT_TYPES_SIZE = 64 * 1024  # 64 KB — protection Zip Bomb lors de l'inspection

# En-têtes email standards pour la détection heuristique EML
_EML_HEADER_MARKERS = (b"From:", b"Subject:", b"Date:", b"MIME-Version:", b"Message-ID:")
_EML_SCAN_SIZE = 4096  # Octets à lire pour la détection EML

# Extensions autorisées pour les formats sans magic bytes fiables
_CSV_EXTENSIONS = {".csv"}
_EML_EXTENSIONS = {".eml"}


def validate_magic_bytes(file, *, original_filename: str = "") -> None:
    """
    Vérifie que le fichier correspond à un format autorisé via ses magic bytes.

    Formats autorisés : PDF, DOCX, XLSX, JPEG, PNG, CSV, MSG, EML.
    Formats rejetés : XLSM (macros Excel), tout autre type.

    CSV et EML n'ont pas de magic bytes fiables. On combine extension +
    heuristique de contenu ("validation sécurisée adaptative" — PRD v2 FR15).

    Args:
        file: Fichier Django (InMemoryUploadedFile ou TemporaryUploadedFile).
        original_filename: Nom original du fichier pour déduire l'extension.
            Requis pour la validation CSV et EML.

    Raises:
        ValidationError: Si le type est interdit ou non reconnu.
    """
    file.seek(0)
    header = file.read(8)
    file.seek(0)

    if header[:4] == _MAGIC_PDF:
        return  # PDF valide

    if header[:3] == _MAGIC_JPEG:
        return  # JPEG valide

    if header[:8] == _MAGIC_PNG:
        return  # PNG valide

    if header[:4] == _MAGIC_ZIP:
        _validate_zip_not_xlsm(file)
        return  # DOCX ou XLSX valide

    if header[:8] == _MAGIC_OLE2:
        return  # MSG (Outlook) valide — format OLE2 Compound File

    # Formats sans magic bytes : validation par extension + heuristique de contenu
    ext = _get_extension(original_filename or getattr(file, "name", ""))

    if ext in _CSV_EXTENSIONS:
        _validate_csv_content(file)
        return  # CSV valide

    if ext in _EML_EXTENSIONS:
        _validate_eml_content(file)
        return  # EML valide

    raise ValidationError(
        _(
            "Format de fichier non autorisé. Seuls PDF, DOCX, XLSX, CSV, "
            "MSG, EML, JPEG et PNG sont acceptés. "
            "Vérifiez que votre fichier n'est pas corrompu."
        )
    )


def _get_extension(filename: str) -> str:
    """Extrait l'extension normalisée (minuscule, avec le point)."""
    if "." in filename:
        return "." + filename.rsplit(".", 1)[-1].lower()
    return ""


def _validate_csv_content(file) -> None:
    """
    Valide qu'un fichier CSV est du texte valide (pas de bytes nuls).

    Heuristique : lit les 4096 premiers octets et vérifie l'absence de bytes nuls
    (indicateur d'un fichier binaire déguisé en CSV).

    Raises:
        ValidationError: Si le fichier contient des bytes nuls.
    """
    file.seek(0)
    sample = file.read(_EML_SCAN_SIZE)
    file.seek(0)

    if b"\x00" in sample:
        raise ValidationError(
            _("Le fichier CSV semble corrompu ou contient des données binaires.")
        )


def _validate_eml_content(file) -> None:
    """
    Valide qu'un fichier EML contient des en-têtes email standards.

    Heuristique : vérifie la présence d'au moins 2 en-têtes email
    reconnus dans les 4096 premiers octets.

    Raises:
        ValidationError: Si aucun en-tête email n'est détecté.
    """
    file.seek(0)
    sample = file.read(_EML_SCAN_SIZE)
    file.seek(0)

    matches = sum(1 for marker in _EML_HEADER_MARKERS if marker in sample)
    if matches < 2:
        raise ValidationError(
            _(
                "Le fichier EML ne contient pas d'en-têtes email valides. "
                "Vérifiez qu'il s'agit bien d'un email exporté."
            )
        )


def _validate_zip_not_xlsm(file) -> None:
    """
    Ouvre l'archive ZIP et inspecte [Content_Types].xml pour détecter les macros XLSM.

    Protection : lecture limitée à _MAX_CONTENT_TYPES_SIZE pour éviter les Zip Bombs.

    Raises:
        ValidationError: Si le fichier est un XLSM (macros) ou un ZIP invalide/corrompu.
    """
    file.seek(0)
    try:
        with zipfile.ZipFile(file, "r") as zf:
            if "[Content_Types].xml" not in zf.namelist():
                raise ValidationError(
                    _("Le fichier ZIP ne contient pas de structure Office valide.")
                )
            with zf.open("[Content_Types].xml") as ct:
                content = ct.read(_MAX_CONTENT_TYPES_SIZE)
            if _XLSM_MARKER in content:
                raise ValidationError(
                    _(
                        "Les fichiers Excel avec macros (.xlsm) ne sont pas autorisés "
                        "pour des raisons de sécurité. Enregistrez votre fichier en .xlsx."
                    )
                )
    except zipfile.BadZipFile:
        raise ValidationError(
            _("Le fichier est corrompu ou n'est pas une archive Office valide.")
        )
    finally:
        file.seek(0)


def validate_file_size(file, max_size_mb: int = 6) -> None:
    """
    Vérifie que la taille du fichier ne dépasse pas max_size_mb.

    Args:
        file: Fichier Django.
        max_size_mb: Limite en mégaoctets (défaut 6 Mo — NFR-SCA-01 / FR15).

    Raises:
        ValidationError: Si le fichier est trop volumineux.
    """
    max_bytes = max_size_mb * 1024 * 1024
    if file.size > max_bytes:
        raise ValidationError(
            _(
                f"Le fichier dépasse la taille maximale autorisée de {max_size_mb} Mo. "
                f"Taille actuelle : {file.size / (1024 * 1024):.1f} Mo."
            )
        )


def compute_sha256(file) -> str:
    """
    Calcule le hash SHA-256 du fichier par chunks pour économiser la mémoire.

    Args:
        file: Fichier Django (positionné au début).

    Returns:
        str: Hash SHA-256 en hexadécimal (64 caractères).
    """
    hasher = hashlib.sha256()
    file.seek(0)
    for chunk in iter(lambda: file.read(8192), b""):
        hasher.update(chunk)
    file.seek(0)
    return hasher.hexdigest()


def detect_mime_type(file, *, original_filename: str = "") -> str:
    """
    Détecte le type MIME depuis les magic bytes (pas l'extension).

    Pour les formats sans magic bytes (CSV, EML), l'extension est utilisée
    en complément de l'heuristique de contenu.

    Args:
        file: Fichier Django (positionné au début après validation).
        original_filename: Nom original pour déduire l'extension.

    Returns:
        str: Type MIME (ex: "application/pdf", "image/jpeg").
    """
    file.seek(0)
    header = file.read(8)
    file.seek(0)

    if header[:4] == _MAGIC_PDF:
        return "application/pdf"
    if header[:3] == _MAGIC_JPEG:
        return "image/jpeg"
    if header[:8] == _MAGIC_PNG:
        return "image/png"
    if header[:8] == _MAGIC_OLE2:
        return "application/vnd.ms-outlook"
    if header[:4] == _MAGIC_ZIP:
        # Distinguer DOCX vs XLSX à partir du Content_Types
        try:
            with zipfile.ZipFile(file, "r") as zf:
                if "[Content_Types].xml" in zf.namelist():
                    with zf.open("[Content_Types].xml") as ct:
                        content = ct.read(_MAX_CONTENT_TYPES_SIZE)
                    if b"wordprocessingml" in content:
                        return "application/vnd.openxmlformats-officedocument.wordprocessingml.document"
                    if b"spreadsheetml" in content:
                        return "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
        except zipfile.BadZipFile:
            pass
        finally:
            file.seek(0)
        return "application/zip"

    # Formats sans magic bytes : détection par extension
    ext = _get_extension(original_filename or getattr(file, "name", ""))
    if ext in _CSV_EXTENSIONS:
        return "text/csv"
    if ext in _EML_EXTENSIONS:
        return "message/rfc822"

    return "application/octet-stream"
