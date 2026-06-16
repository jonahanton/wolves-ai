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

A good mixture is not the one with the most worlds. It is the one whose axes
match the strongest live questions after evidence and computation have met.
Sometimes that is model trust against market trust. Sometimes it is a named
contender gap, an availability branch, a result-attribution question, a path
edge, a matchup read, a covariate disagreement or a quiet-day null. The field
guide gives instruments for testing those branches; it is not permission to
publish a stock template.

## Where your numbers come from

Every probability you touch is produced by one deterministic pipeline with
two parts: a fitted strength model and a tournament simulator. The engine
calls the strength model "the champion" (the model that
won the internal model gate; wq docstrings use the term), and your run works
against a frozen copy of its fitted state.

The strength model is a time-decayed Poisson goal model: one strength per
team, fitted by maximum likelihood on the international match history
(about 12k matches inside the decay window) with a 913-day half-life and
importance weighting (friendlies 1.0, competitive 2.5 to 4.0), plus two
globals (goal intercept, home advantage). No Elo prior; elo_history is
reference data, not an input. The MLE covariance is the free approximate
posterior behind wq.posterior_draws and wq.title_uncertainty. Strength
units: 0.1 is roughly 100 Elo or 0.47 goals per match.
wq.model_explain(team) decomposes any fitted strength into the results
behind it.

