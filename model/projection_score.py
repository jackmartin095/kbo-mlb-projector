"""Composite KBO->MLB projection scores.

For each player, take their final available KBO season and z-score a set of
performance metrics relative to the full KBO player pool *for that season*.
The z-scores are combined into a weighted composite_score.

Two output tables are produced:
  - kbo_to_mlb_projection.csv: KBO_to_MLB players, scored on their final KBO season.
  - kbo_only_scouting_pool.csv: KBO_only players, scored on their most recent season.
"""

import re
from pathlib import Path

import pandas as pd

PROCESSED_DIR = Path(__file__).parent.parent / "data" / "processed"
MASTER_FILE = PROCESSED_DIR / "kbo_master.csv"

TO_MLB_OUTPUT = PROCESSED_DIR / "kbo_to_mlb_projection.csv"
SCOUTING_POOL_OUTPUT = PROCESSED_DIR / "kbo_only_scouting_pool.csv"
SCOUTING_POOL_FILTERED_OUTPUT = PROCESSED_DIR / "kbo_only_scouting_pool_filtered.csv"

# Players 30 or older are removed from the scouting pool (long-shot MLB targets).
MAX_AGE = 29

# Player-seasons below this PA are dropped from the scouting pool before scoring
# (e.g. an in-progress 2026 season shouldn't be treated as a player's "most recent season").
MIN_PA = 300

# Known foreign-born KBO imports to remove from the scouting pool, regardless
# of what the surname-based heuristic below would say.
FOREIGN_PLAYERS = {
    "Austin Dean",
    "Mel Rojas Jr.",
    "Yonathan Perlaza",
    "Socrates Brito",
    "Dixon Machado",
    "Aaron Altherr",
    "Daz Cameron",
    "Patrick Wisdom",
    "Yasiel Puig",
}

# Romanized Korean surnames, used to catch any other foreign players whose
# NameASCII (formatted "Given Name(s) Surname") doesn't end in a Korean surname.
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

NAME_SUFFIXES = {"jr", "sr", "ii", "iii", "iv"}

# metric -> (weight, invert)
METRICS = {
    "wRC+": (0.30, False),
    "bb_pct": (0.25, False),
    "k_pct": (0.20, True),
    "iso": (0.15, False),
    "Spd": (0.10, False),
}

DISPLAY_COLS = [
    "Name",
    "NameASCII",
    "Season",
    "Team",
    "Age",
    "PA",
    "wRC+",
    "bb_pct",
    "k_pct",
    "iso",
    "Spd",
    "z_wRC+",
    "z_bb_pct",
    "z_k_pct",
    "z_iso",
    "z_Spd",
    "composite_score",
    "age_multiplier",
    "adjusted_composite",
    "player_type",
]

# Age -> multiplier brackets
AGE_MULTIPLIERS = [
    (20, 1.25),
    (22, 1.15),
    (24, 1.05),
    (27, 1.00),
    (29, 0.90),
]


def age_multiplier(age: float) -> float:
    for max_age, mult in AGE_MULTIPLIERS:
        if age <= max_age:
            return mult
    return 0.90  # 28-29 fallback (shouldn't reach here given MAX_AGE=29)


def add_zscores(df: pd.DataFrame) -> pd.DataFrame:
    """Add per-season z-score columns for each metric, using the full KBO pool."""
    df = df.copy()
    for metric in METRICS:
        season_mean = df.groupby("Season")[metric].transform("mean")
        season_std = df.groupby("Season")[metric].transform("std")
        df[f"z_{metric}"] = (df[metric] - season_mean) / season_std
    return df


def add_composite_score(df: pd.DataFrame) -> pd.DataFrame:
    df = df.copy()
    score = pd.Series(0.0, index=df.index)
    for metric, (weight, invert) in METRICS.items():
        z = df[f"z_{metric}"]
        if invert:
            z = -z
        score = score + weight * z
    df["composite_score"] = score
    df["age_multiplier"] = df["Age"].apply(age_multiplier)
    df["adjusted_composite"] = df["composite_score"] * df["age_multiplier"]
    return df


