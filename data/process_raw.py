"""Build the master KBO 2023-2026 dataset from raw FanGraphs exports.

Merges the yearly rate and counting leaderboards on Season + PlayerId,
and tags each row as KBO_to_MLB, MLB_to_KBO, or KBO_only.
"""

import re
from pathlib import Path

import pandas as pd

RAW_DIR = Path(__file__).parent / "raw"
PROCESSED_DIR = Path(__file__).parent / "processed"

RATE_FILE = RAW_DIR / "kbo_yearly_rate.csv"
COUNTING_FILE = RAW_DIR / "kbo_yearly_counting.csv"
OUTPUT_FILE = PROCESSED_DIR / "kbo_master.csv"

KBO_TO_MLB = {
    "Jung Hoo Lee",
    "Hyeseong Kim",
    "Ha-seong Kim",
    "Byung-ho Park",
    "Hyun Soo Kim",
    "Kwang-hyun Kim",
    "Hyeon-jong Yang",
    "Sung-Mun Song",
}

MLB_TO_KBO = {
    "Aaron Altherr",
    "Daz Cameron",
    "Patrick Wisdom",
    "Dixon Machado",
    "Socrates Brito",
    "Yasiel Puig",
}


def _norm(name: str) -> str:
    return re.sub(r"[^a-z0-9]", "", str(name).lower())


_KBO_TO_MLB_NORM = {_norm(n) for n in KBO_TO_MLB}
_MLB_TO_KBO_NORM = {_norm(n) for n in MLB_TO_KBO}


def tag_player_type(name_ascii: str) -> str:
    n = _norm(name_ascii)
    if n in _KBO_TO_MLB_NORM:
        return "KBO_to_MLB"
    if n in _MLB_TO_KBO_NORM:
        return "MLB_to_KBO"
    return "KBO_only"


def main() -> None:
    rate = pd.read_csv(RATE_FILE)
    counting = pd.read_csv(COUNTING_FILE)

    merge_keys = ["Season", "PlayerId", "Team"]
    shared_cols = ["Name", "NameASCII", "Age", "PA", "AVG", "MLBAMID"]
    counting_trimmed = counting.drop(columns=shared_cols)
    master = rate.merge(counting_trimmed, on=merge_keys, how="inner")

    # Traded players have split rows per team; keep the highest-PA row per
    # player-season so rate stats (wRC+, BB%, etc.) reflect their primary stint.
    # Sum PA across stints so the total is accurate.
    pa_totals = master.groupby(["Season", "PlayerId"])["PA"].transform("sum")
    idx = master.groupby(["Season", "PlayerId"])["PA"].idxmax()
    master = master.loc[idx].copy()
    master["PA"] = pa_totals.loc[idx].values

    master["player_type"] = master["NameASCII"].apply(tag_player_type)
    master = master.sort_values(["Season", "Name"]).reset_index(drop=True)

    PROCESSED_DIR.mkdir(parents=True, exist_ok=True)
    master.to_csv(OUTPUT_FILE, index=False)

    print(f"Wrote {OUTPUT_FILE} -> shape {master.shape}")
    print(f"\nplayer_type counts:\n{master['player_type'].value_counts()}")
    crossovers = master[master["player_type"] != "KBO_only"]
    print(f"\nCrossover rows ({len(crossovers)}):")
    print(crossovers[["Season", "NameASCII", "Team", "player_type", "PA", "wRC+"]].to_string(index=False))


if __name__ == "__main__":
    main()
