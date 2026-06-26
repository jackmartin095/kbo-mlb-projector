# KBO-to-MLB Projection Model

A statistical framework for projecting which KBO (Korea Baseball Organization) hitters are most likely to succeed as everyday MLB players, built on validated historical crossover data.

## Overview

This project builds a composite scouting model for evaluating KBO hitters against a realistic MLB outcome range, using two anchor groups:

- **Ceiling reference**: KBO players who successfully transitioned to MLB (e.g. Jung Hoo Lee, Hyeseong Kim, Sung-Mun Song)
- **Floor reference**: MLB players who washed out and signed in KBO (e.g. Patrick Wisdom, Daz Cameron, Aaron Altherr)

The model scores current KBO hitters on a composite metric built from multiple seasons of data, weights recent performance and younger age more heavily, regresses for sample size, and benchmarks each player against a floor derived from former MLB players. The goal is a defensible projection — not just "good in KBO," but "good in KBO, on a reliable sample, at an age and profile that has historically translated."

## Why this exists

The KBO-to-MLB posting pipeline has produced several successful everyday MLB players in recent years, but there is no public, transparent statistical framework in English for evaluating which current KBO players are most likely to follow that path. This project is an attempt to build one, using publicly available FanGraphs data.

## Methodology

**Data sources**: FanGraphs KBO international leaderboard, year-by-year, 2023-2026, exported at an 80 PA per-season floor. FanGraphs MLB leaderboards supply the crossover validation and floor groups.

**Core metrics**: wRC+, BB%, K%, ISO, Spd - chosen because they are the most stable, translatable indicators of hitting ability across run environments, prioritizing plate discipline and power over batting average or counting stats that are more sensitive to league-context inflation. OBP, SLG, OPS, and wOBA are deliberately excluded as largely redundant with wRC+ and ISO; including them would double-count the same underlying skills.

**Multi-season profiles**: rather than scoring a single season, each player's profile is a recency-weighted aggregate across all their qualifying seasons in the 2023-2026 window. The most recent season is weighted most heavily (50% / 30% / 20% across the three most recent, redistributed proportionally when fewer seasons are available). This rewards consistency and recent form over a single outlier year.

**Composite score**: each metric is converted to a z-score relative to the full qualifying KBO pool, then combined using the following weights:

| Metric | Weight | Rationale |
|---|---|---|
| wRC+ | 30% | Overall offensive value, context-adjusted |
| BB% | 25% | Plate discipline, historically the most translatable skill |
| K% (inverted) | 20% | Contact ability, lower is better |
| ISO | 15% | Raw power |
| Spd | 10% | Athleticism / speed score |

**Sample-size regression**: before scoring, each player's rate stats are regressed toward the pool mean in proportion to sample size, using the standard shrinkage approach common to projection systems like Marcel. A player's own value is trusted as `PA / (PA + K)`, with a regression constant of K=300 (roughly half a season as the 50% trust point). This prevents small-sample standouts from outranking proven players on thin data, while the displayed stat lines remain the player's actual (unregressed) numbers - only the score reflects the regression.

**Age adjustment**: a multiplier is applied to the composite score to account for development runway, since a given statistical profile is more predictive at a younger age:

| Age (most recent season) | Multiplier |
|---|---|
| 20 and under | 1.25x |
| 21-22 | 1.15x |
| 23-24 | 1.05x |
| 25-27 | 1.00x |
| 28-29 | 0.90x |

**Filters**: the scouting pool requires at least 200 combined PA across 2023-2026, an age under 30 in the player's most recent season, and excludes foreign-born KBO imports (the goal is projecting domestic KBO talent, not players already evaluated by MLB).

**Floor benchmarking**: average pre-KBO MLB performance (wRC+, BB%, K%, ISO, Spd) is calculated for the MLB-to-KBO group - players whose MLB careers didn't stick before they signed in Korea. This establishes a floor: a current KBO player should project above this benchmark to be considered a real MLB candidate.

**Validation**: the framework is checked against the known successful crossover cohort. Jung Hoo Lee and Hyeseong Kim rank at or near the top of the KBO-to-MLB validation set using their pre-transition KBO data, which the model was not directly fit to predict.

## What's in this repo

```
data/
  raw/              FanGraphs CSV exports (KBO leaderboard, year-by-year 2023-2026)
  processed/        Cleaned master dataset, scoring outputs, final rankings
  crossover/        MLB outcome data for validation and floor benchmark players
  process_raw.py    Data pipeline: merge, clean, tag crossover players
model/
  projection_score.py   Recency weighting, shrinkage, composite scoring, age adjustment, floor benchmark
scouting_tool/
  scout.py          Command-line scouting report generator for any player in the pool
```

## Usage

Generate a full scouting report for any player in the KBO scouting pool:

```bash
python scouting_tool/scout.py "Player Name"
```

This returns: the player's recency-weighted stat line, their composite score and percentile rank within the scouting pool, the seasons included in their profile, the three closest statistical comparables among validated KBO-to-MLB players, and a positioning verdict against the MLB floor benchmark.

## Limitations

This is a hitter-only model built on a relatively small validation sample (the KBO-to-MLB crossover cohort is fewer than ten players), so it should be read as a directional scouting aid rather than a precise forecast. It does not yet account for defensive position, injury history, or pitch-level plate discipline data (O-Swing%, Z-Contact%, SwStr%), which are not available on the public KBO leaderboard and would meaningfully improve the model if incorporated. The recency weighting favors recent form but cannot fully correct for a player whose role or health has changed mid-window.

The model code, data pipeline, and scouting tool logic are public here. The underlying FanGraphs data isn't included, so it isn't plug-and-play, but the full methodology is visible. A proper interactive version is in the works.

## Author

Built by Jack Martin, staff writer at FanGraphs RotoGraphs, based in Incheon, South Korea. Reach out at jackmartin095@gmail.com, on Substack at [@yagoojack](https://yagoojack.substack.com), or on X at [@jack_mariners](https://x.com/jack_mariners).
