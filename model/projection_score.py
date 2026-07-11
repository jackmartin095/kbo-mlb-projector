"""KBO→MLB composite projection scores (2023-2026 data).

KBO_to_MLB players: scored on their final KBO season (per-season z-scores).
KBO_only players: PA-weighted career aggregate across all 2023-2026
seasons, z-scored across the qualifying pool's aggregated profiles.

Qualifying: 200+ combined PA across 2023-2026, age < 30 in most recent season.
"""

import re
from pathlib import Path

import numpy as np
import pandas as pd

PROCESSED_DIR = Path(__file__).parent.parent / "data" / "processed"
CROSSOVER_DIR = Path(__file__).parent.parent / "data" / "crossover"
MASTER_FILE = PROCESSED_DIR / "kbo_master.csv"
MLB_OUTCOMES_FILE = CROSSOVER_DIR / "mlb_outcomes.csv"

TO_MLB_OUTPUT = PROCESSED_DIR / "kbo_to_mlb_projection.csv"
SCOUTING_POOL_OUTPUT = PROCESSED_DIR / "kbo_only_scouting_pool.csv"
SCOUTING_POOL_FILTERED_OUTPUT = PROCESSED_DIR / "kbo_only_scouting_pool_filtered.csv"

MIN_CAREER_PA = 200
MAX_AGE = 29

METRICS = {
    "wRC+": (0.30, False),
    "BB%":  (0.25, False),
    "K%":   (0.20, True),
    "ISO":  (0.15, False),
    "Spd":  (0.10, False),
}

RAW_METRICS = list(METRICS.keys())

AGE_MULTIPLIERS = [
    (20, 1.25),
    (22, 1.15),
    (24, 1.05),
    (27, 1.00),
    (29, 0.90),
]

KOREAN_SURNAMES = {
    "kim", "lee", "park", "choi", "jung", "jeong", "chung", "kang", "jo", "cho",
    "yoon", "yun", "jang", "chang", "lim", "im", "yim", "han", "oh", "seo", "suh",
    "shin", "sin", "kwon", "hwang", "ahn", "an", "song", "yoo", "yu", "ryu",
    "hong", "moon", "mun", "yang", "bae", "pae", "baek", "paek", "heo", "huh",
    "hur", "nam", "sim", "shim", "noh", "roh", "no", "ha", "kwak", "gwak",
    "sung", "seong", "cha", "joo", "ju", "woo", "min", "gu", "koo", "goo",
    "jin", "ji", "pyo", "tak", "yeom", "eom", "um", "gong", "bang", "pang",
    "tae", "son", "chae", "go", "ko", "na", "ra", "rha", "choo", "chu",
    "jeon", "chun", "cheon", "byun", "pyun",
}

FOREIGN_PLAYERS = {
    "Austin Dean", "Mel Rojas Jr.", "Yonathan Perlaza", "Socrates Brito",
    "Dixon Machado", "Aaron Altherr", "Daz Cameron", "Patrick Wisdom",
    "Yasiel Puig", "Henry Ramos",
}

NAME_SUFFIXES = {"jr", "sr", "ii", "iii", "iv"}


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def age_multiplier(age: int) -> float:
    for max_age, mult in AGE_MULTIPLIERS:
        if age <= max_age:
            return mult
    return 0.90


def _format_seasons(seasons: list[int]) -> str:
    s = sorted(seasons)
    if len(s) == 1:
        return f"{s[0]} only"
    return f"{s[0]}-{s[-1]}"


def is_likely_korean(name_ascii: str) -> bool:
    tokens = re.split(r"[\s-]+", str(name_ascii).strip())
    tokens = [t for t in tokens if t.rstrip(".").lower() not in NAME_SUFFIXES]
    if not tokens:
        return False
    surname = re.sub(r"[^a-z]", "", tokens[-1].lower())
    return surname in KOREAN_SURNAMES


# ---------------------------------------------------------------------------
# Per-season z-scores (used for KBO_to_MLB)
# ---------------------------------------------------------------------------

def add_season_zscores(df: pd.DataFrame) -> pd.DataFrame:
    df = df.copy()
    for metric in METRICS:
        mean = df.groupby("Season")[metric].transform("mean")
        std = df.groupby("Season")[metric].transform("std")
        df[f"z_{metric}"] = (df[metric] - mean) / std
    return df


def add_composite(df: pd.DataFrame) -> pd.DataFrame:
    df = df.copy()
    score = pd.Series(0.0, index=df.index)
    for metric, (weight, invert) in METRICS.items():
        z = df[f"z_{metric}"]
        score += weight * (-z if invert else z)
    df["composite_score"] = score
    df["age_multiplier"] = df["Age"].apply(age_multiplier)
    df["adjusted_composite"] = df["composite_score"] * df["age_multiplier"]
    return df


