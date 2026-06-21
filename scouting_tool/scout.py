"""Scouting report generator for KBO players.

Usage:
    python scouting_tool/scout.py "Hyun Min Ahn"
"""

import sys
from pathlib import Path

import numpy as np
import pandas as pd

PROCESSED_DIR = Path(__file__).parent.parent / "data" / "processed"
CROSSOVER_DIR = Path(__file__).parent.parent / "data" / "crossover"
SCOUTING_POOL = PROCESSED_DIR / "kbo_only_scouting_pool.csv"
KBO_TO_MLB = PROCESSED_DIR / "kbo_to_mlb_projection.csv"
MLB_OUTCOMES = CROSSOVER_DIR / "mlb_outcomes.csv"

Z_COLS = ["z_wRC+", "z_bb_pct", "z_k_pct", "z_iso", "z_Spd"]


def find_player(df: pd.DataFrame, query: str) -> pd.Series | None:
    """Case-insensitive substring match on Name or NameASCII."""
    q = query.lower().strip()
    mask = (
        df["Name"].str.lower().str.contains(q, regex=False)
        | df["NameASCII"].str.lower().str.contains(q, regex=False)
    )
    hits = df[mask]
    if hits.empty:
        return None
    if len(hits) > 1:
        exact = hits[hits["NameASCII"].str.lower() == q]
        if not exact.empty:
            return exact.iloc[0]
        print(f"Multiple matches found — using first: {hits['Name'].tolist()}")
    return hits.iloc[0]


def percentile_rank(series: pd.Series, value: float) -> float:
    return (series < value).sum() / len(series) * 100


def euclidean_distance(row_a: pd.Series, row_b: pd.Series) -> float:
    return float(np.sqrt(((row_a[Z_COLS].values - row_b[Z_COLS].values) ** 2).sum()))


def similarity_matches(player: pd.Series, comps: pd.DataFrame, n: int = 3) -> pd.DataFrame:
    distances = comps.apply(lambda row: euclidean_distance(player, row), axis=1)
    idx = distances.nsmallest(n).index
    result = comps.loc[idx].copy()
    result["distance"] = distances[idx]
    return result


def mlb_benchmarks(outcomes: pd.DataFrame) -> dict:
    """Compute avg MLB stats for each group."""
    stat_cols = ["wRC+", "BB%", "K%", "ISO", "Spd"]
    return {group: gdf[stat_cols].mean() for group, gdf in outcomes.groupby("group")}


def fmt_pct(v: float) -> str:
    return f"{v:.1%}"


