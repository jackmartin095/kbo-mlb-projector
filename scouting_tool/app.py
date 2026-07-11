"""KBO-to-MLB Projection Model — Streamlit app."""

from pathlib import Path

import pandas as pd
import plotly.graph_objects as go
import streamlit as st

DATA_FILE = Path(__file__).parent.parent / "data" / "processed" / "kbo_scored_pool.csv"
HOT_FILE  = Path(__file__).parent.parent / "data" / "processed" / "kbo_hot_2026.csv"
MLB_OUTCOMES_FILE = Path(__file__).parent.parent / "data" / "crossover" / "mlb_outcomes.csv"

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


@st.cache_data
def load_hot() -> pd.DataFrame:
    df = pd.read_csv(HOT_FILE)
    df["Team"] = df["Team"].str.replace(r" \(KBO\)", "", regex=True)
    df["BB%"] = (df["BB%"] * 100).round(1)
    df["K%"]  = (df["K%"]  * 100).round(1)
    df["ISO"] = df["ISO"].round(3)
    df["Spd"] = df["Spd"].round(1)
    df["wRC+"] = df["wRC+"].round(1)
    df["Score"] = df["hot_composite"].round(3)
    return df


@st.cache_data
def load_mlb_outcomes() -> dict:
    outcomes = pd.read_csv(MLB_OUTCOMES_FILE)
    stat_cols = ["wRC+", "BB%", "K%", "ISO", "Spd"]
    return {
        group: gdf[stat_cols].mean()
        for group, gdf in outcomes.groupby("group")
    }


# ---------------------------------------------------------------------------
# Navigation
# ---------------------------------------------------------------------------

PAGES = ["📋 The Board", "🔍 Player Deep-Dive", "🔥 Hot Right Now", "📖 Methodology"]

if "page" not in st.session_state:
    st.session_state["page"] = PAGES[0]
if "selected_player" not in st.session_state:
    st.session_state["selected_player"] = None

with st.sidebar:
    st.markdown("## ⚾ KBO→MLB Projector")
    st.divider()
    page = st.radio("Navigation", PAGES, index=PAGES.index(st.session_state["page"]))
    st.session_state["page"] = page
    st.divider()
    st.caption("Data: [FanGraphs KBO Leaderboards](https://www.fangraphs.com/leaders/international?pos=all&stats=bat&lg=KBO&qual=0&season=2026&season1=2023&ind=1&team=0&pagenum=1&pageitems=2000000)")

df = load_data()
hot_df = load_hot()
mlb_benchmarks = load_mlb_outcomes()

# ---------------------------------------------------------------------------
# Page 1 — The Board
# ---------------------------------------------------------------------------

