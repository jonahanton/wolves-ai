# The Wolves' World Cup Superforecaster

World Cup 2026 forecasting app.

## How the forecast works

The full forecast is an agentic pipeline, which is a dynamic graph and I've scheduled it to run once a day. An agent graph plans and executes the forecast as a 
wave-scheduled DAG, with a master agent that dispatches waves of specialist worker nodes (research, quant, forecast, critic) onto a shared workspace. The graph continues to go (the master 'patches' it live) until the master evaluates that the forecast is complete and can be published, and passes a bunch of conditions imposed by a validator agent and a referee agent. Research nodes pull live signal from the web; the quantitative base is fitted from Elo histories, past international results (football-data, martj42), bookmaker and Polymarket market closes.

The agents don't predict the scorelines in individual games as I think this would be subject to heavy bias and clear failure modes, so instead they propose a set of weighted scenario 'worlds', each expressed as additive team strength deltas over a base. Every world is then MC simulated over the full tournament (50k sims) using an Elo/Poisson bivariate match engine, and the tournament's rules are enforced exactly with real group fixtures, FIFA group tiebreakers, the best-third-place ranking, etc. The per-world champion, reach and exit distributions are combined into a weighted mixture, extremised against a baseline prior.

Since the full forecast is relatively expensive to run (a few dollars) between runs I estimate the impact of live/completed fixtures (that have happened since the last forecast) through re-running the MC engine with finished games fixed to their results and in-play games conditioned on a live scoreline distribution.

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

The completed tournament is served as a static Cloudflare Pages archive. The private S3 source archive can reproduce every published tournament day without a live backend.

Deploy a committed update from a clean `main` branch after authenticating AWS and Wrangler:

```bash
make archive/deploy
```

## Develop

```bash
make lint            # engine + backend (ruff)
make test            # engine + backend tests
make frontend/dev    # run the web app with hot reload
make frontend/lint
```

## Licence

AGPL-3.0. See [LICENSE](LICENSE).
