"""Define archive workflow failures."""

from __future__ import annotations


class ArchiveExportError(ValueError):
    """The requested source cannot create a verified static archive."""
