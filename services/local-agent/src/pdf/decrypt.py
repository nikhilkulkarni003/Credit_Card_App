"""
Local PDF decryption + text extraction. Runs entirely on-machine — the password
is held in a local variable only for the duration of this call and is never
logged, returned, or persisted here.
"""

from __future__ import annotations

import pymupdf


class PdfDecryptError(Exception):
    """Raised on a wrong password or unreadable PDF. Message must never include the password."""


def decrypt_and_extract_text(pdf_bytes: bytes, password: str) -> str:
    doc = pymupdf.open(stream=pdf_bytes, filetype="pdf")
    try:
        if doc.needs_pass:
            ok = doc.authenticate(password)
            if not ok:
                raise PdfDecryptError("Incorrect statement password (or corrupted PDF).")

        pages_text = [page.get_text() for page in doc]
        return "\n".join(pages_text)
    finally:
        doc.close()
        del password
