# Field guide: quantitative reasoning for the Wolves forecaster

Reference material, not a syllabus: methods with example outputs, not a table
of current values. Two kinds of numbers live here and they age differently.
Literature anchors and evidenced nulls are stable; they carry evidence grades
and you may lean on them directly. Engine measurements are EXAMPLE OUTPUTS,
captured once (10 June 2026, champion fit, dataset f6aae7630aae, 50k
common-random-number sims unless stated) to show each method's shape and
rough scale; the live surface drifts with every refit, so recompute before a
measured number does any work in a finding. One wq call is cheaper than one
stale anchor. England in the examples is simply the team the method was
demonstrated on; every method applies unchanged to any team. The only
low-altitude rules are in the statistical honesty section.

## Methods, each with an example output

### Elasticity, and its convexity

Method: before sizing any story, sweep the parameter through wq.impact and
read the local slope; never extrapolate linearly from one point. Example
output: England strength +0.02 = +0.61pp title, +0.05 = +1.71, +0.10 = +4.26,
+0.20 = +9.58, +0.30 = +17.30, so the +0.30 effect is 4x the +0.10 effect,
and longshots scale down brutally (Ghana +0.10 = +0.008pp, below the noise
floor; +0.30 = +0.23pp). The lesson is structural: the response is convex in
strength and collapses with baseline title probability.

### The two absence mechanisms, far apart

Method: decide which mechanism the news implies before sizing it, because a
match-scoped rate hit and a tournament-scoped strength hit price the same
headline an order of magnitude apart. Example output: a star missing
England's group games only (-0.20 xG per game via MatchRatePerturbation) cost
-0.38pp title, because England qualify regardless; the same star diminished
for the whole tournament (-0.10 strength) cost -3.03pp, 8x more. Which
mechanism a story implies is the single most consequential modelling choice
in availability analysis.

### Scenario mixtures and factor lattices

Method: express a story as a factor with weighted variants, compose factors
into a lattice with wq.scenario_mixture, and read three things from the
output: the mixture headline, the per-factor marginals (the attribution AND
the noise check), and the noise floor. Ride magnitude uncertainty as
Normal(mean, sd) deltas or MC draws; where the response is locally linear the
mean magnitude is adequate and the draw sd is the cheap materiality test.
Example output: a three-world fitness morning (0.55/0.33/0.12) gave
conditionals 6.99/6.61/4.28pp England title, mixture 6.54 against baseline
6.99; composed with a heat factor (0.70/0.30) the 6-world lattice gave 6.68
vs 7.19; the heat marginals (6.67 vs 6.69) sat inside the paired-seed floor,
so the artifact said heat does not move the headline, and an MC heat
magnitude Normal(-0.15, 0.05) over 20 draws moved the answer by 0.07pp with
draw sd 0.04pp: immaterial.

### Implied-delta inversion (what is the market pricing?)

Method: when the model and the market disagree, invert the gap (brentq on the
strength delta that reproduces the market price) to translate pp into
parameter units you can argue about. Example output: market England 11.18 vs
model 7.19 inverted to +0.099 strength, one key-player-class upgrade; the
France gap (-7.31pp) was the largest on the board. Every gap is a research
question, not an error to be corrected.

### Triangulation

Method: hunt edges where two INDEPENDENT instruments accuse the same team;
one instrument alone is a hypothesis. Example output: the squad-value
regression (corr 0.94 with fitted strengths, n=40) flagged Colombia as most
overrated against its squad value (+0.22 residual) while Colombia also
carried the largest positive model-vs-market gap (+2.89pp). Squad value is
the single best-evidenced non-market covariate (Peeters 2018, beats Elo and
FIFA rank).

### Group-stage effects read through group lenses

