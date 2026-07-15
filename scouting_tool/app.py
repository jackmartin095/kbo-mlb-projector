"""KBO-to-MLB Projection Model — Streamlit app."""

from pathlib import Path

import pandas as pd
import plotly.graph_objects as go
import streamlit as st
from packaging.version import Version as _V

_ST_SUPPORTS_SELECTION = _V(st.__version__) >= _V("1.35.0")

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
    df["Percentile"] = df["Percentile"].round(1)
    df["Trend"] = df["Trend"].round(3)
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
    result = {}
    for group, gdf in outcomes.groupby("group"):
        # PA-weighted average per player first, then average across players
        player_aggs = (
            gdf.groupby("Name")
            .apply(lambda d: pd.Series(
                {s: (d[s] * d["PA"]).sum() / d["PA"].sum() for s in stat_cols}
            ), include_groups=False)
        )
        result[group] = player_aggs.mean()
    return result


# ---------------------------------------------------------------------------
# Navigation
# ---------------------------------------------------------------------------

PAGES = ["📖 Methodology", "📋 The Board", "🔍 Player Deep-Dive", "🔥 Hot Right Now"]

if "page" not in st.session_state:
    st.session_state["page"] = PAGES[0]  # Methodology is index 0 = landing page
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

if page == PAGES[1]:
    st.title("⚾ KBO→MLB Projection Board")
    st.markdown(
        "A ranked pool of KBO hitters most likely to succeed if posted to MLB. "
        "Each player's score is built from a PA-weighted career aggregate across 2023–2026, "
        "shrunk toward the pool mean for reliability, and adjusted upward for younger players "
        "with more development runway. Use the sidebar to filter by team, PA minimum, or age. "
        "Click a row and use **Open in Deep-Dive →** to view a full player profile. "
        "Note: the composite weights plate discipline and contact heavily, so contact-first "
        "profiles with limited power can rank well. Check the ISO column and the deep-dive "
        "radar for a player's full shape."
    )
    st.caption(
        f"PA-weighted career aggregate (2023–2026) · K=300 Marcel shrinkage · Age ≤ 29 · {len(df)} qualifying players"
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
    filtered = filtered[~filtered["Seasons"].isin(["2023 only", "2024 only"])]
    if selected_teams:
        filtered = filtered[filtered["Team"].isin(selected_teams)]
    filtered = filtered[filtered["Combined PA"] >= min_pa]
    filtered = filtered[filtered["Age"] <= max_age]
    filtered = filtered.sort_values(sort_col, ascending=sort_asc).reset_index(drop=True)
    filtered["Rank"] = range(1, len(filtered) + 1)

    display_cols = ["Rank", "Name", "Team", "Age", "Seasons", "Combined PA",
                    "wRC+", "BB%", "K%", "ISO", "Spd", "Adj Score", "Percentile",
                    "Trend", "Trajectory"]

    st.subheader(f"Full Qualifying Pool — {len(filtered)} players")
    st.caption("Click a row then use **Open in Deep-Dive →** to view the player profile.")

    _score_max = float(df["Adj Score"].max())
    _score_min = float(df["Adj Score"].min())

    col_cfg = {
        "Rank":        st.column_config.NumberColumn("Rank",       width="small"),
        "Name":        st.column_config.TextColumn("Name",         width="medium"),
        "Team":        st.column_config.TextColumn("Team",         width="small"),
        "Age":         st.column_config.NumberColumn("Age",        width="small"),
        "Seasons":     st.column_config.TextColumn("Seasons",      width="small"),
        "Combined PA": st.column_config.NumberColumn("PA",         width="small"),
        "wRC+":        st.column_config.NumberColumn("wRC+",       format="%.1f",  width="small"),
        "BB%":         st.column_config.NumberColumn("BB%",        format="%.1f%%", width="small"),
        "K%":          st.column_config.NumberColumn("K%",         format="%.1f%%", width="small"),
        "ISO":         st.column_config.NumberColumn("ISO",        format="%.3f",  width="small"),
        "Spd":         st.column_config.NumberColumn("Spd",        format="%.1f",  width="small"),
        "Adj Score":   st.column_config.ProgressColumn(
            "Adj Score",
            format="%.3f",
            min_value=_score_min,
            max_value=_score_max,
            width="medium",
        ),
        "Percentile":  st.column_config.NumberColumn("Percentile", format="%.1f",  width="small"),
        "Trend":       st.column_config.NumberColumn("Trend",      format="%+.3f", width="small"),
        "Trajectory":  st.column_config.TextColumn("Trajectory",   width="small"),
    }

    _df_kwargs = dict(on_select="rerun", selection_mode="single-row") if _ST_SUPPORTS_SELECTION else {}
    event = st.dataframe(
        filtered[display_cols],
        column_config=col_cfg,
        use_container_width=True,
        hide_index=True,
        height=min(50 + len(filtered) * 35, 900),
        **_df_kwargs,
    )

    selected_rows = (event.selection.get("rows", []) if event and hasattr(event, "selection") and event.selection else []) if _ST_SUPPORTS_SELECTION else []
    if selected_rows:
        selected_name = filtered.iloc[selected_rows[0]]["Name"]
        st.session_state["selected_player"] = selected_name
        if st.button(f"Open **{selected_name}** in Deep-Dive →"):
            st.session_state["page"] = PAGES[2]
            st.rerun()

    st.caption(
        "**Adj Score** = composite z-score across wRC+ (30%), BB% (25%), ISO (20%), "
        "K% inverted (15%), Spd (10%) · shrunk toward pool mean by PA · multiplied by age factor"
    )


# ---------------------------------------------------------------------------
# Page 2 — Player Deep-Dive
# ---------------------------------------------------------------------------

elif page == PAGES[2]:
    st.title("🔍 Player Deep-Dive")
    st.markdown(
        "Full scouting profile for any player in the qualifying pool. Select a player from "
        "the sidebar dropdown to see their career aggregate stat line, z-score radar chart "
        "showing their statistical shape against the pool average, trend and trajectory, "
        "and how their numbers compare to the KBO→MLB ceiling and MLB→KBO floor benchmarks."
    )
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

    player_rows = df[df["Name"] == chosen]
    if player_rows.empty:
        st.error(f"Player not found: '{chosen}' (label: '{chosen_label}'). Please select again.")
        st.stop()
    player = player_rows.iloc[0]

    # --- Player name ---
    st.subheader(chosen)

    # --- Header ---
    rank_val = int(player["Rank"])
    pctile_val = float(player["Percentile"])

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
    def _fmt_int(val):
        return str(int(round(float(val)))) if pd.notna(val) else "—"

    def _fmt_float(val, fmt=".3f"):
        return format(float(val), fmt) if pd.notna(val) else "—"

    sl1, sl2, sl3, sl4, sl5, sl6, sl7, sl8 = st.columns(8)
    sl1.metric("AVG",  _fmt_float(player.get("AVG")))
    sl2.metric("OBP",  _fmt_float(player.get("OBP")))
    sl3.metric("SLG",  _fmt_float(player.get("SLG")))
    sl4.metric("OPS",  _fmt_float(player.get("OPS")))
    sl5.metric("HR",   _fmt_int(player.get("HR")))
    sl6.metric("SB",   _fmt_int(player.get("SB")))
    sl7.metric("RBI",  _fmt_int(player.get("RBI")))
    sl8.metric("R",    _fmt_int(player.get("R")))

    with st.expander("Full counting stats", expanded=False):
        count_cols = ["G", "AB", "H", "2B", "3B", "HR", "R", "RBI", "BB", "SO", "SB", "CS", "HBP"]
        count_data = {col: _fmt_int(player.get(col)) for col in count_cols if col in player.index}
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
            st.caption(
                "Trend = most recent season's composite z-score minus prior seasons' recency-weighted composite. "
                "Positive = most recent season was better than prior baseline; negative = recent season was weaker. "
                "Labels are relative: → Stable means the trend is near the median for the pool, "
                "not that performance is flat in absolute terms."
            )
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

    floor_data = mlb_benchmarks.get("MLB_to_KBO")
    ceiling_data = mlb_benchmarks.get("KBO_to_MLB")
    player_wrc = float(player["wRC+"])

    bm_cols = st.columns(3)
    with bm_cols[0]:
        st.metric("This Player — wRC+", f"{player_wrc:.1f}")
    with bm_cols[1]:
        if ceiling_data is not None:
            st.metric("KBO→MLB Ceiling Avg — wRC+", f"{ceiling_data['wRC+']:.1f}")
    with bm_cols[2]:
        if floor_data is not None:
            st.metric("MLB→KBO Floor Avg — wRC+", f"{floor_data['wRC+']:.1f}")

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

elif page == PAGES[3]:
    st.title("🔥 Hot Right Now — 2026 In-Season Form")
    st.markdown(
        "Who is performing best in the KBO right now, regardless of career history. "
        "Players are scored on their 2026 stats only — no multi-year aggregation, no age multiplier — "
        "making this a pure snapshot of current-season form. A player who ranks low on the main board "
        "but appears here is someone whose recent production has outrun their track record. "
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

    # Build board rank lookup for Gap column
    board_rank_map = dict(zip(df["Name"], df["Rank"].astype(int)))

    filtered_hot = hot_df.copy()
    if hot_selected_teams:
        filtered_hot = filtered_hot[filtered_hot["Team"].isin(hot_selected_teams)]
    filtered_hot = filtered_hot[filtered_hot["PA"] >= hot_min_pa]
    filtered_hot = filtered_hot[filtered_hot["Age"] <= hot_max_age]
    filtered_hot = filtered_hot.sort_values("Score", ascending=False).reset_index(drop=True)
    filtered_hot["Hot Rank"] = range(1, len(filtered_hot) + 1)
    filtered_hot["Board Rank"] = filtered_hot["Name"].map(board_rank_map)
    # Gap = Board Rank minus Hot Rank; large positive = performing well above career track record
    filtered_hot["Gap"] = filtered_hot.apply(
        lambda r: int(r["Board Rank"] - r["Hot Rank"]) if pd.notna(r["Board Rank"]) else None,
        axis=1,
    )
    # Visual indicator for large gaps
    def _gap_label(gap):
        if gap is None or pd.isna(gap):
            return "—"
        if gap >= 20:
            return f"▲▲ +{gap}"
        if gap >= 8:
            return f"▲ +{gap}"
        if gap <= -8:
            return f"▼ {gap}"
        return f"+{gap}" if gap > 0 else str(gap)
    filtered_hot["Gap"] = filtered_hot["Gap"].apply(_gap_label)
    filtered_hot["Board Rank"] = filtered_hot["Board Rank"].apply(
        lambda v: int(v) if pd.notna(v) else None
    )

    hot_display_cols = ["Hot Rank", "Name", "Team", "Age", "PA",
                        "wRC+", "BB%", "K%", "ISO", "Spd", "Score", "Board Rank", "Gap"]

    hot_col_cfg = {
        "Hot Rank": st.column_config.NumberColumn("Hot Rank", width="small"),
        "Name":  st.column_config.TextColumn("Name",    width="medium"),
        "Team":  st.column_config.TextColumn("Team",    width="small"),
        "Age":   st.column_config.NumberColumn("Age",   width="small"),
        "PA":    st.column_config.NumberColumn("2026 PA", width="small"),
        "wRC+":  st.column_config.NumberColumn("wRC+",  format="%.1f", width="small"),
        "BB%":   st.column_config.NumberColumn("BB%",   format="%.1f%%", width="small"),
        "K%":    st.column_config.NumberColumn("K%",    format="%.1f%%", width="small"),
        "ISO":   st.column_config.NumberColumn("ISO",   format="%.3f", width="small"),
        "Spd":   st.column_config.NumberColumn("Spd",   format="%.1f", width="small"),
        "Score":      st.column_config.ProgressColumn(
            "2026 Score",
            format="%.3f",
            min_value=float(hot_df["Score"].min()),
            max_value=float(hot_df["Score"].max()),
            width="medium",
        ),
        "Board Rank": st.column_config.NumberColumn("Board Rank", width="small"),
        "Gap":        st.column_config.TextColumn(
            "Gap ↑",
            help="Board Rank minus Hot Rank. Large positive (▲▲) = performing well above career track record.",
            width="small",
        ),
    }

    st.subheader(f"Hot Right Now — {len(filtered_hot)} players")
    st.caption("**Gap** = Board Rank minus Hot Rank. ▲▲ = performing far above career projection; ▼ = cooling off relative to track record.")

    _hot_kwargs = dict(on_select="rerun", selection_mode="single-row") if _ST_SUPPORTS_SELECTION else {}
    hot_event = st.dataframe(
        filtered_hot[hot_display_cols],
        column_config=hot_col_cfg,
        use_container_width=True,
        hide_index=True,
        height=min(50 + len(filtered_hot) * 35, 900),
        **_hot_kwargs,
    )

    hot_selected_rows = (hot_event.selection.get("rows", []) if hot_event and hasattr(hot_event, "selection") and hot_event.selection else []) if _ST_SUPPORTS_SELECTION else []
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
            st.session_state["page"] = PAGES[2]
            st.rerun()

    st.divider()
    st.caption(
        "**2026 Score** = composite z-score across wRC+ (30%), BB% (25%), ISO (20%), "
        "K% inverted (15%), Spd (10%) · z-scored against 2026 qualifying pool only · no age factor applied"
    )


# ---------------------------------------------------------------------------
# Page 4 — Methodology
# ---------------------------------------------------------------------------

elif page == PAGES[0]:
    st.title("📖 Methodology")
    st.caption("How the KBO→MLB Projection Model works")
    st.divider()

    st.markdown("""
A statistical scouting tool for identifying KBO hitters most likely to succeed in MLB.
Built on four years of FanGraphs data, validated against the players who actually made
the jump. Start with the Board for rankings, or read on for how the model works.

---

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

#### Design note — why recency isn't in the composite

The career aggregate deliberately treats all seasons equally on a per-plate-appearance
basis rather than weighting recent seasons more heavily. This is a design choice, not
an oversight. Blending recency into the composite would produce a single number that
mixes two different signals — how good a player has been, and how good he is becoming —
making it harder to tell which is driving a ranking.

Instead, the model separates them. The main board answers "who has been reliably good,"
using the full career sample. The Trend column answers "who is improving," by comparing
recent performance against a player's own prior baseline. The Hot Right Now page answers
"who is performing best today," using 2026 data alone. Each view is legible on its own,
and a player who ranks low on the board but high on Trend or Hot is itself a meaningful
scouting signal: current form has outrun the track record, and the question becomes
whether it holds.

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
| ISO    | 20%    | Higher = better |
| K%     | 15%    | **Lower = better** (inverted) |
| Spd    | 10%    | Higher = better |

**Why ISO is weighted at 20%:** MLB pitchers attack hitters who pose no extra-base threat,
so power functions as something closer to a gating requirement than a bonus at the major
league level. A contact-first KBO profile with minimal ISO carries more translation risk
than its KBO production suggests. The weighting reflects that prior. (Note: within the
small crossover sample used for the ceiling and floor benchmarks, ISO did not cleanly
separate successful transitions from washouts — the weighting is based on reasoning about
MLB pitching environments rather than on that limited evidence.)

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

### Benchmarks — Ceiling and Floor

The Player Deep-Dive page shows each player's wRC+ against two reference points drawn
from real KBO crossover data: a ceiling (what successful KBO→MLB transitions looked like
in MLB) and a floor (what MLB veterans who moved to KBO produced before making that move).
Both are built using the same PA-weighted averaging method as the main model.

---

#### The Ceiling

The ceiling is the average post-transition MLB production of 9 players who moved from
the KBO to MLB: Shin-Soo Choo, Jung Hoo Lee, Ha-seong Kim, Hyun Soo Kim, Dae-Ho Lee,
Hyeseong Kim, Byung-ho Park, Sung-Mun Song, and Jae-Gyun Hwang. Their MLB stats were
PA-weighted within each player's career, then averaged equally across all 9 players,
giving a ceiling of **86.1 wRC+** (BB% 8.9%, K% 22.7%, ISO .127).

That number represents what a successful KBO→MLB transition has actually looked like
in terms of MLB offensive production.

**Why it matters — Jung Hoo Lee and Ha-seong Kim as examples:**
Lee posted a 109.0 wRC+ across 1,036 MLB plate appearances (2024–2026), improving
each season: 83 wRC+ in his first year, 107 in his second, 128 in his third. His KBO
profile — elite contact, strong walk rate, low strikeout rate — translated cleanly,
and the model ranked him top-3 in the backtest validation using only his final KBO season.

Ha-seong Kim provides a second data point with a larger sample. He posted a 103.0 wRC+
across 1,706 MLB plate appearances (2021–2024), peaking at 118.2 wRC+ in 2023 before
an injury-shortened 2024. Like Lee, his KBO profile centered on contact and discipline
rather than raw power, and he established himself as a well-above-average MLB hitter
across four seasons.

**An honest caveat:**
The sample is only 9 players, which limits precision considerably. Several transitions
are recent enough that long-term outcomes aren't established — Sung-Mun Song has 48
MLB plate appearances, Jae-Gyun Hwang just 57. Both are pulling the group average
down significantly (25.8 and 54.4 wRC+ respectively). The ceiling is best read as a
directional reference for what the KBO→MLB group has produced in MLB on average, not
a precise prediction of what any individual player will achieve.

---

#### The Floor

The floor is the average pre-KBO MLB production of 23 MLB veterans who subsequently
moved to play in the KBO — players like Daz Cameron, Aaron Altherr, Guillermo Heredia,
and others. Their MLB stats were PA-weighted within each player's career, then averaged
equally across all 23 players, giving a floor of **65.1 wRC+**.

That number represents the level of MLB production that, in practice, did not sustain
a major league career long enough to keep a player out of the KBO.

**Why it matters — Daz Cameron as an example:**
Cameron posted a 64.9 wRC+ across 472 MLB plate appearances — not enough to hold a
roster spot. He then hit 121.0 wRC+ across his KBO appearances. Elite production by
KBO standards, from a hitter MLB had already moved on from. The floor exists to make
that gap visible: strong KBO numbers alone do not establish MLB viability, because
the KBO contains players who have already demonstrated they can dominate it while
failing to stick in the majors.

**An honest caveat:**
This group is not uniformly composed of MLB washouts. Yasiel Puig (110 wRC+ in MLB)
and Patrick Wisdom (102 wRC+) were productive major league hitters who moved to the
KBO for reasons other than performance — money, playing time, roster decisions. The
floor is best read as "the average MLB outcome among players who ended up in the KBO,"
not "the average failed MLB hitter." It is a directional benchmark, not a precise
threshold, and should be interpreted accordingly.

---

### Validation — Known KBO→MLB Transitions

To test whether the model identifies the right players, two known successful KBO→MLB
transitions were run through the same pipeline used for the main board — PA-weighted
career aggregate, z-scored against the KBO_only qualifying pool, and ranked.

**Note:** K=300 Marcel shrinkage and the age multiplier were removed for this exercise
so the output reflects each player's raw statistical profile without model adjustments.
This gives a cleaner read on whether the underlying stats were genuinely elite, separate
from how the model penalizes small samples or rewards youth.

| Player | Seasons in Data | PA | Raw Composite | Hypothetical Rank | Percentile |
|--------|----------------|-----|--------------|-------------------|------------|
| Jung Hoo Lee 이정후 | 2023 only | 387 | +1.50 | **#3** | 97.4 |
| Sung-Mun Song 송성문 | 2023–2025 | 1,686 | +1.12 | **#6** | 93.6 |

**Jung Hoo Lee** — only his final KBO season (2023) is available in this dataset since
he posted to MLB after that year. Despite the single-season limitation, his profile was
top-3 material: elite contact (K% z: +2.70), strong walk rate (+1.68), and standout
wRC+ (+2.02). The full model would have shrunk his score significantly toward the pool
mean due to the small sample — this backtest removes that adjustment to show his true
statistical footprint.

**Sung-Mun Song** — three full seasons available (2023–2025, 1,686 PA), giving a robust
sample. His aggregate profile — wRC+ 129.3, BB% 10.1%, K% 12.8%, ISO .171 — scores in
the top 6. The full model applies a 0.90× age discount (he was 28 in his final KBO season),
which is removed here to show the underlying stat quality without the age penalty.

Both players would have ranked in the top 6 of the current qualifying pool on statistical
merit alone, validating that the model's underlying signals meaningfully distinguish
players who go on to succeed in MLB.

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