# ---------------------------------------------------------------------------
# Pool-wide z-scores (used for KBO_only aggregates)
# ---------------------------------------------------------------------------

REGRESSION_K = 300


def apply_shrinkage(df: pd.DataFrame) -> pd.DataFrame:
    """Regress each metric toward the pool mean based on PA (Marcel-style).

    Stores shrunk values in shrunk_<metric> columns; raw columns are preserved.
    """
    df = df.copy()
    for metric in METRICS:
        pool_mean = df[metric].mean()
        reliability = df["PA"] / (df["PA"] + REGRESSION_K)
        df[f"shrunk_{metric}"] = pool_mean + (df[metric] - pool_mean) * reliability
    return df


def add_poolwide_zscores(df: pd.DataFrame, use_shrunk: bool = False) -> pd.DataFrame:
    df = df.copy()
    for metric in METRICS:
        src = f"shrunk_{metric}" if use_shrunk else metric
        mean = df[src].mean()
        std = df[src].std()
        df[f"z_{metric}"] = (df[src] - mean) / std
    return df


# ---------------------------------------------------------------------------
# Career aggregate
# ---------------------------------------------------------------------------

def aggregate_profiles(df: pd.DataFrame) -> pd.DataFrame:
    """One PA-weighted row per player. Filters: 200+ career PA, age < 30."""
    rows = []
    for pid, grp in df.groupby("PlayerId"):
        total_pa = int(grp["PA"].sum())
        if total_pa < MIN_CAREER_PA:
            continue
        grp = grp.sort_values("Season", ascending=False)
        latest = grp.iloc[0]
        if int(latest["Age"]) > MAX_AGE:
            continue

        pa_weights = grp["PA"].values.astype(float)
        agg = {col: float(np.average(grp[col].values, weights=pa_weights)) for col in RAW_METRICS}
        agg["PA"] = total_pa
        agg["Name"] = latest["Name"]
        agg["NameASCII"] = latest["NameASCII"]
        agg["Season"] = int(latest["Season"])
        agg["Team"] = latest["Team"]
        agg["Age"] = int(latest["Age"])
        agg["PlayerId"] = pid
        agg["player_type"] = latest["player_type"]
        agg["seasons_used"] = _format_seasons(grp["Season"].tolist())
        rows.append(agg)
    return pd.DataFrame(rows)


# ---------------------------------------------------------------------------
# Filters
# ---------------------------------------------------------------------------

def remove_foreign(df: pd.DataFrame) -> pd.DataFrame:
    df = df[~df["NameASCII"].isin(FOREIGN_PLAYERS)]
    df = df[df["NameASCII"].apply(is_likely_korean)]
    return df


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

DISPLAY_COLS = [
    "Name", "NameASCII", "Season", "Team", "Age", "PA",
    "wRC+", "BB%", "K%", "ISO", "Spd",
    "z_wRC+", "z_BB%", "z_K%", "z_ISO", "z_Spd",
    "composite_score", "age_multiplier", "adjusted_composite",
    "player_type",
]

RANKINGS_CSV = PROCESSED_DIR / "kbo_rankings_final.csv"
RANKINGS_MD = PROCESSED_DIR / "kbo_rankings_final.md"
SCORED_POOL_CSV = PROCESSED_DIR / "kbo_scored_pool.csv"

RANKING_COLS = ["Rank", "Name", "Team", "seasons_used", "PA", "Age",
                "wRC+", "BB%", "K%", "ISO", "Spd",
                "adjusted_composite", "Percentile"]


def build_rankings(df: pd.DataFrame, pool_size: int) -> pd.DataFrame:
    out = df[["Name", "Team", "seasons_used", "PA", "Age",
              "wRC+", "BB%", "K%", "ISO", "Spd",
              "z_wRC+", "z_BB%", "z_K%", "z_ISO", "z_Spd",
              "adjusted_composite"]].copy()
    out.insert(0, "Rank", range(1, len(out) + 1))
    out["Percentile"] = out["adjusted_composite"].apply(
        lambda v: (df["adjusted_composite"] < v).sum() / pool_size * 100
    )
    return out


def to_markdown(df: pd.DataFrame) -> str:
    lines = []
    headers = ["Rank", "Name", "Team", "Seasons", "PA", "Age",
               "wRC+", "BB%", "K%", "ISO", "Spd", "Adj Score", "Pctile"]
    lines.append("| " + " | ".join(headers) + " |")
    lines.append("|" + "|".join(["---:" if i != 1 and i != 2 and i != 3 else "---" for i in range(len(headers))]) + "|")
    for _, r in df.iterrows():
        row = [
            f"{int(r['Rank'])}",
            r["Name"],
            r["Team"].replace(" (KBO)", ""),
            r["seasons_used"],
            f"{int(r['PA'])}",
            f"{int(r['Age'])}",
            f"{r['wRC+']:.1f}",
            f"{r['BB%']:.1%}",
            f"{r['K%']:.1%}",
            f"{r['ISO']:.3f}",
            f"{r['Spd']:.1f}",
            f"{r['adjusted_composite']:+.3f}",
            f"{r['Percentile']:.1f}",
        ]
        lines.append("| " + " | ".join(row) + " |")
    return "\n".join(lines)