def latest_season_per_player(df: pd.DataFrame) -> pd.DataFrame:
    idx = df.groupby("PlayerId")["Season"].idxmax()
    return df.loc[idx]


def is_likely_korean(name_ascii: str) -> bool:
    """Heuristic: NameASCII is "Given Name(s) Surname" -- check the surname
    token against a list of common romanized Korean surnames."""
    tokens = re.split(r"[\s-]+", str(name_ascii).strip())
    tokens = [t for t in tokens if t.rstrip(".").lower() not in NAME_SUFFIXES]
    if not tokens:
        return False
    surname = re.sub(r"[^a-z]", "", tokens[-1].lower())
    return surname in KOREAN_SURNAMES


def apply_scouting_filters(df: pd.DataFrame) -> pd.DataFrame:
    """Remove players 30+ and known/likely foreign imports from the scouting pool."""
    df = df[df["Age"] < MAX_AGE + 1]
    df = df[~df["Name"].isin(FOREIGN_PLAYERS)]
    df = df[~df["NameASCII"].isin(FOREIGN_PLAYERS)]
    df = df[df["NameASCII"].apply(is_likely_korean)]
    return df


def main() -> None:
    master = pd.read_csv(MASTER_FILE)

    # z-scores computed against the full player pool for each season.
    scored = add_zscores(master)
    scored = add_composite_score(scored)

    # KBO_to_MLB players, final KBO season.
    to_mlb = scored[scored["player_type"] == "KBO_to_MLB"]
    to_mlb = latest_season_per_player(to_mlb)
    to_mlb = to_mlb.sort_values("composite_score", ascending=False).reset_index(drop=True)

    # KBO_only players, most recent qualifying (PA >= MIN_PA) season -- the scouting pool.
    kbo_only = scored[scored["player_type"] == "KBO_only"]
    kbo_only = kbo_only[kbo_only["PA"] >= MIN_PA]
    kbo_only = latest_season_per_player(kbo_only)
    kbo_only = kbo_only.sort_values("adjusted_composite", ascending=False).reset_index(drop=True)

    # Scouting pool with age cap + foreign-player filter applied.
    kbo_only_filtered = apply_scouting_filters(kbo_only)
    top15 = kbo_only_filtered.head(15).reset_index(drop=True)
    top15_out = top15[
        ["Name", "Season", "Age", "PA", "wRC+", "bb_pct", "k_pct", "iso", "Spd",
         "composite_score", "age_multiplier", "adjusted_composite"]
    ].rename(columns={"bb_pct": "BB%", "k_pct": "K%", "iso": "ISO"})
    top15_out.insert(0, "Rank", range(1, len(top15_out) + 1))

    PROCESSED_DIR.mkdir(parents=True, exist_ok=True)
    to_mlb[DISPLAY_COLS].to_csv(TO_MLB_OUTPUT, index=False)
    kbo_only[DISPLAY_COLS].to_csv(SCOUTING_POOL_OUTPUT, index=False)
    top15_out.to_csv(SCOUTING_POOL_FILTERED_OUTPUT, index=False)

    print(f"Wrote {TO_MLB_OUTPUT} -> shape {to_mlb.shape}")
    print(f"Wrote {SCOUTING_POOL_OUTPUT} -> shape {kbo_only.shape}")
    print(f"Wrote {SCOUTING_POOL_FILTERED_OUTPUT} -> shape {top15_out.shape}")
    print()

    print("=== KBO_to_MLB projection ranking (final KBO season) ===")
    print(
        to_mlb[["Name", "Season", "Team", "wRC+", "bb_pct", "k_pct", "iso", "Spd", "composite_score"]].to_string(
            index=False
        )
    )
    print()

    print(
        f"=== Top 15 KBO_only scouting candidates "
        f"(Age <= {MAX_AGE}, PA >= {MIN_PA}, foreign imports removed) ==="
    )
    print(top15_out.to_string(index=False))


if __name__ == "__main__":
    main()
