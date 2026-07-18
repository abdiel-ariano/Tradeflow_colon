"""Validate uploaded files (type, size, image decode) before storage."""
from __future__ import annotations

import logging
from pathlib import Path

log = logging.getLogger('tradeflow.security')

IMAGE_CONTENT_TYPES = frozenset({
    'image/jpeg', 'image/jpg', 'image/png', 'image/webp', 'image/gif',
})
PROOF_CONTENT_TYPES = IMAGE_CONTENT_TYPES | frozenset({'application/pdf'})
IMAGE_EXTS = frozenset({'.jpg', '.jpeg', '.png', '.webp', '.gif'})
PROOF_EXTS = IMAGE_EXTS | frozenset({'.pdf'})

_MAGIC_JPEG = (b'\xff\xd8\xff',)
_MAGIC_PNG = (b'\x89PNG\r\n\x1a\n',)
_MAGIC_GIF = (b'GIF87a', b'GIF89a')
_MAGIC_WEBP_RIFF = b'RIFF'
_MAGIC_WEBP_WEBP = b'WEBP'


class UploadValidationError(ValueError):
    """Raised when an upload fails security checks."""


def _ext(name: str) -> str:
    return Path(name or '').suffix.lower()


def _sniff_image_kind(head: bytes) -> str | None:
    """Return jpeg/png/gif/webp from magic bytes, or None."""
    if not head:
        return None
    if any(head.startswith(m) for m in _MAGIC_JPEG):
        return 'jpeg'
    if any(head.startswith(m) for m in _MAGIC_PNG):
        return 'png'
    if any(head.startswith(m) for m in _MAGIC_GIF):
        return 'gif'
    if (
        len(head) >= 12
        and head.startswith(_MAGIC_WEBP_RIFF)
        and head[8:12] == _MAGIC_WEBP_WEBP
    ):
        return 'webp'
    return None


def _pillow_verify(uploaded) -> None:
    """Raise UploadValidationError if Pillow cannot decode the image."""
    try:
        from PIL import Image
        if hasattr(uploaded, 'seek'):
            uploaded.seek(0)
        with Image.open(uploaded) as im:
            im.verify()
        if hasattr(uploaded, 'seek'):
            uploaded.seek(0)
    except UploadValidationError:
        raise
    except Exception as exc:
        raise UploadValidationError('bad_image') from exc


def validate_uploaded_file(
    uploaded,
    *,
    max_bytes: int,
    allowed_content_types: frozenset[str],
    allowed_exts: frozenset[str],
    require_image_decode: bool = False,
) -> object:
    """Return ``uploaded`` if safe; raise ``UploadValidationError`` otherwise."""
    if not uploaded:
        raise UploadValidationError('empty')
    size = int(getattr(uploaded, 'size', 0) or 0)
    if size <= 0:
        raise UploadValidationError('empty')
    if size > max_bytes:
        raise UploadValidationError('too_large')

    name = (getattr(uploaded, 'name', '') or '').strip()
    if not name or _ext(name) not in allowed_exts:
        raise UploadValidationError('bad_extension')

    content_type = (getattr(uploaded, 'content_type', '') or '').split(';')[0].strip().lower()
    if content_type and content_type not in allowed_content_types:
        # Some browsers send application/octet-stream — fall through to magic checks.
        if content_type not in ('application/octet-stream', ''):
            raise UploadValidationError('bad_content_type')

    # Sniff first bytes for images / PDF.
    pos = uploaded.tell() if hasattr(uploaded, 'tell') else None
    try:
        head = uploaded.read(32) or b''
        if hasattr(uploaded, 'seek'):
            uploaded.seek(pos or 0)
    except Exception as exc:
        log.warning('upload_read_failed err=%s', exc)
        raise UploadValidationError('unreadable') from exc

    ext = _ext(name)
    if ext == '.pdf':
        if not head.startswith(b'%PDF'):
            raise UploadValidationError('bad_magic')
        return uploaded

    kind = _sniff_image_kind(head)
    if require_image_decode:
        if kind is None and ext != '.webp':
            raise UploadValidationError('bad_magic')
        _pillow_verify(uploaded)
        return uploaded

    if kind is None and ext in IMAGE_EXTS:
        # Soft path (proofs): allow octet-stream + known image ext only if magic ok
        # or webp RIFF already handled; otherwise reject.
        raise UploadValidationError('bad_magic')
    return uploaded


def validate_image_upload(uploaded, *, max_bytes: int = 5 * 1024 * 1024):
    """Validate a product/logo/license image upload."""
    return validate_uploaded_file(
        uploaded,
        max_bytes=max_bytes,
        allowed_content_types=IMAGE_CONTENT_TYPES,
        allowed_exts=IMAGE_EXTS,
        require_image_decode=True,
    )


def validate_proof_upload(uploaded, *, max_bytes: int = 5 * 1024 * 1024):
    """Validate a bank-transfer proof (image or PDF)."""
    return validate_uploaded_file(
        uploaded,
        max_bytes=max_bytes,
        allowed_content_types=PROOF_CONTENT_TYPES,
        allowed_exts=PROOF_EXTS,
        require_image_decode=False,
    )