def main() -> None:
    master = pd.read_csv(MASTER_FILE)

    # --- KBO_to_MLB: per-season z-scores, final KBO season ---
    scored = add_season_zscores(master)
    scored = add_composite(scored)

    to_mlb = scored[scored["player_type"] == "KBO_to_MLB"]
    idx = to_mlb.groupby("PlayerId")["Season"].idxmax()
    to_mlb = to_mlb.loc[idx].sort_values("composite_score", ascending=False).reset_index(drop=True)

    # --- KBO_only: career aggregate, shrink toward pool mean, then z-score ---
    kbo_raw = master[master["player_type"] == "KBO_only"]
    pool = aggregate_profiles(kbo_raw)
    pool = apply_shrinkage(pool)
    pool = add_poolwide_zscores(pool, use_shrunk=True)
    pool = add_composite(pool)
    pool = pool.sort_values("adjusted_composite", ascending=False).reset_index(drop=True)

    pool_filtered = remove_foreign(pool)
    pool_size = len(pool_filtered)

    # Build full ranked pool and top 15
    full_rankings = build_rankings(pool_filtered.reset_index(drop=True), pool_size)
    top15 = full_rankings.head(15).copy()

    # --- Floor benchmark from MLB outcomes ---
    outcomes = pd.read_csv(MLB_OUTCOMES_FILE)
    floor_group = outcomes[outcomes["group"] == "MLB_to_KBO"]
    floor_stats = floor_group[["wRC+", "BB%", "K%", "ISO", "Spd"]].mean()

    # --- Write outputs ---
    PROCESSED_DIR.mkdir(parents=True, exist_ok=True)

    to_mlb_cols = [c for c in DISPLAY_COLS if c in to_mlb.columns]
    to_mlb[to_mlb_cols].to_csv(TO_MLB_OUTPUT, index=False)

    pool_cols = [c for c in DISPLAY_COLS if c in pool.columns] + ["seasons_used"]
    pool[pool_cols].to_csv(SCOUTING_POOL_OUTPUT, index=False)
    top15.to_csv(SCOUTING_POOL_FILTERED_OUTPUT, index=False)

    full_rankings.to_csv(RANKINGS_CSV, index=False)
    full_rankings.to_csv(SCORED_POOL_CSV, index=False)

    md_content = (
        f"# KBO-Only Scouting Rankings (2023-2026)\n\n"
        f"PA-weighted career aggregate | K={REGRESSION_K} shrinkage | Age ≤ {MAX_AGE}\n\n"
        f"Qualifying pool: {pool_size} players | Min {MIN_CAREER_PA} career PA\n\n"
        f"**Floor benchmark (MLB→KBO avg):** wRC+ {floor_stats['wRC+']:.1f} | "
        f"BB% {floor_stats['BB%']:.1%} | K% {floor_stats['K%']:.1%} | "
        f"ISO {floor_stats['ISO']:.3f} | Spd {floor_stats['Spd']:.1f}\n\n"
        f"## Top 15\n\n{to_markdown(top15)}\n\n"
        f"## Full Qualifying Pool ({pool_size} players)\n\n{to_markdown(full_rankings)}\n"
    )
    RANKINGS_MD.write_text(md_content)

    # --- Print results ---
    print(f"Wrote {TO_MLB_OUTPUT} -> shape {to_mlb.shape}")
    print(f"Wrote {SCOUTING_POOL_OUTPUT} -> shape {pool.shape}")
    print(f"Wrote {RANKINGS_CSV} -> {len(full_rankings)} players")
    print(f"Wrote {RANKINGS_MD}")

    print(f"\nQualifying KBO_only pool size: {len(pool)} players")
    print(f"After foreign-player filter:   {pool_size} players\n")

    print("=== KBO_to_MLB projection ranking (final KBO season) ===")
    print(to_mlb[["Name", "Season", "Team", "wRC+", "BB%", "K%", "ISO", "Spd", "composite_score"]].to_string(index=False))

    print(f"\n=== Floor benchmark: MLB→KBO group average (pre-KBO MLB stats) ===")
    print(f"  wRC+ {floor_stats['wRC+']:.1f}  |  BB% {floor_stats['BB%']:.1%}  |  "
          f"K% {floor_stats['K%']:.1%}  |  ISO {floor_stats['ISO']:.3f}  |  Spd {floor_stats['Spd']:.1f}")

    print(f"\n=== Top 15 KBO_only (career-aggregate, 200+ PA, age ≤ {MAX_AGE}) ===")
    print(top15.to_string(index=False))


if __name__ == "__main__":
    main()
