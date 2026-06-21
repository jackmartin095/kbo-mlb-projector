# KBO-to-MLB Projection Model

A statistical framework for projecting which KBO (Korea Baseball Organization) hitters are most likely to succeed as everyday MLB players, built on validated historical crossover data.

## Overview

This project builds a composite scouting model for evaluating KBO hitters against a realistic MLB outcome range, using two anchor groups:

- **Ceiling reference**: KBO players who successfully transitioned to MLB (e.g. Jung Hoo Lee, Hyeseong Kim, Sung-Mun Song)
- **Floor reference**: MLB players who washed out and signed in KBO (e.g. Patrick Wisdom, Daz Cameron, Aaron Altherr)

The model scores current KBO hitters on a composite metric, applies an age adjustment for development runway, and benchmarks each player against both the ceiling and floor groups to produce a defensible projection — not just "good in KBO," but "good in KBO at an age and profile that has historically translated."

## Why this exists

The KBO-to-MLB posting pipeline has produced several successful everyday MLB players in recent years, but there is no public, transparent statistical framework in English for evaluating which current KBO players are most likely to follow that path. This project is an attempt to build one, using publicly available FanGraphs data.

## Methodology

**Data sources**: FanGraphs KBO international leaderboard (year-by-year, 2021–2026) and FanGraphs MLB leaderboards for the crossover validation groups.

**Core metrics**: wRC+, BB%, K%, ISO, Spd — chosen because they are the most stable, translatable indicators of hitting ability across run environments, prioritizing plate discipline and power over batting average or counting stats that are more sensitive to league-context inflation.

**Composite score**: each metric is converted to a z-score relative to the full KBO player pool in the same season, then combined using the following weights:

| Metric | Weight | Rationale |
|---|---|---|
| wRC+ | 30% | Overall offensive value, context-adjusted |
| BB% | 25% | Plate discipline, historically the most translatable skill |
| K% (inverted) | 20% | Contact ability, lower is better |
| ISO | 15% | Raw power |
| Spd | 10% | Athleticism / speed score |

**Age adjustment**: a multiplier is applied to the composite score to account for development runway, since a given statistical profile is more predictive at a younger age:

| Age | Multiplier |
|---|---|
| ≤20 | 1.25x |
| 21–22 | 1.15x |
| 23–24 | 1.05x |
| 25–27 | 1.00x |
| 28–29 | 0.90x |

**Filters applied to the scouting pool**: minimum 300 PA in the most recent qualifying season, age 29 or under, and foreign-born KBO imports excluded (the goal is projecting domestic KBO talent, not players already evaluated by MLB).

**Validation**: the model is checked against the known successful crossover cohort — Jung Hoo Lee and Hyeseong Kim, in particular, rank at or near the top of the KBO-to-MLB validation set using their final pre-transition KBO seasons, which the model was not directly fit to predict.

**Floor/ceiling benchmarking**: average MLB performance (wRC+, BB%, K%, ISO, Spd) is calculated separately for the KBO-to-MLB group (post-transition) and the MLB-to-KBO group (pre-transition, i.e. their MLB performance before washing out to KBO). A current KBO player's adjusted composite score is compared against both benchmarks to contextualize their projection.

## What's in this repo

```
data/
  raw/              FanGraphs CSV exports (KBO leaderboard, year-by-year and career)
  processed/        Cleaned, merged, tagged master dataset and scoring outputs
  crossover/        MLB outcome data for validation/benchmark players
  process_raw.py    Data pipeline: merge, clean, tag crossover players
model/
  projection_score.py   Composite scoring, age adjustment, ceiling/floor benchmarks
scouting_tool/
  scout.py          Command-line scouting report generator for any player in the pool
```

## Usage

Generate a full scouting report for any player in the KBO scouting pool:

```bash
python scouting_tool/scout.py "Player Name"
```

This returns: their most recent qualifying season stat line with z-scores, raw and age-adjusted composite score, percentile rank within the scouting pool, the three closest statistical comparables among validated KBO-to-MLB players, and a positioning verdict against the ceiling/floor MLB outcome benchmarks.

## Current top candidates (as of 2026 season data)

| Player | Age | wRC+ | BB% | K% | ISO | Adj. Score | Percentile |
|---|---|---|---|---|---|---|---|
| Hyun Min Ahn | 21 | 177 | 15.6% | 14.9% | .235 | +1.940 | 99th |
| Do Yeong Kim | 20 | 167 | 10.6% | 17.6% | .300 | +1.866 | 98th |
| Seong-yoon Kim | 26 | 148 | 12.1% | 10.0% | .143 | +1.061 | 97th |

Full board and individual reports available via the scouting tool.

## Limitations

This is a hitter-only model built on a relatively small validation sample (the KBO-to-MLB crossover cohort is fewer than 10 players in the 2021–2026 window), so it should be read as a directional scouting aid rather than a precise forecast. It does not yet account for defensive position, injury history, or pitch-level plate discipline data (O-Swing%, Z-Contact%, SwStr%), which are not available on the public KBO leaderboard and would meaningfully improve the model if incorporated.

## Author

Built by Jack Martin, staff writer at FanGraphs RotoGraphs, based in Incheon, South Korea. Reach out at jackmartin095@gmail.com, on Substack at [@yagoojack](https://yagoojack.substack.com), or on X at [@jack_mariners](https://x.com/jack_mariners).
