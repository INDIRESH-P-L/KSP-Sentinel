"""File upload validation: extension allow-list, magic-byte sniffing, and size cap.

Deliberately does NOT depend on python-magic/libmagic -- that needs a native
libmagic.dll that isn't reliably present on Windows dev machines, and a dependency
that silently isn't there is worse than a slightly shorter list of signatures we
check ourselves. The signatures below cover the extensions we actually allow.

Rejects based on extension AND content signature, not either alone: a renamed
`.exe` given a `.pdf` name is still caught here (wrong magic bytes for the claimed
extension), and a legitimate pdf named `evidence.exe` is still rejected (bad
extension) even though its bytes would look fine.
"""

MAX_UPLOAD_BYTES = 10 * 1024 * 1024  # 10 MB

ALLOWED_EXTENSIONS = {"pdf", "jpg", "jpeg", "png", "csv"}

# (extension set, signature-checker) -- checked against the first bytes of the file.
_MAGIC_SIGNATURES = {
    "pdf": [b"%PDF-"],
    "jpg": [b"\xff\xd8\xff"],
    "jpeg": [b"\xff\xd8\xff"],
    "png": [b"\x89PNG\r\n\x1a\n"],
}


class FileValidationError(ValueError):
    pass


def _extension_of(filename: str) -> str:
    if "." not in filename:
        return ""
    return filename.rsplit(".", 1)[-1].lower()


def validate_upload(filename: str, content: bytes) -> None:
    """Raises FileValidationError with a user-facing reason, or returns None if the
    file passes every check. Caller is responsible for actually deleting/not-saving
    the file on failure."""
    if not filename or "/" in filename or "\\" in filename or ".." in filename:
        # Directory traversal / path injection via a crafted filename.
        raise FileValidationError("Invalid filename")

    ext = _extension_of(filename)
    if ext not in ALLOWED_EXTENSIONS:
        raise FileValidationError(f"File type '.{ext}' is not allowed. Allowed types: {sorted(ALLOWED_EXTENSIONS)}")

    if len(content) == 0:
        raise FileValidationError("File is empty")
    if len(content) > MAX_UPLOAD_BYTES:
        raise FileValidationError(f"File exceeds the {MAX_UPLOAD_BYTES // (1024*1024)} MB size limit")

    # CSV has no reliable magic bytes -- validated instead by requiring the content
    # decode as text and not look like an executable/script in disguise.
    if ext == "csv":
        try:
            content.decode("utf-8")
        except UnicodeDecodeError:
            raise FileValidationError("CSV file is not valid UTF-8 text")
        if content.lstrip().startswith((b"MZ", b"\x7fELF", b"#!")):
            raise FileValidationError("File content does not match its extension")
        return

    signatures = _MAGIC_SIGNATURES.get(ext, [])
    if signatures and not any(content.startswith(sig) for sig in signatures):
        raise FileValidationError("File content does not match its extension (renamed file?)")
