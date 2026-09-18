# KBO-to-MLB Projection Model

A statistical framework for projecting which KBO (Korea Baseball Organization) hitters are most likely to succeed as everyday MLB players, built on validated historical crossover data.

Live app: https://kbo-mlb-projector-hcpteg3qzkempqsm8tcd6i.streamlit.app/

## Overview

This project builds a composite scouting model for evaluating KBO hitters against a realistic MLB outcome range, using two anchor groups:

- **Ceiling reference**: KBO players who successfully transitioned to MLB (e.g. Jung Hoo Lee, Hyeseong Kim, Sung-Mun Song)
- **Floor reference**: MLB players who washed out and signed in KBO (e.g. Patrick Wisdom, Daz Cameron, Aaron Altherr)

The model scores current KBO hitters on a career composite built from multiple seasons of data, regresses for sample size, adjusts for age, and benchmarks each player against a floor derived from former MLB players and a ceiling derived from confirmed KBO-to-MLB transitions. A separate Trend calculation flags who is improving or declining relative to their own track record, and a Hot Right Now view scores players on current-season form alone. The goal is a defensible projection, not just "good in KBO," but "good in KBO, on a reliable sample, at an age and profile that has historically translated," with recent form and momentum surfaced as their own explicit signals rather than folded into one blended number.

## Why this exists

The KBO-to-MLB posting pipeline has produced several successful everyday MLB players in recent years, but there is no public, transparent statistical framework in English for evaluating which current KBO players are most likely to follow that path. This project is an attempt to build one, using publicly available FanGraphs data.

## Methodology

**Data sources**: FanGraphs KBO international leaderboard, year-by-year, 2023-2026, exported at an 80 PA per-season floor. FanGraphs MLB leaderboards supply the crossover validation and floor groups.

**Core metrics**: wRC+, BB%, K%, ISO, Spd, chosen because they are the most stable, translatable indicators of hitting ability across run environments, prioritizing plate discipline and power over batting average or counting stats that are more sensitive to league-context inflation. OBP, SLG, OPS, and wOBA are deliberately excluded as largely redundant with wRC+ and ISO, including them would double-count the same underlying skills.

**Career aggregate**: each player's profile is a PA-weighted average across all their qualifying seasons in the 2023-2026 window, so a season contributes to the aggregate in proportion to how many plate appearances it represents. This mirrors how FanGraphs itself calculates multi-year leaderboards and avoids over-weighting small partial seasons. All seasons are weighted equally on a per-PA basis in this aggregate; recency is deliberately handled elsewhere rather than blended into this number (see Trend, below), so that "how good has this player been" and "is this player improving" stay legible as separate signals.

**Composite score**: each metric is converted to a z-score relative to the full qualifying KBO pool, then combined using the following weights:

| Metric | Weight | Rationale |
|---|---|---|
| wRC+ | 30% | Overall offensive value, context-adjusted |
| BB% | 25% | Plate discipline, historically the most translatable skill |
| ISO | 20% | Raw power. MLB pitchers attack hitters who show no extra-base threat, so power functions closer to a gating requirement than a bonus at the major league level |
| K% (inverted) | 15% | Contact ability, lower is better |
| Spd | 10% | Athleticism / speed score |

**Sample-size regression**: before scoring, each player's rate stats are regressed toward the pool mean in proportion to sample size, using the standard shrinkage approach common to projection systems like Marcel. A player's own value is trusted as `PA / (PA + K)`, with a regression constant of K=300 (roughly half a season as the 50% trust point). This prevents small-sample standouts from outranking proven players on thin data, while the displayed stat lines remain the player's actual, unregressed numbers, only the composite score reflects the regression.

**Age adjustment**: a multiplier is applied to the composite score to account for development runway, since a given statistical profile is more predictive at a younger age:

| Age (most recent season) | Multiplier |
|---|---|
| 20 and under | 1.25x |
| 21-22 | 1.15x |
| 23-24 | 1.05x |
| 25-27 | 1.00x |
| 28-29 | 0.90x |

**Filters**: the scouting pool requires at least 200 combined PA across 2023-2026, an age under 30 in the player's most recent season, and excludes foreign-born KBO imports (the goal is projecting domestic KBO talent, not players already evaluated by MLB).