The simulator Monte Carlos the full 48-team tournament (groups, best-thirds
qualification, bracket) from match score grids, with common random numbers
by seed so paired runs difference cleanly. Played results enter twice:
overlaid on the bracket (the match is no longer random) and overlaid on the
fit (strengths see last night's games); the attribution report separates
the two channels. In live mode an in-match hazard model fitted to World Cup
goal timings drives minute-by-minute probabilities.

On agent runs the submitted mixture is the agent's forecast surface. A
calibration governor can shrink final published probabilities towards the
deterministic anchor when the adjustment track record turns negative;
check_forecast previews that final surface. You work from two reference views
of equal standing: this model, and the market consensus (a weighted log-odds
blend of de-vigged bookmaker outrights and Polymarket), which historically
beats the raw model by about 0.031 nats per match. They are references, not
mandatory worlds. A model-base and market-base split is correct only when
trust in those instruments is the day's live uncertainty. If the live
uncertainty is a named market gap, result-attribution question, availability
branch, path edge, matchup read or covariate disagreement, make the worlds
express that football question directly. The market base is available by
inverting prices into implied strengths (wq.implied_delta), but a large gap
between the bases is a finding that demands work, never a hidden market leg
the harness will add. Reconcile it inside the mixture, in either direction.
The snapshot still records the market and a reference blend for transparency.
Deterministic (non-agent) runs do publish a fixed convex blend with the
market; that is their guard against having no reasoning layer, not yours.

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
in availability analysis. The second most consequential is certainty:
"doubtful", "racing to be fit" and "managed in training" are weighted splits
across plays-diminished and misses-matches worlds (managed load sits near
-0.03 strength, a true tournament-ending loss near -0.10), never the worst
case at weight 1.0. Reserve certainty weighting for a confirmed ruling-out.

### Scenario mixtures and factor lattices

Method: list the plausible axes first, then choose the smallest world shape
that preserves the real uncertainty. Candidate axes can include reference
trust (model vs market), a named contender gap, an availability branch,
result attribution, matchup/path leverage, external covariates, or a true
quiet day. Express a story as a factor with weighted variants, compose
factors into a lattice with wq.scenario_mixture, and read four things from
the output: the mixture headline, the per-factor marginals (the attribution
AND the noise check), the noise floor, and the implied spread against the
parameter floor (wq.mixture_spread). Ride magnitude uncertainty as
Normal(mean, sd) deltas or MC draws; where the response is locally linear the
mean magnitude is adequate and the draw sd is the cheap materiality test.
The magnitude distribution is the first and largest cheap source of honest
width: on the fitted model a single france world (weight 0.3, mean +0.10)
lifts vs_floor from 1.40 at a point delta to 1.46 at sd 0.04 and 1.66 at sd
0.10, monotone throughout. A flat list of single-team stories captures each
team's width on its own; the lattice adds width to a team only when several
stories bear on THAT team, and then integrates their joint honestly: two
opposing france stories (up +0.12, down -0.10) gave flat vs_floor 1.84 but
lattice 1.62, because the joint "both" world partially cancels. So choose the
lattice for co-occurring or interacting stories, the flat list with
distribution deltas for independent single-team stories, and never reach for
the lattice as a width device. When three or more continuous drivers are
jointly live the lattice truncates at the world cap and under-disperses;
express those as continuous latent effects, which ride one set of draws.
The same factor structure applies all tournament; scope each scenario to
the fixtures actually remaining, never to games already played.
Example output: a three-world fitness morning (0.55/0.33/0.12) gave
conditionals 6.99/6.61/4.28pp England title, mixture 6.54 against baseline
6.99; composed with a heat factor (0.70/0.30) the 6-world lattice gave 6.68
vs 7.19; the heat marginals (6.67 vs 6.69) sat inside the paired-seed floor,
so the artifact said heat does not move the headline, and an MC heat
magnitude Normal(-0.15, 0.05) over 20 draws moved the answer by 0.07pp with
draw sd 0.04pp: immaterial.

### The axis audit and mixture spread read

Method: before registering a mixture on a contested day, write the axis audit
in the result: which axes you considered, which evidence or computation made
each live, which axes were collapsed, merged or rejected, and why the
surviving worlds are the right branches. Then read the band those worlds
imply against the parameter-noise floor with wq.mixture_spread; the same read
is available on the forecast node as the mixture_spread quick-look and in the
spread section of check_forecast. Example output:
wq.mixture_spread(scenarios=worlds) gave Spain mean 0.138, band [10.4, 16.7],
width 6.3pp against a 5.1pp floor, vs_floor 1.24, with world means model_base
0.186 / market_base 0.160 / spain_injury 0.071 and the note "spain band 6.3pp
is 1.24x the parameter floor and overlaps yesterday's 7.9 to 14.6". Reading
vs_floor: below ~1.05 with contested evidence on the ledger, a believed
branch is missing from the mixture; comfortably above, submit.

### Two instruments for two unknowns

Method: pick the uncertainty instrument from the kind of unknown. Magnitude
unknown (how big is the knock) rides inside one world as a delta
distribution; regime unknown (does he play at all) is discrete worlds with
weights matching the reporting. Example output: a knock of uncertain size
priced as DeltaDistribution(mean=-0.10, sd=0.03) inside the injury world,
while "60/40 he starts" priced as two worlds at 0.60/0.40; collapsing the
regime split into one averaged delta understated the published band and
flagged mixture_underdispersed.

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

### Fixture effects read through the phase's lens

Method: read fixture stories through the lens the tournament phase makes
relevant, never title pp alone, which hides most of the action for any
favourite: during group play, qualification and group-win probabilities;
in the knockout rounds, per-round reach (wq.reach) and path difficulty,
since group columns no longer exist. Example output (group phase): England
v Croatia win 2-0 = +0.78pp title, draw -0.01, loss 0-1 = -1.40 (the loss
costs nearly twice the win's gain); the Mexico altitude case moved group
win 52.2 to 55.0 while title pp moved 0.04.

### Two update channels, both material

Method: after results land, decompose the day's move into the bracket-overlay
channel and the refit channel with the attribution report, and never re-add
by hand what the refit already priced. On days with no ingested results both
channels are zero by construction and this method is a no-op; in the
knockout rounds the bracket channel reflects elimination rather than
qualification, and the same decomposition applies. Example output: after a mocked
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

### The disagreement chain (gap, structural test, posterior)

Method: any model-vs-market gap runs the same three calls. wq.implied_delta
translates the gap into strength units you can argue about;
wq.title_uncertainty asks whether the gap sits outside the model's own
parameter uncertainty (inside [p10, p90] is noise, outside is structural
disagreement worth a world); a posterior reconciliation (conjugate, or emcee
on a hand-written log-posterior with the market as a noisy logit observation)
produces the DeltaDistribution to publish. For the width the resulting
mixture implies, wq.mixture_spread is the instrument, not title_uncertainty.
Example output: France model 8.5
vs market 15.6 inverted to +0.147; the gap sat outside France's own 80%
parameter CI [4.9, 10.9] while Spain's and Brazil's gaps sat inside theirs
(no action); the emcee posterior gave delta +0.126 (80% CI +0.076..+0.177),
title 14.8%, published as DeltaDistribution(mean=0.126, sd=0.039).

### The score-test misrating hunt

Method: convert a contender's recent-results residual into a parameter delta
via the model's own likelihood (delta = score/information, SE =
1/sqrt(information)), run it both on the current fit and on a fit frozen in
the past: the gap between the two separates "model cannot fit this team"
from "team changed regime". Cross-check any flag by refitting the decay
half-life at the extremes; the per-team perturbation should reproduce the
wholesale refit's title impact. Example output: Norway +0.234 in-sample
(z=1.8), +0.607 out-of-sample (z=4.4); priced at +0.20 the title impact is
+5.4pp against a 0.4pp floor, and the 1-year-half-life refit independently
reproduced it (+5.24pp). Brazil and Belgium flagged the other way (-3.1pp,
-2.2pp). Size the published world BELOW the full residual delta: the
half-life is a prior, not an error.

### External covariates as second measurements

Method: regress the fitted strengths on an external covariate across the
full cross-section, treat the regression line as a noisy second measurement,
and let a conjugate update against the model's own posterior variance size
the perturbation; for time-series signals, fit the SIGNED coefficient and
demand era stability plus an out-of-sample log-loss gain before pricing.
Where two independent signals agree (z-scores across the cross-section),
price the agreement; where independent instruments CONFLICT on a team, widen
the world's DeltaDistribution rather than picking a side. Example output:
squad value (R2 0.85, n=48) gave England prior N(1.494, 0.123) x likelihood
N(1.563, 0.125) = posterior +0.034, +1.35pp title; Elo trend came out
mean-reverting, not momentum (coefficient -0.0043 per Elo-point/year,
z=-4.7, sign-stable across four eras, OOS log-loss gain), fading Spain
(steepest climb, also hot vs squad value: both signals agree) by -4.3pp
conservatively; Norway was flagged UP by the score test and DOWN by the
value regression, so its world widened instead of moving.

### The leverage map

Method: with common random numbers the whole Jacobian of title-vs-parameter
is cheap; sweep +-0.05/+-0.10 across the contenders before deciding where
analysis is worth spending, and report fixture leverage in BOTH rankings:
raw win-minus-loss spread (tail exposure; favourites' wins over minnows are
already priced, all the leverage is in the loss) and probability-weighted
expected movement (news value). Example output: exposure is proportional to
title probability (Spain 3.37pp per +0.05, England 1.64, Norway 0.84);
France-Iraq carried the biggest tail (spread 3.16pp title, -30pp R32 on a
loss, win +0.01pp) while England-Croatia carried the most expected movement
(0.85pp). Perturbation algebra: additive to ~0.2pp EXCEPT favourite-down
plus rival-up pairs, ~15% super-additive on the rival (replicated across
three seeds), so mixtures simulate opposite-sign worlds jointly, never by
summing single impacts. Interaction terms combine three runs; inflate the
floor by sqrt(3) and replicate across seeds before declaring one real.

### One result, one update

Method: wq.update_from_result sizes the strength update one played match
justifies (the model's own match likelihood over a delta grid, weighted by
the champion's parameter prior); the qualification-path effect of the result
flows separately through the played-results channel and is never re-added.
Example output: England losing to Panama justifies -0.044 (-1.6pp title);
beating Croatia +0.018; an expected win under +0.01. Information is
asymmetric (surprises carry 3-5x), scorelines roughly double a bare W/D/L,
and the posterior sd barely moves (0.121 vs prior 0.123): no single match
justifies a large update. Cap single-match form perturbations at |0.05|,
typical |0.02|. Distinct instrument for a different question:
MatchOutcomePerturbation and ScorelinePerturbation pin a result into the
sim path (what does this fixture outcome do to the bracket), while
update_from_result moves the fitted strength (what does this result say
about the team); mid-tournament analyses usually need both, never summed.

### The conditional vocabulary (matchup, stage and knockout-outcome bets)

Method: when a belief is local to a pairing or a round rather than the whole
tournament, reach for the conditional types instead of laundering it into a
flat strength shift. OpponentConditionalStrength(team, opponents, delta) shifts
a side's goal rate only when it meets named opponents (a matchup read: a team
that struggles against a low block); StageConditionalStrength(team, stage,
delta) shifts it only in one knockout round (a side that raises its level once
elimination football starts; stage is r32/r16/qf/sf/final); KnockoutOutcome(
team, opponent, p_advance, stage) bets the resolved advance directly should the
pairing occur, the honest answer to "back France over Spain at 55% if they
meet". All three are scoreable against the baseline (they move per-match and
title probabilities the ledger already tracks) and publish; size deltas on the
same scale as a strength shift (0.1 is a clear edge, beyond 0.3 implies a
different team). Example output (13 Jun, dataset 5323afd41ba9, 30k CRN sims):
KnockoutOutcome(Spain over Argentina, p_advance=0.95) moved Spain title 18.1 to
22.9pp and Argentina 9.8 to 6.3; OpponentConditionalStrength(Spain +0.8 vs
Argentina) moved Spain to 22.1 and Argentina to 6.6 (a strong matchup edge
priced through the lambdas rather than the resolved outcome);
StageConditionalStrength(Spain +0.8 in the final) moved Spain to 25.9, all of it
landing in the one round it touches. Prefer KnockoutOutcome when the belief is
about who advances and OpponentConditionalStrength when it is about how the
match is played; a confederation-wide correlated move is a multi-team
LatentEffect, not a perturbation.

