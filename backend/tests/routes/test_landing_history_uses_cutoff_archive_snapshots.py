from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[3]


def test_landing_history_uses_only_snapshots_in_the_selected_archive_payload():
    archive_source = (REPO_ROOT / "web/src/components/archive/archive-landing-page.tsx").read_text(
        encoding="utf-8"
    )
    page_source = (REPO_ROOT / "web/src/app/page.tsx").read_text(encoding="utf-8")

    assert "payload.forecast_history" in archive_source
    assert "loadDefaultArchiveDay()" in page_source
    assert "fetch(" not in archive_source
