"""Build the master KBO yearly dataset from raw FanGraphs leaderboard exports.

Merges the yearly rate and counting leaderboards on Season + PlayerId, derives
BB%/K% as decimals, ISO, and a BB/K ratio, and tags rows with a player_type
based on known KBO<->MLB crossover players.
"""

import re
from pathlib import Path

import pandas as pd

RAW_DIR = Path(__file__).parent / "raw"
PROCESSED_DIR = Path(__file__).parent / "processed"

RATE_FILE = RAW_DIR / "kbo_yearly_rate.csv"
COUNTING_FILE = RAW_DIR / "kbo_yearly_counting.csv"
OUTPUT_FILE = PROCESSED_DIR / "kbo_master.csv"

# Players who moved from KBO to MLB (or are in KBO now after MLB exposure
# but are primarily tracked as future/current MLB talent).
KBO_TO_MLB = {
    "Jung Hoo Lee",
    "Hyeseong Kim",
    "Ha-seong Kim",
    "Byung-ho Park",
    "Hyun Soo Kim",
    "Kwang-hyun Kim",
    "Hyeon-jong Yang",
}

# Players who came from MLB (or affiliated minor league systems) to play in KBO.
MLB_TO_KBO = {
    "Aaron Altherr",
    "Daz Cameron",
    "Patrick Wisdom",
    "Dixon Machado",
    "Socrates Brito",
    "Yasiel Puig",
}


def normalize_name(name: str) -> str:
    """Lowercase and strip non-alphanumeric characters for fuzzy name matching."""
    return re.sub(r"[^a-z0-9]", "", str(name).lower())


KBO_TO_MLB_NORM = {normalize_name(n) for n in KBO_TO_MLB}
MLB_TO_KBO_NORM = {normalize_name(n) for n in MLB_TO_KBO}


def tag_player_type(name_ascii: str) -> str:
    norm = normalize_name(name_ascii)
    if norm in KBO_TO_MLB_NORM:
        return "KBO_to_MLB"
    if norm in MLB_TO_KBO_NORM:
        return "MLB_to_KBO"
    return "KBO_only"


def main() -> None:
    rate = pd.read_csv(RATE_FILE)
    counting = pd.read_csv(COUNTING_FILE)

    # Columns present in both files describe the same player-season and are
    # identical between the two exports; keep the rate file's copies and drop
    # the duplicates from the counting file before merging.
    shared_cols = ["Name", "NameASCII", "Team", "Age", "PA", "AVG", "MLBAMID"]
    counting_trimmed = counting.drop(columns=shared_cols)

    master = rate.merge(counting_trimmed, on=["Season", "PlayerId"], how="inner")

    # BB% and K% are already expressed as decimals (e.g. 0.1009 == 10.09%) in
    # the raw export, but coerce explicitly in case of percent-string input.
    for col, out_col in [("BB%", "bb_pct"), ("K%", "k_pct")]:
        series = master[col]
        if series.dtype == object:
            series = series.str.rstrip("%").astype(float) / 100.0
        master[out_col] = series.astype(float)

    # Recompute ISO directly from SLG - AVG (matches the FanGraphs ISO column,
    # included here so it's an explicit derived field rather than a passthrough).
    master["iso"] = master["SLG"] - master["AVG"]

    # BB/K ratio derived from the rate-based percentages.
    master["bb_k_ratio"] = master["bb_pct"] / master["k_pct"]

    master["player_type"] = master["NameASCII"].apply(tag_player_type)

    master = master.sort_values(["Season", "Name"]).reset_index(drop=True)

    PROCESSED_DIR.mkdir(parents=True, exist_ok=True)
    master.to_csv(OUTPUT_FILE, index=False)

    print(f"Wrote {OUTPUT_FILE} -> shape {master.shape}")
    print()
    print("player_type counts:")
    print(master["player_type"].value_counts())
    print()
    crossovers = master[master["player_type"] != "KBO_only"]
    print(f"Crossover rows ({len(crossovers)}):")
    print(
        crossovers[
            ["Season", "Name", "NameASCII", "Team", "player_type", "bb_pct", "k_pct", "iso", "bb_k_ratio", "wRC+"]
        ].to_string(index=False)
    )


if __name__ == "__main__":
    main()