### News-shock scale (example outputs, recompute to use)

Backup keeper in (-0.03 strength) = -1.09pp. Star striker out (-0.12) =
France -3.77pp, Spain +0.59. One-match tactical worry (-0.3 xG) = -0.20pp.
These three points exist to stop order-of-magnitude errors, not to be reused
as magnitudes.

## News-to-parameter patterns

Each pattern names the mechanism, the calibration anchor or computation
path for its magnitude, the key uncertainty, and the market cross-check.
They are prompts for the analysis, not steps that must all be taken;
compose and overrule with stated reasons.

- INJURY / AVAILABILITY. Mechanism first (the 8x lesson above). Magnitude
  from the anchors: an all-time great absent is 5 to 10pp win probability
  (~0.15 to 0.25 goals), a normal starter an order of magnitude less; or
  computed by remove-and-reaggregate lineup strength. Uncertainty as a
  fitness split (plays / misses group / plays diminished) with
  Bayesian-derived weights. Cross-check by inverting the market move: if the
  market re-priced -0.10 and the mechanism says group-games-only, one of you
  is wrong, and that disagreement IS the finding. A confirmed availability
  item is priced or explicitly nulled with its noise floor, never waved
  through as "already in the model": the refit cannot see a single-fixture
  absence at all.
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
It is also possible that the market has priced something in a direction you
disagree with, which is more than valid. Given that we only see the output
univariates from the market, and not the reasoning, it can be hard to know
what caused the changes in market numbers.

