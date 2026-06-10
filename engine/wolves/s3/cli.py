"""Shared --storage flag so any run can choose local, s3 or both."""

from __future__ import annotations

from typing import TYPE_CHECKING

from wolves.s3.layout import StorageMode

if TYPE_CHECKING:
    import argparse

    from wolves.config import Settings

STORAGE_MODES: tuple[StorageMode, ...] = ("local", "s3", "both")


def add_storage_argument(parser: argparse.ArgumentParser) -> None:
    parser.add_argument(
        "--storage",
        choices=STORAGE_MODES,
        default=None,
        help="where artifacts are stored this run (default: STORAGE_MODE setting)",
    )


def apply_storage_choice(settings: Settings, storage: StorageMode | None) -> Settings:
    return settings.model_copy(update={"storage_mode": storage}) if storage else settings