if page == PAGES[0]:
    st.title("⚾ KBO→MLB Projection Board")
    st.caption(
        "PA-weighted career aggregate (2023–2026) · K=300 Marcel shrinkage · Age ≤ 29 · "
        f"{len(df)} qualifying players"
    )
    st.divider()

    with st.sidebar:
        st.divider()
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

    filtered = df.copy()
    if selected_teams:
        filtered = filtered[filtered["Team"].isin(selected_teams)]
    filtered = filtered[filtered["Combined PA"] >= min_pa]
    filtered = filtered[filtered["Age"] <= max_age]
    filtered = filtered.sort_values(sort_col, ascending=sort_asc).reset_index(drop=True)
    filtered["Rank"] = range(1, len(filtered) + 1)

    display_cols = ["Rank", "Name", "Team", "Age", "Seasons", "Combined PA",
                    "wRC+", "BB%", "K%", "ISO", "Spd", "Adj Score", "Pctile",
                    "Trajectory"]

    st.subheader(f"Full Qualifying Pool — {len(filtered)} players")
    st.caption("Click a row then use **Open in Deep-Dive →** to view the player profile.")

    col_cfg = {
        "Rank":        st.column_config.NumberColumn("Rank",      width="small"),
        "Name":        st.column_config.TextColumn("Name",        width="medium"),
        "Team":        st.column_config.TextColumn("Team",        width="small"),
        "Age":         st.column_config.NumberColumn("Age",       width="small"),
        "Seasons":     st.column_config.TextColumn("Seasons",     width="small"),
        "Combined PA": st.column_config.NumberColumn("PA",        width="small"),
        "wRC+":        st.column_config.NumberColumn("wRC+",      format="%.1f", width="small"),
        "BB%":         st.column_config.NumberColumn("BB%",       format="%.1f%%", width="small"),
        "K%":          st.column_config.NumberColumn("K%",        format="%.1f%%", width="small"),
        "ISO":         st.column_config.NumberColumn("ISO",       format="%.3f", width="small"),
        "Spd":         st.column_config.NumberColumn("Spd",       format="%.1f", width="small"),
        "Adj Score":   st.column_config.ProgressColumn(
            "Adj Score",
            format="%.3f",
            min_value=float(df["Adj Score"].min()),
            max_value=float(df["Adj Score"].max()),
            width="medium",
        ),
        "Pctile":      st.column_config.NumberColumn("Pctile",    format="%.1f", width="small"),
        "Trajectory":  st.column_config.TextColumn("Trend",       width="small"),
    }

    event = st.dataframe(
        filtered[display_cols],
        column_config=col_cfg,
        use_container_width=True,
        hide_index=True,
        height=min(50 + len(filtered) * 35, 900),
        on_select="rerun",
        selection_mode="single-row",
    )

    selected_rows = event.selection.get("rows", []) if event and event.selection else []
    if selected_rows:
        selected_name = filtered.iloc[selected_rows[0]]["Name"]
        st.session_state["selected_player"] = selected_name
        if st.button(f"Open **{selected_name}** in Deep-Dive →"):
            st.session_state["page"] = PAGES[1]
            st.rerun()

    st.caption(
        "**Adj Score** = composite z-score across wRC+ (30%), BB% (25%), K% inverted (20%), "
        "ISO (15%), Spd (10%) · shrunk toward pool mean by PA · multiplied by age factor"
    )


# ---------------------------------------------------------------------------
# Page 2 — Player Deep-Dive
# ---------------------------------------------------------------------------