def print_report(
    player: pd.Series,
    pool: pd.DataFrame,
    comps: pd.DataFrame,
    outcomes: pd.DataFrame,
) -> None:
    raw_score = player["composite_score"]
    mult = player["age_multiplier"]
    adj_score = player["adjusted_composite"]

    # Percentile rank on adjusted_composite
    pct = percentile_rank(pool["adjusted_composite"], adj_score)

    matches = similarity_matches(player, comps)
    benchmarks = mlb_benchmarks(outcomes)
    ceiling = benchmarks.get("KBO_to_MLB")
    floor = benchmarks.get("MLB_to_KBO")

    # KBO→MLB ceiling benchmark scores (adjusted)
    kbo_to_mlb_adj_avg = comps["adjusted_composite"].mean()
    kbo_to_mlb_adj_min = comps["adjusted_composite"].min()

    sep = "=" * 60

    print()
    print(sep)
    print(f"  SCOUTING REPORT: {player['Name']}")
    print(sep)

    # --- Stat line ---
    print(f"\n  Season: {int(player['Season'])}  |  Team: {player['Team']}  |  Age: {int(player['Age'])}")
    print(f"\n  {'Metric':<12} {'Raw':>8}  {'Z-Score':>8}")
    print(f"  {'-'*32}")
    stats = [
        ("PA",    f"{int(player['PA'])}",          ""),
        ("wRC+",  f"{player['wRC+']:.1f}",          f"{player['z_wRC+']:+.2f}"),
        ("BB%",   fmt_pct(player["bb_pct"]),         f"{player['z_bb_pct']:+.2f}"),
        ("K%",    fmt_pct(player["k_pct"]),          f"{player['z_k_pct']:+.2f}"),
        ("ISO",   f"{player['iso']:.3f}",            f"{player['z_iso']:+.2f}"),
        ("Spd",   f"{player['Spd']:.1f}",            f"{player['z_Spd']:+.2f}"),
    ]
    for label, raw, z in stats:
        print(f"  {label:<12} {raw:>8}  {z:>8}")

    # --- Composite scores ---
    print(f"\n  {'Raw Composite':<28} : {raw_score:+.3f}")
    print(f"  {'Age Multiplier':<28} : {mult:.2f}x  (age {int(player['Age'])})")
    print(f"  {'Adjusted Composite':<28} : {adj_score:+.3f}")
    print(f"  {'Percentile Rank (adjusted)':<28} : {pct:.1f}th  (KBO-only pool, n={len(pool)})")

    # --- Similarity matches ---
    print(f"\n  3 Closest KBO→MLB Comparables")
    print(f"  {'Player':<28} {'Season':>6}  {'Dist':>6}  {'Adj Score':>10}")
    print(f"  {'-'*56}")
    for _, row in matches.iterrows():
        print(
            f"  {row['NameASCII']:<28} {int(row['Season']):>6}  "
            f"{row['distance']:>6.3f}  {row['adjusted_composite']:>+10.3f}"
        )

    # --- MLB Outcome Context ---
    print(f"\n  MLB Outcome Context")
    print(f"  {'-'*56}")
    print(f"  {'':30} {'wRC+':>6}  {'BB%':>6}  {'K%':>6}  {'ISO':>6}  {'Spd':>5}")
    print(f"  {'-'*56}")
    if ceiling is not None:
        print(
            f"  {'Ceiling  (KBO→MLB avg, n=8)':<30} "
            f"{ceiling['wRC+']:>6.1f}  {ceiling['BB%']:>6.1%}  "
            f"{ceiling['K%']:>6.1%}  {ceiling['ISO']:>6.3f}  {ceiling['Spd']:>5.1f}"
        )
    if floor is not None:
        print(
            f"  {'Floor    (MLB→KBO avg, n=23)':<30} "
            f"{floor['wRC+']:>6.1f}  {floor['BB%']:>6.1%}  "
            f"{floor['K%']:>6.1%}  {floor['ISO']:>6.3f}  {floor['Spd']:>5.1f}"
        )

    print(f"\n  Adjusted Score Positioning")
    print(f"  {'-'*56}")
    print(f"  KBO→MLB players avg adj score : {kbo_to_mlb_adj_avg:+.3f}")
    print(f"  KBO→MLB players min adj score : {kbo_to_mlb_adj_min:+.3f}")
    print(f"  This player's adj score       : {adj_score:+.3f}  ({pct:.0f}th pct)")

    gap = adj_score - kbo_to_mlb_adj_avg
    if adj_score >= kbo_to_mlb_adj_avg:
        verdict = f"ABOVE ceiling avg ({gap:+.3f})"
    elif adj_score >= kbo_to_mlb_adj_min:
        verdict = f"Within ceiling range ({adj_score - kbo_to_mlb_adj_min:+.3f} vs lowest KBO→MLB)"
    else:
        verdict = f"Below KBO→MLB range ({gap:.3f} gap to ceiling avg)"
    print(f"  Verdict                       : {verdict}")

    # --- Summary paragraph ---
    wrc_desc = "elite" if player["wRC+"] > 150 else "above-average" if player["wRC+"] > 110 else "below-average"
    bb_desc = "strong" if player["z_bb_pct"] > 0.5 else "average" if player["z_bb_pct"] > -0.5 else "weak"
    k_desc = "impressive" if player["z_k_pct"] < -0.5 else "average" if player["z_k_pct"] < 0.5 else "elevated"
    iso_desc = "plus" if player["z_iso"] > 0.5 else "average" if player["z_iso"] > -0.5 else "below-average"
    spd_desc = "plus" if player["z_Spd"] > 0.5 else "average" if player["z_Spd"] > -0.5 else "below-average"
    best_comp = matches.iloc[0]

    print(f"\n  Summary")
    print(f"  {'-'*56}")
    summary = (
        f"  In {int(player['Season'])}, {player['NameASCII']} posted {wrc_desc} offensive production "
        f"(wRC+ {player['wRC+']:.0f}) with {bb_desc} plate discipline (BB% {fmt_pct(player['bb_pct'])}) "
        f"and {k_desc} contact rates (K% {fmt_pct(player['k_pct'])}). "
        f"He shows {iso_desc} power (ISO {player['iso']:.3f}) and {spd_desc} speed (Spd {player['Spd']:.1f}). "
        f"Age-adjusted composite of {adj_score:+.3f} ({mult:.2f}x at age {int(player['Age'])}) "
        f"ranks in the {pct:.0f}th percentile of the KBO-only scouting pool. "
        f"Closest MLB-transition comp: {best_comp['NameASCII']} "
        f"({int(best_comp['Season'])} KBO, adj score {best_comp['adjusted_composite']:+.3f})."
    )
    words = summary.split()
    line = ""
    for word in words:
        if len(line) + len(word) + 1 > 68:
            print(line)
            line = "  " + word
        else:
            line = (line + " " + word).lstrip() if not line else line + " " + word
    if line:
        print(line)

    print(f"\n{sep}\n")


def main() -> None:
    if len(sys.argv) < 2:
        print("Usage: python scouting_tool/scout.py \"Player Name\"")
        sys.exit(1)

    query = " ".join(sys.argv[1:])

    pool = pd.read_csv(SCOUTING_POOL)
    comps = pd.read_csv(KBO_TO_MLB)
    outcomes = pd.read_csv(MLB_OUTCOMES)

    player = find_player(pool, query)
    if player is None:
        print(f"Player not found in KBO-only scouting pool: '{query}'")
        print("Tip: try a partial name, e.g. 'Ahn' or 'Hyun Min'")
        sys.exit(1)

    print_report(player, pool, comps, outcomes)


if __name__ == "__main__":
    main()
