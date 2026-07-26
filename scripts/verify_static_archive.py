#!/usr/bin/env python3
"""Verify a content-addressed static archive release."""

from __future__ import annotations

import argparse
from pathlib import Path

from wolves.archive.contracts import ArchiveManifest
from wolves.archive.errors import ArchiveExportError
from wolves.archive.publish import release_digest
from wolves.archive.verify import verify_archive


def main() -> None:
    """Verify the archive contract and release digest."""
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("root", type=Path)
    parser.add_argument("expected_release")
    args = parser.parse_args()

    manifest = ArchiveManifest.model_validate_json((args.root / "manifest.json").read_bytes())
    verify_archive(args.root, manifest)
    actual_release = release_digest(args.root)
    if actual_release != args.expected_release:
        raise ArchiveExportError(
            f"archive release digest differs: expected {args.expected_release}, received {actual_release}"
        )


if __name__ == "__main__":
    main()
