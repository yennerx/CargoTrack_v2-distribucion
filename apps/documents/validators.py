from pathlib import Path

from django.conf import settings
from django.core.exceptions import ValidationError

FILE_SIGNATURES = {
    "pdf": (b"%PDF-", "application/pdf"),
    "png": (b"\x89PNG\r\n\x1a\n", "image/png"),
    "bmp": (b"BM", "image/bmp"),
    "jpg": (b"\xff\xd8\xff", "image/jpeg"),
    "jpeg": (b"\xff\xd8\xff", "image/jpeg"),
}


def validate_document_file(uploaded_file):
    extension = Path(uploaded_file.name).suffix.lower().lstrip(".")
    allowed_extensions = set(settings.DOCUMENT_ALLOWED_EXTENSIONS)
    if extension not in allowed_extensions or extension not in FILE_SIGNATURES:
        raise ValidationError("La extensión del archivo no está permitida.")
    if uploaded_file.size > settings.DOCUMENT_MAX_SIZE_MB * 1024 * 1024:
        raise ValidationError("El archivo supera el tamaño máximo permitido.")

    uploaded_file.seek(0)
    signature, _mime = FILE_SIGNATURES[extension]
    header = uploaded_file.read(len(signature))
    uploaded_file.seek(0)
    if header != signature:
        raise ValidationError("El contenido del archivo no coincide con su extensión.")
    return extension, FILE_SIGNATURES[extension][1]