elif page == PAGES[1]:
    st.title("🔍 Player Deep-Dive")
    st.divider()

    # Build dropdown labels: "Name — Team · #Rank"
    player_labels = [
        f"{row['Name']} — {row['Team']} · #{int(row['Rank'])}"
        for _, row in df.sort_values("Rank").iterrows()
    ]
    name_to_label = {
        row["Name"]: f"{row['Name']} — {row['Team']} · #{int(row['Rank'])}"
        for _, row in df.iterrows()
    }
    label_to_name = {v: k for k, v in name_to_label.items()}

    default_idx = 0
    selected_name = st.session_state.get("selected_player")
    if selected_name and selected_name in name_to_label:
        default_label = name_to_label[selected_name]
        if default_label in player_labels:
            default_idx = player_labels.index(default_label)

    with st.sidebar:
        st.divider()
        chosen_label = st.selectbox("Select Player", player_labels, index=default_idx)
        chosen = label_to_name.get(chosen_label, player_labels[0])
        st.session_state["selected_player"] = chosen

    player = df[df["Name"] == chosen].iloc[0]

    # --- Header ---
    rank_val = int(player["Rank"])
    pctile_val = float(player["Pctile"])

    col1, col2, col3, col4 = st.columns(4)
    col1.metric("Rank", f"#{rank_val}")
    col2.metric("Percentile", f"{pctile_val:.1f}th")
    col3.metric("Adj Score", f"{float(player['Adj Score']):+.3f}")
    trajectory = player.get("Trajectory", "N/A") if pd.notna(player.get("Trajectory")) else "N/A"
    trend_val = player.get("Trend")
    trend_str = f"{float(trend_val):+.3f}" if pd.notna(trend_val) else "N/A"
    col4.metric("Trajectory", f"{trajectory}  ({trend_str})")

    st.divider()

    # --- Bio row ---
    bio1, bio2, bio3, bio4 = st.columns(4)
    bio1.markdown(f"**Team:** {player['Team']}")
    bio2.markdown(f"**Age:** {int(player['Age'])}")
    bio3.markdown(f"**Seasons:** {player['Seasons']}")
    bio4.markdown(f"**Combined PA:** {int(player['Combined PA'])}")

    st.divider()

    # --- Slash line / counting stats ---
    sl1, sl2, sl3, sl4, sl5, sl6, sl7, sl8 = st.columns(8)
    sl1.metric("AVG",  f"{float(player['AVG']):.3f}")
    sl2.metric("OBP",  f"{float(player['OBP']):.3f}")
    sl3.metric("SLG",  f"{float(player['SLG']):.3f}")
    sl4.metric("OPS",  f"{float(player['OPS']):.3f}")
    sl5.metric("HR",   f"{int(player['HR'])}")
    sl6.metric("SB",   f"{int(player['SB'])}")
    sl7.metric("RBI",  f"{int(player['RBI'])}")
    sl8.metric("R",    f"{int(player['R'])}")

    with st.expander("Full counting stats", expanded=False):
        count_cols = ["G", "AB", "H", "2B", "3B", "HR", "R", "RBI", "BB", "SO", "SB", "CS", "HBP"]
        count_data = {col: int(player[col]) for col in count_cols if col in player.index}
        count_df = pd.DataFrame([count_data])
        st.dataframe(count_df, hide_index=True, use_container_width=False)
        st.caption(f"Counting totals across {player['Seasons']}")

    st.divider()

    # --- Stat line + Radar side-by-side ---
    left, right = st.columns([1, 2])

    with left:
        st.subheader("Career Aggregate Stat Line")
        stats = {
            "wRC+":  f"{float(player['wRC+']):>6.1f}",
            "BB%":   f"{float(player['BB%']):>5.1f}%",
            "K%":    f"{float(player['K%']):>5.1f}%",
            "ISO":   f"{float(player['ISO']):>6.3f}",
            "Spd":   f"{float(player['Spd']):>5.1f}",
        }
        z_cols = {
            "wRC+": "z_wRC+",
            "BB%":  "z_BB%",
            "K%":   "z_K%",
            "ISO":  "z_ISO",
            "Spd":  "z_Spd",
        }
        stat_rows = []
        for metric, raw in stats.items():
            z = float(player[z_cols[metric]])
            bar = "▓" * int(abs(z) * 2) if abs(z) < 5 else "▓▓▓▓▓▓▓▓▓▓"
            direction = "+" if z >= 0 else "-"
            stat_rows.append({
                "Metric": metric,
                "Value": raw.strip(),
                "Z-Score": f"{z:+.2f}",
            })
        stat_df = pd.DataFrame(stat_rows)
        st.dataframe(
            stat_df,
            hide_index=True,
            use_container_width=True,
            column_config={
                "Metric":  st.column_config.TextColumn(width="small"),
                "Value":   st.column_config.TextColumn(width="small"),
                "Z-Score": st.column_config.TextColumn(width="small"),
            },
        )

        # Trend detail
        st.divider()
        st.subheader("Trend")
        if pd.notna(trend_val):
            color = "green" if float(trend_val) > 0 else "red"
            st.markdown(
                f"**{trajectory}** &nbsp; <span style='color:{color};font-size:1.2em'>{trend_str}</span>",
                unsafe_allow_html=True,
            )
            st.caption("Trend = most recent season composite minus prior seasons' recency-weighted composite")
        else:
            st.markdown("**N/A** — single-season player, no trend data")

    with right:
        st.subheader("Statistical Shape — Z-Scores vs Pool Average")

        metric_labels = ["wRC+", "BB%", "K% (inv)", "ISO", "Spd"]
        z_values_raw = [
            float(player["z_wRC+"]),
            float(player["z_BB%"]),
            -float(player["z_K%"]),   # invert so higher = better on chart
            float(player["z_ISO"]),
            float(player["z_Spd"]),
        ]

        # Close the polygon
        theta = metric_labels + [metric_labels[0]]
        r_player = z_values_raw + [z_values_raw[0]]
        r_zero = [0] * len(theta)

        fig = go.Figure()

        # Pool average ring (zero line)
        fig.add_trace(go.Scatterpolar(
            r=r_zero,
            theta=theta,
            mode="lines",
            name="Pool avg",
            line=dict(color="rgba(150,150,150,0.5)", width=1.5, dash="dot"),
            hoverinfo="skip",
        ))

        # Player shape
        fill_color = "rgba(0, 116, 217, 0.18)"
        line_color = "rgba(0, 116, 217, 0.9)"

        fig.add_trace(go.Scatterpolar(
            r=r_player,
            theta=theta,
            mode="lines+markers",
            fill="toself",
            fillcolor=fill_color,
            name=player["Name"],
            line=dict(color=line_color, width=2.5),
            marker=dict(size=7, color=line_color),
            hovertemplate="<b>%{theta}</b><br>Z-Score: %{r:+.2f}<extra></extra>",
        ))

        axis_range = max(3.0, max(abs(v) for v in z_values_raw) + 0.4)

        fig.update_layout(
            polar=dict(
                radialaxis=dict(
                    visible=True,
                    range=[-axis_range, axis_range],
                    tickvals=[-2, -1, 0, 1, 2],
                    tickfont=dict(size=11),
                    gridcolor="rgba(180,180,180,0.3)",
                    linecolor="rgba(180,180,180,0.4)",
                ),
                angularaxis=dict(
                    tickfont=dict(size=13),
                    gridcolor="rgba(180,180,180,0.25)",
                    linecolor="rgba(180,180,180,0.4)",
                ),
                bgcolor="rgba(0,0,0,0)",
            ),
            showlegend=True,
            legend=dict(orientation="h", yanchor="bottom", y=-0.12, x=0.5, xanchor="center"),
            margin=dict(t=30, b=40, l=60, r=60),
            height=420,
            paper_bgcolor="rgba(0,0,0,0)",
            plot_bgcolor="rgba(0,0,0,0)",
            font=dict(size=13),
        )

        st.plotly_chart(fig, use_container_width=True)
        st.caption(
            "All five axes z-scored against the full KBO-only pool aggregate. "
            "K% is inverted so outward = better on every axis. "
            "Dotted ring = pool average (z=0)."
        )

    st.divider()

    # --- Score positioning vs MLB benchmarks ---
    st.subheader("Score Positioning vs MLB Benchmarks")

    adj = float(player["Adj Score"])
    floor_data = mlb_benchmarks.get("MLB_to_KBO")
    ceiling_data = mlb_benchmarks.get("KBO_to_MLB")

    bm_cols = st.columns(3)
    with bm_cols[0]:
        st.metric("This Player", f"{adj:+.3f}")
    with bm_cols[1]:
        if ceiling_data is not None:
            st.metric("KBO→MLB Ceiling Avg (wRC+)", f"{ceiling_data['wRC+']:.0f}")
    with bm_cols[2]:
        if floor_data is not None:
            st.metric("MLB→KBO Floor Avg (wRC+)", f"{floor_data['wRC+']:.0f}")

    if floor_data is not None and ceiling_data is not None:
        st.markdown("**Floor & Ceiling Stat Comparison**")
        bench_rows = []
        for metric in ["wRC+", "BB%", "K%", "ISO", "Spd"]:
            player_val = float(player[metric])
            floor_val = float(floor_data[metric])
            ceil_val = float(ceiling_data[metric])
            if metric in ("BB%", "K%"):
                player_fmt = f"{player_val:.1f}%"
                floor_fmt  = f"{floor_val * 100:.1f}%"
                ceil_fmt   = f"{ceil_val * 100:.1f}%"
            elif metric == "ISO":
                player_fmt = f"{player_val:.3f}"
                floor_fmt  = f"{floor_val:.3f}"
                ceil_fmt   = f"{ceil_val:.3f}"
            else:
                player_fmt = f"{player_val:.1f}"
                floor_fmt  = f"{floor_val:.1f}"
                ceil_fmt   = f"{ceil_val:.1f}"
            bench_rows.append({
                "Metric": metric,
                "This Player": player_fmt,
                "KBO→MLB Ceiling": ceil_fmt,
                "MLB→KBO Floor": floor_fmt,
            })
        bench_df = pd.DataFrame(bench_rows)
        st.dataframe(
            bench_df,
            hide_index=True,
            use_container_width=False,
            column_config={
                "Metric":         st.column_config.TextColumn(width="small"),
                "This Player":    st.column_config.TextColumn(width="small"),
                "KBO→MLB Ceiling": st.column_config.TextColumn(width="medium"),
                "MLB→KBO Floor":  st.column_config.TextColumn(width="medium"),
            },
        )
        st.caption(
            "Ceiling = average MLB stats of the 8 KBO players who successfully transitioned. "
            "Floor = average pre-KBO MLB stats of the 23 MLB veterans who moved to KBO."
        )


