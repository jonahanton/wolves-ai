# Field guide: quantitative reasoning for the Wolves forecaster

Reference material, not a syllabus. Every number below is the engine's own,
measured on the live deterministic surface on 10 June 2026 (champion fit,
dataset f6aae7630aae, 50k common-random-number sims unless stated). Use the
patterns when they fit and compose freely when they do not; the only
low-altitude rules are in the statistical honesty section. England in the
worked examples is simply the team the numbers were measured on; every
pattern applies unchanged to any team.

## Worked examples with real numbers

### Elasticity, and its convexity

England strength sweeps: +0.02 = +0.61pp title, +0.05 = +1.71, +0.10 = +4.26,
+0.20 = +9.58, +0.30 = +17.30. Convex, not linear: the +0.30 effect is 4x the
+0.10 effect. Longshots scale down brutally: Ghana +0.10 = +0.008pp (below
the noise floor), +0.30 = +0.23pp. Know the slope before sizing a story.

### The two absence mechanisms, 8x apart

A star missing England's GROUP GAMES ONLY (-0.20 xG per game via
MatchRatePerturbation) costs -0.38pp title, because England qualify from the
group regardless. The same star diminished for the WHOLE TOURNAMENT (-0.10
strength) costs -3.03pp. Which mechanism a news story implies is the single
most consequential modelling choice in availability analysis.

### Scenario mixtures and factor lattices

The Saka morning, three worlds 0.55/0.33/0.12: conditionals 6.99/6.61/4.28pp
England title, mixture 6.54 (-0.45pp vs baseline). Composed with a Dallas
heat factor (0.70/0.30) the 6-world product lattice gives 6.68 vs baseline
7.19. Per-factor marginals are the attribution AND the noise check: saka
plays/misses/strain marginals 7.16/6.79/4.13 (the story), heat marginals
6.67/6.69, INSIDE the paired-seed floor, so the artifact says heat does not
move the headline. Magnitude uncertainty rides as Normal(mean, sd) deltas or
MC draws: heat as Normal(-0.15, 0.05) over 20 draws gave 6.61 vs 6.68
fixed-point with sd 0.04pp over draws; where the response is locally linear,
the mean magnitude is adequate and the draw sd is the cheap materiality test.

### Implied-delta inversion (what is the market pricing?)

Market England 11.18 vs model 7.19: brentq inversion says the market prices
England +0.099 strength above the model, one key-player-class upgrade. The
France gap (-7.31pp) is the largest on the board: the market believes
something the results model does not see. Every gap is a research question.

### Triangulation

The squad-value regression (corr 0.94 with fitted strengths, n=40) flags
Colombia as most overrated vs its squad value (+0.22 residual); independently
Colombia carries the largest positive model-vs-market gap (+2.89pp). Two
instruments, same suspect: the canonical edge hunt. Squad value is the single
best-evidenced non-market covariate (Peeters 2018, beats Elo and FIFA rank).

### Group-stage effects read through group lenses

England v Croatia: win 2-0 = +0.78pp title, draw -0.01, loss 0-1 = -1.40 (a
loss costs nearly twice the win's gain). The Mexico altitude case moves group
win 52.2 to 55.0 while title pp moves 0.04: title pp alone hides the action.
Read group-stage stories through qualification and group-win probabilities.

### Two update channels, both material

After a mocked matchday (England 2-0, Argentina upset): the bracket overlay
alone moves England 6.99 to 7.79; refitting moves it further to 8.69. One
group win is worth ~+0.8pp through the bracket and ~+0.9pp through
strengths. The attribution report decomposes both; never re-add by hand what
the refit already priced.

### News-shock calibration table

Backup keeper in (-0.03 strength) = -1.09pp. Mbappe out (-0.12) = France
-3.77pp, Spain +0.59. One-match tactical worry (-0.3 xG) = -0.20pp.

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
univariates from the market, it can be hard to know what caused the changes
in market numbers.

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