**Trend and Trajectory**: computed separately from the career composite so a single outlier season cannot distort a player's overall standing, but momentum is still visible where it exists. Trend compares a player's most recent season, scored on its own against that season's full pool, to a recency-weighted composite of their prior seasons (weighted 50% / 30% / 20% by recency, redistributed proportionally with fewer seasons available). Trajectory labels are assigned by percentile within the qualifying pool: Rising (top 20% of trend scores), Improving (50th-80th percentile), Stable (20th-50th percentile), Declining (bottom 20%).

**Hot Right Now**: a separate view scoring players on 2026 in-season stats only, no career aggregation, no shrinkage, no age multiplier, z-scored against every player with 100+ PA in 2026. It answers a different question than the main board: who is performing best right now, independent of career history. Each player's rank here is also compared against their rank on the main board, so a large gap between the two surfaces players whose current form has outrun their track record.

**Floor benchmarking**: average pre-KBO MLB performance (wRC+, BB%, K%, ISO, Spd) is calculated for the MLB-to-KBO group, players whose MLB careers didn't stick before they signed in Korea. This establishes a floor: a current KBO player should project above this benchmark to be considered a real MLB candidate. As of the most recent data refresh this floor sits at roughly 65.8 wRC+.

**Ceiling benchmarking**: average post-transition MLB performance for the KBO-to-MLB group, calculated the same way and pulled dynamically from the same crossover dataset used for validation, so it updates as more transition data becomes available rather than staying fixed to a number from an earlier data pull.

**Validation**: the framework is checked against the known successful crossover cohort. Jung Hoo Lee and Sung-Mun Song both rank near the top of the KBO-to-MLB validation set using their pre-transition KBO data, which the model was not directly fit to predict.

## What's in this repo

```
data/
  raw/              FanGraphs CSV exports (KBO leaderboard, year-by-year 2023-2026)
  processed/        Cleaned master dataset, scoring outputs, final rankings
  crossover/        MLB outcome data for validation and floor/ceiling benchmark players
  process_raw.py    Data pipeline: merge, clean, tag crossover players
model/
  projection_score.py   Career aggregate, shrinkage, composite scoring, age adjustment, Trend calculation, floor/ceiling benchmarks
scouting_tool/
  scout.py          Command-line scouting report generator for any player in the pool
  app.py            Streamlit web app: Methodology, Board, Player Deep-Dive, Compare, and Hot Right Now pages
```

## Usage

The live app (linked above) is the primary way to use the model: a ranked board, individual player deep-dives with radar charts and comparables, a multi-player comparison view, and the Hot Right Now current-form leaderboard.

For a command-line scouting report on any player in the pool:

```bash
python scouting_tool/scout.py "Player Name"
```

This returns the player's career-aggregate stat line, their composite score and percentile rank within the scouting pool, the seasons included in their profile, Trend and Trajectory, the three closest statistical comparables among validated KBO-to-MLB players, and a positioning verdict against the MLB floor and ceiling benchmarks.

## Limitations

This is a hitter-only model built on a relatively small validation sample (the KBO-to-MLB crossover cohort remains fewer than ten players), so it should be read as a directional scouting aid rather than a precise forecast. It does not yet account for defensive position, injury history, or pitch-level plate discipline data (O-Swing%, Z-Contact%, SwStr%), which are not available on the public KBO leaderboard and would meaningfully improve the model if incorporated. The career aggregate weights all qualifying seasons equally by plate appearances rather than favoring recent ones, so a player whose role or health has changed mid-window is better read through the separate Trend and Hot Right Now views than through the main composite alone.

The model code, data pipeline, and scouting tool logic are public here. The underlying FanGraphs data isn't included, so it isn't plug-and-play, but the full methodology is visible.

## Author

Built by Jack Martin, baseball columnist at FanGraphs RotoGraphs, based in Seoul, South Korea. Reach out at jackmartin095@gmail.com, on Substack at [@yagoojack](https://yagoojack.substack.com), or on X at [@jack_mariners](https://x.com/jack_mariners).