Method: read group-stage stories through qualification and group-win
probabilities, not title pp, which hides most of the action for any
favourite. Example output: England v Croatia win 2-0 = +0.78pp title, draw
-0.01, loss 0-1 = -1.40 (the loss costs nearly twice the win's gain); the
Mexico altitude case moved group win 52.2 to 55.0 while title pp moved 0.04.

### Two update channels, both material

Method: after results land, decompose the day's move into the bracket-overlay
channel and the refit channel with the attribution report, and never re-add
by hand what the refit already priced. Example output: after a mocked
matchday (England 2-0, Argentina upset) the bracket overlay alone moved
England 6.99 to 7.79 and the refit carried it to 8.69, roughly +0.8pp through
the bracket and +0.9pp through strengths for one group win.

### The negative finding, submitted as the deliverable

Method: when the computation says the story does not move the forecast, the
finding IS that null, stated with its evidence: the computed delta, the noise
floor it sits under, and the citation if a published null applies. Example
output: "Dallas heat does not move the England headline: marginals 6.67 vs
6.69, inside the 0.17pp paired-seed floor; magnitude uncertainty tested by MC
draws, sd 0.04pp" is a complete, submit-ready quant result. Do not pad a null
into an adjustment to seem useful.

### News-shock scale (example outputs, recompute to use)

Backup keeper in (-0.03 strength) = -1.09pp. Star striker out (-0.12) =
France -3.77pp, Spain +0.59. One-match tactical worry (-0.3 xG) = -0.20pp.
These three points exist to stop order-of-magnitude errors, not to be reused
as magnitudes.

## News-to-parameter patterns

Each pattern is mechanism -> magnitude (anchored or computed) -> uncertainty
(scenario split or distribution) -> market cross-check (inversion) -> output
impact. Compose and overrule with stated reasons.

- INJURY / AVAILABILITY. Mechanism first (the 8x lesson above). Magnitude
  from the anchors: an all-time great absent is 5 to 10pp win probability
  (~0.15 to 0.25 goals), a normal starter an order of magnitude less; or
  computed by remove-and-reaggregate lineup strength. Uncertainty as a
  fitness split (plays / misses group / plays diminished) with
  Bayesian-derived weights. Cross-check by inverting the market move: if the
  market re-priced -0.10 and the mechanism says group-games-only, one of you
  is wrong, and that disagreement IS the finding.
- LINEUP / ROTATION. Predicted XI strength, never vibes; rotation is real
  only as named players (backup keeper -0.03 = -1.09pp anchors the scale).
  Rumours justify nothing; a tier-1 leaked XI is a scenario, a tier-3 guess
  is a watch item. Lineup news is the market's bread and butter, so check
  what_changed timestamps before assuming any edge survives.
- WEATHER / HEAT / VENUE. Symmetric match-rate suppression unless the
  evidence says acclimatisation asymmetry. Altitude is anchored: ~0.5 goals
  per 1,000 m unacclimatised (BMJ, 1,460 matches), haircut for
  acclimatisation; Mexico City and Guadalajara are live cases. Heat has no
  peer-reviewed goal anchor: magnitude as a distribution (the validated
  Normal(-0.15, 0.05) pattern), labelled a weak prior. Read through group
  lenses.
- FATIGUE / REST. The evidence says decline: no effect with 3+ days both
  sides (Scoppa, all WCs and Euros). Real triggers: under 3 days, or extreme
  asymmetry. A brief built on ordinary rest differentials gets this citation
  back as the finding.
- RECENT FORM. Already in the model: the time-decayed refit holds everything
  real in form. THE DOUBLE-COUNT CHECK IS THE PATTERN: compute what the
  refit already moved (both channels above) and adjust only for information
  the refit cannot see: xG-stripped luck (regress goals-vs-xG gaps to mean),
  results not yet ingested, opponent-quality context the decay misreads.
- MORALE / MANAGER. True manager-change effect ~zero; the apparent bounce is
  regression to the mean. Morale is real only when it operationalises into
  lineup or availability mechanics. Otherwise the honest move is no
  adjustment, with the null cited, and at most a low-weight watch scenario.

### The already-priced-in check

Every price carries its own clock: bookmaker last_update timestamps and the
Polymarket snapshot captured_at. The discipline is to put the news event time
next to those clocks and the market_movement series around it. If the market
re-priced after the news landed, the information is in the price; adjusting
the model again double-counts it. The edge, if any, is where your mechanism
disagrees with the size or direction of the market's move, and that
disagreement is the finding to write up, not a reason to re-add the news.
It's also possible that the market has priced something in a way which you
disagree with, which is more than valid. Given that we only see the output
univariates from the market, and not the reasoning, it can be hard to know
what caused the changes in market numbers.

## What the evidence says is already in the price

Decline briefs built on these; the citation is the finding:

- Momentum and recent-form overlays (null once ability is controlled).
- Rest-day differentials at 3+ days both sides.
- Penalty shootout skill beyond a few points off 50/50 (our 50/50 stands and
  cannot be overridden).
- Steam-chasing: following an odds move after it happens has no documented
  value; the close is the calibration target, not the path to it.
- Travel distance as a standalone effect; vague motivation or pressure
  fudges unless operationalised as predicted rotation feeding lineup
  strength.
- Within-tournament dynamic-strength models: quarterly drift is 0.01 to 0.03
  (Spain +0.099 across WINNING Euro 2024 is the extreme); cheap refits are
  all the dynamics the data supports.
- Heavy Bayesian machinery on results data: hierarchical partial pooling
  LOST to the champion out of sample (0.8312 vs 0.8233 log loss) and
  posterior predictive averaging was a null. Use wq.posterior_draws (the MLE
  covariance is the free approximate posterior) and spend the compute on
  covariates, blend weights and calibration instead.

## Calibration anchors (with evidence grades)

- International home advantage ~100 Elo ~0.45 goals (strong).
- WC host advantage ~167 to 187 Elo-equivalent (strong, historical).
- Altitude ~0.5 goals per 1,000 m unacclimatised (strong, BMJ n=1,460).
- 100 Elo ~0.47 goals ~0.1 strength units (definitional).
- All-time great absent: 5 to 10pp win probability, ~0.15 to 0.25 goals
  (weak: market-revealed, not peer-reviewed; label as a prior).
- Normal starter absent: an order of magnitude less (weak).
- Shootouts 50/50; at most ~55/45 on extreme squad-value gaps (strong null).
- Paired-seed noise floor at 50k sims: ~0.2pp for favourites (England
  seed-pair delta 0.17pp), ~0.35pp at 100k for Spain-sized favourites.
  Cross-team deltas below the floor are fiction; wq.impact reports it.

## Statistical honesty (the one low-altitude zone)

Capable agents p-hack without meaning to, and the failures are invisible, so
these are rules, not suggestions:

- State the analysis plan in the workspace before touching data on any
  model-fitting task.
- Report all runs, not the best run; multiplicity is flagged when screening
  many hypotheses.
- Respect holdout discipline: never tune and evaluate on the same matches.
- Negative results are first-class findings. "Partial pooling adds nothing
  here" was one of this guide's most valuable results.
- Every analysis ends with an externally checkable signal: a holdout score,
  a parity check, a noise-floor comparison, a reproduced baseline.
