"""KBO-to-MLB Projection Model — Streamlit app."""

from pathlib import Path

import pandas as pd
import streamlit as st

DATA_FILE = Path(__file__).parent.parent / "data" / "processed" / "kbo_scored_pool.csv"

st.set_page_config(
    page_title="KBO→MLB Projector",
    page_icon="⚾",
    layout="wide",
)

# ---------------------------------------------------------------------------
# Data
# ---------------------------------------------------------------------------

@st.cache_data
def load_data() -> pd.DataFrame:
    df = pd.read_csv(DATA_FILE)
    df["Team"] = df["Team"].str.replace(r" \(KBO\)", "", regex=True)
    df["BB%"] = (df["BB%"] * 100).round(1)
    df["K%"]  = (df["K%"]  * 100).round(1)
    df["ISO"] = df["ISO"].round(3)
    df["Spd"] = df["Spd"].round(1)
    df["wRC+"] = df["wRC+"].round(1)
    df["Adj Score"] = df["adjusted_composite"].round(3)
    df["Pctile"] = df["Percentile"].round(1)
    df = df.rename(columns={"seasons_used": "Seasons", "PA": "Combined PA"})
    return df

df = load_data()

# ---------------------------------------------------------------------------
# Page 1 — The Board
# ---------------------------------------------------------------------------

st.title("⚾ KBO→MLB Projection Board")
st.caption(
    "PA-weighted career aggregate (2023–2026) · K=300 Marcel shrinkage · Age ≤ 29 · "
    f"{len(df)} qualifying players"
)
st.divider()

# --- Sidebar controls ---
with st.sidebar:
    st.header("Filters")
    teams = sorted(df["Team"].unique())
    selected_teams = st.multiselect("Team", teams, default=[])
    min_pa = st.slider("Min Combined PA", 200, 2000, 200, step=50)
    max_age = st.slider("Max Age", 20, 29, 29)
    st.divider()
    sort_col = st.selectbox(
        "Sort by",
        ["Adj Score", "wRC+", "BB%", "K%", "ISO", "Spd", "Age", "Combined PA"],
        index=0,
    )
    sort_asc = st.checkbox("Ascending", value=False)

# --- Filter ---
filtered = df.copy()
if selected_teams:
    filtered = filtered[filtered["Team"].isin(selected_teams)]
filtered = filtered[filtered["Combined PA"] >= min_pa]
filtered = filtered[filtered["Age"] <= max_age]
filtered = filtered.sort_values(sort_col, ascending=sort_asc).reset_index(drop=True)
filtered["Rank"] = range(1, len(filtered) + 1)

# --- Display columns ---
display_cols = ["Rank", "Name", "Team", "Age", "Seasons", "Combined PA",
                "wRC+", "BB%", "K%", "ISO", "Spd", "Adj Score", "Pctile"]

st.subheader(f"Full Qualifying Pool — {len(filtered)} players")

# Build column config
col_cfg = {
    "Rank":        st.column_config.NumberColumn("Rank",    width="small"),
    "Name":        st.column_config.TextColumn("Name",      width="medium"),
    "Team":        st.column_config.TextColumn("Team",      width="small"),
    "Age":         st.column_config.NumberColumn("Age",     width="small"),
    "Seasons":     st.column_config.TextColumn("Seasons",   width="small"),
    "Combined PA": st.column_config.NumberColumn("PA",      width="small"),
    "wRC+":        st.column_config.NumberColumn("wRC+",    format="%.1f", width="small"),
    "BB%":         st.column_config.NumberColumn("BB%",     format="%.1f%%", width="small"),
    "K%":          st.column_config.NumberColumn("K%",      format="%.1f%%", width="small"),
    "ISO":         st.column_config.NumberColumn("ISO",     format="%.3f", width="small"),
    "Spd":         st.column_config.NumberColumn("Spd",     format="%.1f", width="small"),
    "Adj Score":   st.column_config.ProgressColumn(
        "Adj Score",
        format="%.3f",
        min_value=float(df["Adj Score"].min()),
        max_value=float(df["Adj Score"].max()),
        width="medium",
    ),
    "Pctile":      st.column_config.NumberColumn("Pctile",  format="%.1f", width="small"),
}

st.dataframe(
    filtered[display_cols],
    column_config=col_cfg,
    use_container_width=True,
    hide_index=True,
    height=min(50 + len(filtered) * 35, 900),
)

st.caption(
    "**Adj Score** = composite z-score across wRC+ (30%), BB% (25%), K% inverted (20%), "
    "ISO (15%), Spd (10%) · shrunk toward pool mean by PA · multiplied by age factor"
)
