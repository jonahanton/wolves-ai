"""Print the declared blob layout; --live adds what is actually stored."""

from __future__ import annotations

import argparse

from wolves.config import Settings
from wolves.observability.logging import configure_cli_logging
from wolves.s3.artifacts import ArtifactStore
from wolves.s3.layout import LAYOUT, describe


def main() -> None:
    configure_cli_logging()
    parser = argparse.ArgumentParser(description="Inspect the wolves artifact store")
    parser.add_argument("--live", action="store_true", help="list stored objects per prefix")
    args = parser.parse_args()

    settings = Settings()
    print(describe())
    if not args.live:
        return
    store = ArtifactStore(settings)
    print(f"\nmode={store.mode} bucket={store.bucket or '-'} local_root={store.local_root}")
    for prefix in sorted({spec.prefix for spec in LAYOUT}):
        names = ", ".join(spec.name for spec in LAYOUT if spec.prefix == prefix)
        keys = store.list_keys(prefix=prefix)
        print(f"\n{prefix} ({names})  {len(keys)} object(s)")
        for key in keys[-5:]:
            print(f"  {key}")


if __name__ == "__main__":
    main()
