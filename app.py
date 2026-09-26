import folium
import pandas as pd
import streamlit as st
from streamlit_folium import st_folium

from proximity import build_opportunity_table, estimate_shared_cost_savings, find_geographic_overlaps

st.set_page_config(page_title="Gridlock — Utility Coordination Finder", layout="wide")

UTILITY_COLORS = {"DESC": "#1f77b4", "GPC": "#d62728"}

st.title("⚡ Gridlock — Cross-Utility Coordination Finder")
st.caption(
    "Flags planned transmission/substation projects from two neighboring utilities that are "
    "geographically close, and highlights which of those also overlap in build timeline."
)

# ---- Sidebar controls ----
st.sidebar.header("Settings")
radius_miles = st.sidebar.slider("Geographic overlap threshold (miles)", min_value=5, max_value=60, value=25, step=5)

uploaded = st.sidebar.file_uploader("Upload your own CSV (optional)", type="csv")
if uploaded is not None:
    df = pd.read_csv(uploaded)
else:
    try:
        df = pd.read_csv("data/projects.csv")
    except FileNotFoundError:
        st.error("No data found at data/projects.csv. Run `python generate_mock_data.py` first.")
        st.stop()

required_cols = {"id", "name", "utility", "type", "status", "lat", "lon", "start_date", "end_date"}
missing = required_cols - set(df.columns)
if missing:
    st.error(f"Uploaded data is missing required columns: {missing}")
    st.stop()

utilities = sorted(df["utility"].unique())
if len(utilities) < 2:
    st.warning("Need at least two utilities in the data to find cross-utility overlaps.")

status_filter = st.sidebar.multiselect(
    "Filter by status", options=sorted(df["status"].unique()), default=sorted(df["status"].unique())
)
type_filter = st.sidebar.multiselect(
    "Filter by project type", options=sorted(df["type"].unique()), default=sorted(df["type"].unique())
)

df = df[df["status"].isin(status_filter) & df["type"].isin(type_filter)].reset_index(drop=True)

# ---- Overlap analysis ----
overlap_df = find_geographic_overlaps(df, radius_miles=radius_miles)
opportunity_df = build_opportunity_table(df, overlap_df, radius_miles=radius_miles)

flagged_ids = set()
if not overlap_df.empty:
    flagged_ids = set(overlap_df["project_a"]).union(set(overlap_df["project_b"]))

# ---- Top-line metrics ----
col1, col2, col3, col4 = st.columns(4)
col1.metric("Total projects", len(df))
col2.metric(f"Projects within {radius_miles}mi of the other utility", len(flagged_ids))
col3.metric("Geographic overlaps", len(overlap_df))
col4.metric("...also timeline overlap", int(opportunity_df["timeline_overlap"].sum()) if not opportunity_df.empty else 0)

# ---- Map ----
st.subheader("Map")
if len(df):
    m = folium.Map(location=[df["lat"].mean(), df["lon"].mean()], zoom_start=7, tiles="OpenStreetMap")

    for _, row in df.iterrows():
        is_flagged = row["id"] in flagged_ids
        folium.CircleMarker(
            location=[row["lat"], row["lon"]],
            radius=7 if is_flagged else 4,
            color=UTILITY_COLORS.get(row["utility"], "#777777"),
            fill=True,
            fill_opacity=0.9 if is_flagged else 0.5,
            weight=2 if is_flagged else 1,
            popup=folium.Popup(
                f"<b>{row['name']}</b><br>"
                f"Utility: {row['utility']}<br>"
                f"Type: {row['type']}<br>"
                f"Status: {row['status']}<br>"
                f"Window: {row['start_date']} → {row['end_date']}",
                max_width=250,
            ),
        ).add_to(m)

    for _, row in overlap_df.iterrows():
        a = df[df["id"] == row["project_a"]].iloc[0]
        b = df[df["id"] == row["project_b"]].iloc[0]
        folium.PolyLine(
            locations=[[a["lat"], a["lon"]], [b["lat"], b["lon"]]],
            color="#ff7f0e",
            weight=1.5,
            opacity=0.7,
            tooltip=f"{row['distance_miles']} mi apart",
        ).add_to(m)

    legend_html = "".join(
        f'<span style="color:{color}; font-weight:bold;">● {u}</span>&nbsp;&nbsp;'
        for u, color in UTILITY_COLORS.items()
    )
    st.markdown(legend_html, unsafe_allow_html=True)
    st_folium(m, width=None, height=550, use_container_width=True)
else:
    st.info("No projects match the current filters.")

# ---- Ranked coordination opportunities ----
st.subheader("Ranked Coordination Opportunities")
if opportunity_df.empty:
    st.write(f"No cross-utility geographic overlaps found within {radius_miles} miles at current filters.")
else:
    display_df = opportunity_df.rename(columns={
        "name_a": "Project A", "utility_a": "Utility A", "type_a": "Type A",
        "name_b": "Project B", "utility_b": "Utility B", "type_b": "Type B",
        "distance_miles": "Distance (mi)", "timeline_overlap": "Timeline Overlap",
        "coordination_score": "Score",
    })[[
        "Project A", "Utility A", "Type A",
        "Project B", "Utility B", "Type B",
        "Distance (mi)", "Timeline Overlap", "Score",
    ]]
    st.dataframe(display_df, width="stretch", hide_index=True)

    csv = opportunity_df.to_csv(index=False).encode("utf-8")
    st.download_button("Download ranked opportunities as CSV", csv, "coordination_opportunities.csv", "text/csv")

    # ---- Bonus: rough cost/impact estimate for the top opportunity ----
    st.subheader("Cost/Impact Estimate (top opportunity)")
    top_row = opportunity_df.iloc[0]
    estimate = estimate_shared_cost_savings(top_row)
    st.markdown(
        f"**{top_row['name_a']}** ({top_row['utility_a']}) ↔ **{top_row['name_b']}** ({top_row['utility_b']}) "
        f"— {top_row['distance_miles']} mi apart, "
        f"{'timeline overlap' if top_row['timeline_overlap'] else 'no timeline overlap'}"
    )
    if estimate.get("applicable"):
        st.success(
            f"Estimated shareable right-of-way: **{estimate['shared_length_miles']} mi** → "
            f"rough savings estimate: **${estimate['estimated_savings_usd']:,}**"
        )
        st.caption(estimate["assumption"] + " — this is a placeholder assumption for demo purposes, not a sourced cost figure.")
    else:
        st.info("Cost estimate only implemented for Transmission Line ↔ Transmission Line pairs. "
                 "This top-ranked pair is a different project-type combination.")

# ---- Raw data (collapsible) ----
with st.expander("View raw project data"):
    st.dataframe(df, width="stretch", hide_index=True)
