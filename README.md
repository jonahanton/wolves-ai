# The Wolves' World Cup Superforecaster

World Cup 2026 forecasting app. A Python Monte-Carlo engine and FastAPI backend serve published forecast snapshots to a Next.js frontend.

## How the forecast works

The agent pipeline runs once a day. An LLM agent graph plans and executes the forecast as a dynamic wave-scheduled DAG: a master agent dispatches waves of specialist worker nodes (research, quant, forecast, critic) onto a shared blackboard, with a referee guarding scope and a pre-mortem critic stress-testing the result. Research nodes pull live signal from web search (Brave and Exa); the quantitative base is fitted from Elo histories, past international results (football-data, martj42), bookmaker and Polymarket market closes, and squad rosters.

The agents do not pick a single scoreline: they propose a set of weighted scenario worlds, each expressed as additive Elo rating deltas over that base. Every world is simulated by Monte-Carlo over the full bracket (50,000 simulations for the published numbers) using an Elo/Poisson bivariate match engine, and the tournament's actual rules are enforced exactly in simulation: real group fixtures, FIFA group tiebreakers, the best-third-place ranking, and the fixed knockout bracket. The per-world champion, reach and exit distributions are combined into a weighted mixture, extremised against a baseline prior. Live match-day results then update the posterior in place, differencing two reach simulations to attribute each probability shift to results or in-game state.

## Run locally

Requires Docker and Make.

```bash
make setup     # create the Python venv and install frontend deps
make app/up    # build and start the full stack (engine, backend, web, db)
```

The app is then at http://localhost:3000 (backend on http://localhost:8080).

```bash
make app/down  # stop the stack
make app/logs  # tail logs
```

## Demo data

To preview a live match-day without real fixtures, toggle a synthetic scenario (a few finished results plus one in-play game). It parks the poller so it cannot overwrite the scenario.

```bash
make demo/on   # apply the synthetic live scenario
make demo/off  # restore real data and re-enable the poller
```

## Serving

The daily run publishes its output as a snapshot (probability distributions, bracket samples) to S3; the backend serves the latest snapshot and the frontend displays it. Live match-day results are polled from API-Football and overlaid on the published forecast.

## Develop

```bash
make lint            # engine + backend (ruff)
make test            # engine + backend tests
make frontend/dev    # run the web app with hot reload
make frontend/lint
```

## Licence

AGPL-3.0. See [LICENSE](LICENSE).
