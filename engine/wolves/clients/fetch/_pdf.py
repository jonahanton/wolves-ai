from __future__ import annotations

import io
import logging
from typing import Protocol

logger = logging.getLogger(__name__)


class PDFTextExtractor(Protocol):
    def extract_text(
        self,
        pdf_bytes: bytes,
        *,
        start: int = 1,
        end: int | None = None,
    ) -> tuple[str, str | None]:
        """Return ``(body, title)``. ``start``/``end`` are 1-indexed page bounds."""
        ...


class PyPDFExtractor:
    def extract_text(
        self,
        pdf_bytes: bytes,
        *,
        start: int = 1,
        end: int | None = None,
    ) -> tuple[str, str | None]:
        try:
            from pypdf import PdfReader
            from pypdf.errors import FileNotDecryptedError, PdfReadError
        except ImportError:  # pragma: no cover
            logger.error("pypdf is not installed; cannot extract PDF text")
            return "(PDF text extraction unavailable: pypdf not installed.)", None

        try:
            reader = PdfReader(io.BytesIO(pdf_bytes))
        except (PdfReadError, ValueError, OSError):
            logger.warning("Failed to parse PDF", exc_info=True)
            return "(Failed to parse PDF. The file may be corrupted or encrypted.)", None

        if reader.is_encrypted:
            try:
                if not reader.decrypt(""):
                    return "(PDF is password-protected; text extraction skipped.)", None
            except Exception:
                logger.warning("Failed to decrypt PDF", exc_info=True)
                return "(PDF is password-protected; text extraction skipped.)", None

        try:
            total = len(reader.pages)
        except (PdfReadError, FileNotDecryptedError):
            logger.warning("PDF page index unreadable", exc_info=True)
            return "(Failed to read PDF page index.)", None

        if total == 0:
            return "(Empty PDF.)", None

        lo = max(0, start - 1)
        hi = min(total, end if end is not None else total)
        if hi <= lo:
            return f"(No readable text in selected page range of {total}-page PDF.)", None

        title: str | None = None
        meta = reader.metadata
        if meta:
            raw_title = meta.title or meta.get("/Title")  # type: ignore[attr-defined]
            if isinstance(raw_title, str) and raw_title.strip():
                title = raw_title.strip()

        parts: list[str] = []
        for i in range(lo, hi):
            try:
                text = reader.pages[i].extract_text() or ""
            except (FileNotDecryptedError, PdfReadError):
                logger.debug("pypdf extract_text failed on page %d", i + 1, exc_info=True)
                text = ""
            except Exception:  # pragma: no cover
                logger.debug("pypdf extract_text unexpected error on page %d", i + 1, exc_info=True)
                text = ""
            if text.strip():
                parts.append(f"--- Page {i + 1}/{total} ---\n{text}")

        body = "\n\n".join(parts) or f"(No readable text in selected pages of {total}-page PDF.)"
        return body, title


_default_extractor: PDFTextExtractor = PyPDFExtractor()


def get_pdf_extractor() -> PDFTextExtractor:
    return _default_extractor


def set_pdf_extractor(extractor: PDFTextExtractor) -> None:
    global _default_extractor
    _default_extractor = extractor
