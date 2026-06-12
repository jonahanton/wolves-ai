from __future__ import annotations

import asyncio
import time

from tests.fakes import ADMIN_HEADERS, build_test_app, client_for, published_engine

TASK_ARN = "arn:aws:ecs:eu-west-2:000000000000:task/wolves/abc123def456abc123def456abc123de"


async def test_admin_stop_answers_while_the_sim_semaphore_is_saturated(tmp_path, monkeypatch):
    engine = published_engine(tmp_path)
    await engine.boot()

    def slow_reach(fit, pins, n_sims, seed, results_until):
        time.sleep(0.5)
        return {}

    monkeypatch.setattr(engine, "_reach", slow_reach)
    app = build_test_app(storage_dir=tmp_path, engine=engine)
    async with client_for(app) as client:
        sims = [asyncio.create_task(client.post("/simulate", json={"nSims": 2000, "seed": seed})) for seed in (1, 2, 3)]
        await asyncio.sleep(0.05)
        started = time.monotonic()
        stop = await client.post("/admin/stop", json={"taskArn": TASK_ARN}, headers=ADMIN_HEADERS)
        elapsed = time.monotonic() - started
        await asyncio.gather(*sims)

    assert stop.status_code == 200
    assert elapsed < 0.3
