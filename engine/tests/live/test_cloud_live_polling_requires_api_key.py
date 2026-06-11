from __future__ import annotations

import pytest

from wolves.config import Settings
from wolves.live import build_fixtures_client


def test_cloud_live_polling_requires_the_real_api_key(tmp_path) -> None:
    settings = Settings(runs_root=tmp_path, storage_mode="both", bucket="test-bucket", api_football_key="")

    with pytest.raises(RuntimeError, match="API_FOOTBALL_KEY"):
        build_fixtures_client(settings)