# ---------------------------------------------------------------------------
# Page 3 — Hot Right Now
# ---------------------------------------------------------------------------

elif page == PAGES[2]:
    st.title("🔥 Hot Right Now — 2026 In-Season Form")
    st.info(
        "**This page reflects 2026 in-season performance only** — not the multi-year projection ranking. "
        "Players are scored on their 2026 stats alone (z-scored against the 2026 qualifying pool), "
        "with no recency weighting and no age multiplier. "
        "Minimum 100 PA in 2026 · Age ≤ 29 · Domestic players only."
    )
    st.caption(f"{len(hot_df)} players qualify · 2026 season through latest data pull")
    st.divider()

    with st.sidebar:
        st.divider()
        st.header("Filters")
        hot_teams = sorted(hot_df["Team"].unique())
        hot_selected_teams = st.multiselect("Team", hot_teams, default=[])
        hot_min_pa = st.slider("Min 2026 PA", 100, 500, 100, step=25)
        hot_max_age = st.slider("Max Age", 20, 29, 29)

    filtered_hot = hot_df.copy()
    if hot_selected_teams:
        filtered_hot = filtered_hot[filtered_hot["Team"].isin(hot_selected_teams)]
    filtered_hot = filtered_hot[filtered_hot["PA"] >= hot_min_pa]
    filtered_hot = filtered_hot[filtered_hot["Age"] <= hot_max_age]
    filtered_hot = filtered_hot.sort_values("Score", ascending=False).reset_index(drop=True)
    filtered_hot["Rank"] = range(1, len(filtered_hot) + 1)

    hot_display_cols = ["Rank", "Name", "Team", "Age", "PA",
                        "wRC+", "BB%", "K%", "ISO", "Spd", "Score"]

    hot_col_cfg = {
        "Rank":  st.column_config.NumberColumn("Rank",  width="small"),
        "Name":  st.column_config.TextColumn("Name",    width="medium"),
        "Team":  st.column_config.TextColumn("Team",    width="small"),
        "Age":   st.column_config.NumberColumn("Age",   width="small"),
        "PA":    st.column_config.NumberColumn("2026 PA", width="small"),
        "wRC+":  st.column_config.NumberColumn("wRC+",  format="%.1f", width="small"),
        "BB%":   st.column_config.NumberColumn("BB%",   format="%.1f%%", width="small"),
        "K%":    st.column_config.NumberColumn("K%",    format="%.1f%%", width="small"),
        "ISO":   st.column_config.NumberColumn("ISO",   format="%.3f", width="small"),
        "Spd":   st.column_config.NumberColumn("Spd",   format="%.1f", width="small"),
        "Score": st.column_config.ProgressColumn(
            "2026 Score",
            format="%.3f",
            min_value=float(hot_df["Score"].min()),
            max_value=float(hot_df["Score"].max()),
            width="medium",
        ),
    }

    st.subheader(f"Hot Right Now — {len(filtered_hot)} players")

    hot_event = st.dataframe(
        filtered_hot[hot_display_cols],
        column_config=hot_col_cfg,
        use_container_width=True,
        hide_index=True,
        height=min(50 + len(filtered_hot) * 35, 900),
        on_select="rerun",
        selection_mode="single-row",
    )

    hot_selected_rows = hot_event.selection.get("rows", []) if hot_event and hot_event.selection else []
    if hot_selected_rows:
        hot_selected_name = filtered_hot.iloc[hot_selected_rows[0]]["Name"]
        # Try to find this player in the multi-year board
        in_board = df[df["Name"] == hot_selected_name]
        if not in_board.empty:
            board_rank = int(in_board.iloc[0]["Rank"])
            board_score = float(in_board.iloc[0]["Adj Score"])
            st.caption(
                f"**{hot_selected_name}** is ranked **#{board_rank}** on the multi-year Projection Board "
                f"(adj score {board_score:+.3f})."
            )
        else:
            st.caption(
                f"**{hot_selected_name}** does not appear on the multi-year Projection Board "
                f"(insufficient career PA or filtered out)."
            )
        if st.button(f"Open **{hot_selected_name}** in Deep-Dive →"):
            st.session_state["selected_player"] = hot_selected_name
            st.session_state["page"] = PAGES[1]
            st.rerun()

    st.divider()
    st.caption(
        "**2026 Score** = composite z-score across wRC+ (30%), BB% (25%), K% inverted (20%), "
        "ISO (15%), Spd (10%) · z-scored against 2026 qualifying pool only · no age factor applied"
    )


