"""Pull FanGraphs MLB batting stats (2015-2026) for KBO crossover players.

Uses curl (via subprocess) for HTTP — Python `requests` triggers Cloudflare bot
detection on FanGraphs, while curl's TLS fingerprint passes through cleanly.
Saves to data/crossover/mlb_outcomes.csv.
"""

import json
import re
import subprocess
import time
from pathlib import Path
from urllib.parse import urlencode

import pandas as pd

OUTPUT = Path(__file__).parent / "mlb_outcomes.csv"

FG_API = "https://www.fangraphs.com/api/leaders/major-league/data"

KEEP_COLS = ["Name", "Season", "Age", "PA", "wRC+", "BB%", "K%", "ISO", "Spd"]

KBO_TO_MLB = [
    "Jung Hoo Lee",
    "Hyeseong Kim",
    "Sung-Mun Song",
    "Byung-ho Park",
    "Hyun Soo Kim",
    "Jae-Gyun Hwang",
    "Shin-Soo Choo",
    "Dae-Ho Lee",
    "Hak-Ju Lee",
]

MLB_TO_KBO = [
    "Aaron Altherr",
    "Dixon Machado",
    "Henry Ramos",
    "Socrates Brito",
    "Patrick Wisdom",
    "Preston Tucker",
    "Yasiel Puig",
    "Anthony Alford",
    "Jake Cave",
    "Victor Reyes",
    "Jason Martin",
    "Luis Liberato",
    "Sam Hilliard",
    "Austin Dean",
    "Daz Cameron",
    "Lewin Diaz",
    "Guillermo Heredia",
    "Jose Miguel Fernandez",
    "Jose Rojas",
    "Zach Reks",
    "Ronnie Dawson",
    "Jose Pirela",
    "Jamie Romak",
    "Matt Davidson",
    "Nicholas Martini",
    "Michael Tauchman",
    "Mel Rojas Jr.",
    "Yonathan Perlaza",
]


def curl_get(url: str, params: dict) -> str | None:
    """Fetch URL with curl. Returns response body string, or None on HTTP/network failure."""
    full_url = f"{url}?{urlencode(params)}"
    cmd = [
        "curl", "-s",
        "-w", "\n__STATUS__%{http_code}",   # append status code to body
        "-H", "User-Agent: Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36",
        "-H", "Accept: application/json, text/plain, */*",
        "-H", "Accept-Language: en-US,en;q=0.9",
        full_url,
    ]
    result = subprocess.run(cmd, capture_output=True, text=True, timeout=60)
    if result.returncode != 0:
        return None
    # Split off the appended status line
    body, _, status_line = result.stdout.rpartition("\n__STATUS__")
    status = int(status_line.strip()) if status_line.strip().isdigit() else 0
    if status != 200:
        return None
    return body


def strip_html(text: str) -> str:
    if not isinstance(text, str):
        return text
    return re.sub(r"<[^>]+>", "", text).strip()


def fetch_season(year: int) -> pd.DataFrame | None:
    """Fetch all batters for a single season. Returns None on failure."""
    params = {
        "pos": "all",
        "stats": "bat",
        "lg": "all",
        "qual": 1,
        "season": year,
        "season1": year,
        "ind": 1,
        "pageitems": 2000,
        "pagenum": 1,
    }
    body = curl_get(FG_API, params)
    if body is None:
        return None
    try:
        data = json.loads(body)
    except json.JSONDecodeError:
        return None
    rows = data.get("data", [])
    if not rows:
        return pd.DataFrame()
    df = pd.DataFrame(rows)
    if "Name" in df.columns:
        df["Name"] = df["Name"].apply(strip_html)
    return df


def normalize(name: str) -> str:
    return re.sub(r"[^a-z ]", "", name.lower().strip())


def find_player_rows(df: pd.DataFrame, target: str) -> pd.DataFrame:
    tgt = normalize(target)
    normed = df["Name"].apply(normalize)
    exact = df[normed == tgt]
    if not exact.empty:
        return exact
    words = tgt.split()
    mask = normed.apply(lambda n: all(w in n for w in words))
    return df[mask]


def pull_all_seasons() -> pd.DataFrame:
    print("Fetching season data from FanGraphs API...")
    seasons = []
    for year in range(2015, 2027):
        print(f"  {year}...", end="", flush=True)
        result = fetch_season(year)
        if result is None:
            # retry once after a pause
            print(f" failed, retrying in 10s...", end="", flush=True)
            time.sleep(10)
            result = fetch_season(year)
        if result is None:
            print(" SKIPPED")
        elif result.empty:
            print(" (no data)")
        else:
            print(f" {len(result)} rows")
            seasons.append(result)
        time.sleep(2)
    return pd.concat(seasons, ignore_index=True) if seasons else pd.DataFrame()


def extract_players(
    all_data: pd.DataFrame,
    player_list: list[str],
    group_label: str,
) -> pd.DataFrame:
    records = []
    for name in player_list:
        hits = find_player_rows(all_data, name)
        if hits.empty:
            print(f"  WARNING: '{name}' not found in FanGraphs data — skipping")
            continue
        available = [c for c in KEEP_COLS if c in hits.columns]
        subset = hits[available].copy()
        subset.insert(0, "Name", hits["Name"].values)
        subset["query_name"] = name
        subset["group"] = group_label
        records.append(subset)
        print(f"  {name}: {len(hits)} season(s)")
    return pd.concat(records, ignore_index=True) if records else pd.DataFrame()


def main() -> None:
    all_data = pull_all_seasons()
    if all_data.empty:
        print("ERROR: No data fetched. Aborting.")
        return

    print(f"\nTotal rows fetched: {len(all_data)}")

    print("\n--- KBO_to_MLB players ---")
    kbo_to_mlb_df = extract_players(all_data, KBO_TO_MLB, "KBO_to_MLB")

    print("\n--- MLB_to_KBO players ---")
    mlb_to_kbo_df = extract_players(all_data, MLB_TO_KBO, "MLB_to_KBO")

    combined = pd.concat([kbo_to_mlb_df, mlb_to_kbo_df], ignore_index=True)
    combined = combined.loc[:, ~combined.columns.duplicated()]

    col_order = ["query_name", "Name", "group", "Season", "Age", "PA", "wRC+", "BB%", "K%", "ISO", "Spd"]
    col_order = [c for c in col_order if c in combined.columns]
    combined = combined[col_order].sort_values(["group", "query_name", "Season"]).reset_index(drop=True)

    OUTPUT.parent.mkdir(parents=True, exist_ok=True)
    combined.to_csv(OUTPUT, index=False)
    print(f"\nSaved {len(combined)} rows → {OUTPUT}")
    print(combined.groupby("group")["query_name"].nunique().rename("players_found").to_string())
    print("\nSample:")
    print(combined.head(10).to_string(index=False))


if __name__ == "__main__":
    main()