## What the evidence says is already in the price

Decline briefs built on these; the citation is the finding:

- Momentum overlays: worse than null. Elo trend is mean-reverting (signed
  coefficient z=-4.7, sign-stable across four eras, OOS-validated): hot
  teams underperform their level. Price reversion or nothing, never
  momentum.
- Favourite-longshot corrections after proportional de-vig: the shrinkage
  fit gave b=0.80 with CI [0.63, 1.04] and the correction failed
  leave-one-tournament-out scoring; de-vigged tournament prices are already
  approximately calibrated, and the 2022 tail produced Morocco, so never
  shave longshots.
- Ad-hoc upset inflation: the sim's draw and upset tails match 1,098
  historical tournament matches bin-by-bin; upsets are priced.
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
- Value-share bridge for tournament-long absence: when player values are
  available, a player who is share s of squad value shifts log(value) by
  log(1-s); times the fitted value-prior slope (regress teams.elo on log squad_value_eur_m in wq)
  times the 0.45 blend weight gives an Elo-point ceiling for the absence
  world. A principled anchor beside the managed/out magnitudes (moderate:
  arithmetic on the engine's own prior).
- Shootouts 50/50; at most ~55/45 on extreme squad-value gaps (strong null).
- Outright market vs Elo at match level: market better by 0.031 nats per
  match (95% CI 0.001 to 0.062, n=230): weight it meaningfully, never defer
  to it (moderate).
- Single-result form update: cap |0.05| strength, typical |0.02|
  (engine-measured via the posterior grid; recompute with
  wq.update_from_result).
- elo_history year Y is END-of-year rating. When querying elo_history
  directly, year-1 is the pre-tournament prior; using year Y leaks the
  tournament itself (data trap, strong).
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