# ---------------------------------------------------------------------------
# Page 4 — Methodology
# ---------------------------------------------------------------------------

elif page == PAGES[3]:
    st.title("📖 Methodology")
    st.caption("How the KBO→MLB Projection Model works")
    st.divider()

    st.markdown("""
### Overview

This model identifies KBO players most likely to succeed if posted to MLB, using
four years of KBO batting data (2023–2026) sourced from FanGraphs. It produces a
single **Adjusted Composite Score** per player that combines statistical quality,
sample reliability, and age trajectory.

---

### Step 1 — Data

Raw data comes from the FanGraphs KBO International Leaderboard, exported separately
as rate stats (wRC+, BB%, K%, ISO, Spd) and counting stats (HR, SB, H, R, RBI, etc.)
then merged on Season + Player ID + Team. Traded players who appear as multiple split-season
rows are deduplicated by keeping their highest-PA stint for rate stats, while PA is summed
across all stints to preserve the true sample size.

Players are tagged into three groups:
- **KBO_only** — domestic KBO players who have not yet played in MLB
- **KBO_to_MLB** — players who crossed over from KBO to MLB (used as a ceiling benchmark)
- **MLB_to_KBO** — MLB veterans who moved to KBO (used as a floor benchmark)

Foreign imports (non-Korean players) are excluded from the scouting pool using a Korean
surname heuristic plus a manually maintained exclusion list.

---

### Step 2 — Career Aggregate

For each KBO_only player, per-season stats are combined into a single career profile using
**PA-weighted averaging** — each season contributes proportionally to how many plate
appearances it represents. This closely mirrors how FanGraphs calculates multi-year
aggregate leaderboards, and avoids over-weighting small partial seasons.

**Qualifying filters:** 200+ combined career PA · most recent season age ≤ 29

---

### Step 3 — Marcel-Style Shrinkage (K = 300)

Raw career averages are regressed toward the pool mean using a reliability weight based
on sample size:

```
shrunk = pool_mean + (raw − pool_mean) × PA / (PA + 300)
```

A player with 300 PA gets a 50/50 blend of their own numbers and the pool mean.
A player with 1,500 PA is 83% their own numbers. This prevents small-sample outliers
from dominating the rankings. Shrunk values are used only for scoring — raw stats are
always displayed.

---

### Step 4 — Z-Scores & Composite

Each shrunk metric is standardized (z-scored) against the full qualifying pool:

```
z = (shrunk_value − pool_mean) / pool_std
```

Five metrics are combined into a **composite score** using fixed weights:

| Metric | Weight | Direction |
|--------|--------|-----------|
| wRC+   | 30%    | Higher = better |
| BB%    | 25%    | Higher = better |
| K%     | 20%    | **Lower = better** (inverted) |
| ISO    | 15%    | Higher = better |
| Spd    | 10%    | Higher = better |

---

### Step 5 — Age Multiplier

The composite score is multiplied by an age factor that rewards younger players
(more development runway) and discounts older ones:

| Age   | Multiplier |
|-------|-----------|
| ≤ 20  | 1.25×     |
| 21–22 | 1.15×     |
| 23–24 | 1.05×     |
| 25–27 | 1.00×     |
| 28–29 | 0.90×     |

The result is the **Adjusted Composite Score** used for final rankings.

---

### Step 6 — Trend & Trajectory

To capture recent momentum without distorting the career aggregate, each player's
**Trend** is computed separately as:

```
Trend = most recent season composite − prior seasons' recency-weighted composite
```

Prior seasons use 50/30/20 recency weights (redistributed for players with more than
three seasons). Composite scores here use raw per-season z-scores against the full
pool for that season, so the trend reflects genuine improvement or decline relative
to peers, not just aging.

Trajectory labels are assigned by percentile within the qualifying pool:
- **↑↑ Rising** — top 20% of trend scores
- **↑ Improving** — 50th–80th percentile
- **→ Stable** — 20th–50th percentile
- **↓ Declining** — bottom 20%

---

### Hot Right Now Page

The Hot Right Now page is a separate view that scores players on **2026 in-season
stats only** — no multi-year aggregation, no shrinkage, no age multiplier. It uses
the same five metrics and composite weights, z-scored against everyone with 100+ PA
in 2026. It answers a different question than the main board: *who is performing best
right now*, independent of career history.

---

### Benchmarks

**Ceiling** — average MLB stats of KBO players who successfully transitioned to MLB
(Jung Hoo Lee, Ha-seong Kim, Hyeseong Kim, et al.). Represents what the best-case
MLB outcome looks like statistically.

**Floor** — average pre-KBO MLB stats of MLB veterans who moved to KBO
(Yasiel Puig, Patrick Wisdom, et al.). Represents the minimum MLB baseline; a KBO
player posting stats below this floor is performing at a level that even MLB players
who washed out could match.

---

### Limitations

- **Rate averaging vs. pooled counting:** PA-weighted rate averaging is a close
  approximation but not identical to recomputing rates from pooled counting totals.
  Small gaps (typically < 5 wRC+ points) may exist vs. FanGraphs aggregate leaderboards.
- **No position adjustment:** All players are evaluated purely on batting metrics.
  Defensive value and positional scarcity are not modeled.
- **No translation factor:** KBO stats are not run through a KBO-to-MLB translation
  (park factors, league difficulty, etc.). The model ranks players relative to each
  other within the KBO context, not against MLB baselines directly.
- **Small crossover sample:** Only eight KBO→MLB transitions are used for the ceiling
  benchmark, limiting its statistical precision.
""")

    st.divider()
    st.caption("Data: FanGraphs KBO Leaderboards · Model by Jack Martin")
