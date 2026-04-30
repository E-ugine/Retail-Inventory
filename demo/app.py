import streamlit as st
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
import folium
from folium.plugins import HeatMap
from streamlit_folium import st_folium
from sqlalchemy import create_engine
from dotenv import load_dotenv
from pathlib import Path
import os

load_dotenv()
DB_URL = os.getenv("DATABASE_URL")

# -------------------------------------------------------
# Page config
# -------------------------------------------------------
st.set_page_config(
    page_title="Kisumu Retail Intelligence",
    page_icon="🛒",
    layout="wide",
    initial_sidebar_state="expanded"
)

# -------------------------------------------------------
# Data loading — cached so it only runs once
# -------------------------------------------------------
@st.cache_data
def load_data():
    engine = create_engine(DB_URL)
    
    outlets = pd.read_sql("""
        SELECT osm_id, name, shop_type, latitude, longitude, suburb, road
        FROM outlets_fmcg;
    """, engine)
    
    velocity = pd.read_sql("SELECT * FROM intel_sales_velocity;", engine)
    
    stockout = pd.read_sql("""
        SELECT * FROM intel_stockout_probability
        ORDER BY stockout_probability DESC;
    """, engine)
    
    coverage = pd.read_sql("SELECT * FROM intel_coverage_gaps;", engine)
    
    invoices = pd.read_sql("""
        SELECT invoice_date, suburb, category, brand,
               quantity, line_total, distributor_id
        FROM synthetic_invoices;
    """, engine)
    invoices["invoice_date"] = pd.to_datetime(invoices["invoice_date"])
    
    return outlets, velocity, stockout, coverage, invoices

outlets, velocity, stockout, coverage, invoices = load_data()

# -------------------------------------------------------
# Sidebar
# -------------------------------------------------------
st.sidebar.image("https://via.placeholder.com/200x60?text=Kisumu+Retail+Intel",
                 use_container_width=True)
st.sidebar.markdown("---")
st.sidebar.markdown("**Data period:** Jul – Dec 2024")
st.sidebar.markdown("**City:** Kisumu, Kenya")
st.sidebar.markdown("**Outlets tracked:** 256")
st.sidebar.markdown("**SKUs monitored:** 24")
st.sidebar.markdown("**Invoice lines:** 50,605")
st.sidebar.markdown("---")
st.sidebar.caption(
    "⚠️ Powered by synthetic transaction data modelled on "
    "Kisumu informal retail structure. "
    "Contact us to integrate real distributor data."
)

page = st.sidebar.radio(
    "Navigate",
    ["🏙️ City Overview", "📈 Sales Velocity",
     "⚠️ Stockout Signals", "🗺️ Coverage Gaps"]
)

# -------------------------------------------------------
# PAGE 1: City Overview
# -------------------------------------------------------
if page == "🏙️ City Overview":
    st.title("🏙️ Kisumu Informal Retail — City Overview")
    st.markdown(
        "A spatial snapshot of FMCG-relevant retail outlets across Kisumu, "
        "derived from OpenStreetMap and enriched with demand intelligence."
    )

    # KPI row
    col1, col2, col3, col4 = st.columns(4)
    col1.metric("FMCG Outlets Mapped", "256")
    col2.metric("Suburbs Covered", str(outlets["suburb"].nunique()))
    col3.metric("Simulated Revenue", "KES 145.7M")
    col4.metric("Stockout Signals", "36")

    st.markdown("---")

    # Map
    st.subheader("Outlet Map")
    
    m = folium.Map(
        location=[-0.091, 34.769],
        zoom_start=13,
        tiles="CartoDB positron"
    )

    # Color by shop type
    color_map = {
        "supermarket": "red",
        "wholesale": "blue",
        "chemist": "green",
        "kiosk": "orange",
        "butcher": "purple",
        "greengrocer": "darkgreen",
        "convenience": "cadetblue",
    }

    for _, row in outlets.dropna(subset=["latitude", "longitude"]).iterrows():
        color = color_map.get(row["shop_type"], "gray")
        folium.CircleMarker(
            location=[row["latitude"], row["longitude"]],
            radius=5,
            color=color,
            fill=True,
            fill_opacity=0.7,
            popup=folium.Popup(
                f"<b>{row['name']}</b><br>"
                f"Type: {row['shop_type']}<br>"
                f"Suburb: {row.get('suburb', 'Unknown')}",
                max_width=200
            )
        ).add_to(m)

    st_folium(m, width=1100, height=500)

    # Shop type breakdown
    st.markdown("---")
    st.subheader("Outlet Type Breakdown")
    type_counts = outlets["shop_type"].value_counts().reset_index()
    type_counts.columns = ["shop_type", "count"]
    
    fig = px.bar(
        type_counts,
        x="shop_type", y="count",
        color="count",
        color_continuous_scale="Blues",
        labels={"shop_type": "Outlet Type", "count": "Count"},
    )
    fig.update_layout(showlegend=False, height=350)
    st.plotly_chart(fig, use_container_width=True)

# -------------------------------------------------------
# PAGE 2: Sales Velocity
# -------------------------------------------------------
elif page == "📈 Sales Velocity":
    st.title("📈 Sales Velocity — Last 4 Weeks")
    st.markdown(
        "Total units sold per suburb per category in the last 4 weeks of the data period. "
        "Higher velocity = higher restocking priority."
    )

    # Filters
    col1, col2 = st.columns(2)
    with col1:
        selected_category = st.selectbox(
            "Filter by category",
            ["All"] + sorted(velocity["category"].unique().tolist())
        )
    with col2:
        top_n = st.slider("Show top N suburbs", 5, 20, 10)

    filtered = velocity.copy()
    if selected_category != "All":
        filtered = filtered[filtered["category"] == selected_category]

    top_suburbs = (
        filtered.groupby("suburb")["total_units"]
        .sum()
        .nlargest(top_n)
        .index.tolist()
    )
    filtered = filtered[filtered["suburb"].isin(top_suburbs)]

    # Heatmap
    st.subheader("Velocity Heatmap — Units Sold")
    pivot = filtered.pivot_table(
        index="suburb", columns="category",
        values="total_units", aggfunc="sum", fill_value=0
    )

    fig = px.imshow(
        pivot,
        color_continuous_scale="YlOrRd",
        labels={"color": "Units Sold"},
        aspect="auto",
        height=450
    )
    fig.update_layout(
        xaxis_title="Category",
        yaxis_title="Suburb",
    )
    st.plotly_chart(fig, use_container_width=True)

    # Revenue bar chart
    st.subheader("Revenue by Suburb (KES)")
    rev_by_suburb = (
        filtered.groupby("suburb")["total_revenue"]
        .sum()
        .sort_values(ascending=True)
        .reset_index()
    )
    fig2 = px.bar(
        rev_by_suburb,
        x="total_revenue", y="suburb",
        orientation="h",
        color="total_revenue",
        color_continuous_scale="Blues",
        labels={"total_revenue": "Revenue (KES)", "suburb": "Suburb"},
        height=400
    )
    fig2.update_layout(showlegend=False)
    st.plotly_chart(fig2, use_container_width=True)

    # Raw table
    with st.expander("View raw velocity data"):
        st.dataframe(
            filtered.sort_values("total_units", ascending=False),
            use_container_width=True
        )

# -------------------------------------------------------
# PAGE 3: Stockout Signals
# -------------------------------------------------------
elif page == "⚠️ Stockout Signals":
    st.title("⚠️ Stockout Signals")
    st.markdown(
        "Outlets where current implied inventory is critically low "
        "based on last delivery date and average depletion rate."
    )

    # Filters
    col1, col2 = st.columns(2)
    with col1:
        prob_filter = st.selectbox(
            "Minimum stockout probability",
            ["All", "Medium (≥25%)", "High (≥50%)", "Critical (≥75%)"]
        )
    with col2:
        cat_filter = st.selectbox(
            "Category",
            ["All"] + sorted(stockout["category"].dropna().unique().tolist())
        )

    filtered_s = stockout.copy()
    if prob_filter == "Medium (≥25%)":
        filtered_s = filtered_s[filtered_s["stockout_probability"] >= 0.25]
    elif prob_filter == "High (≥50%)":
        filtered_s = filtered_s[filtered_s["stockout_probability"] >= 0.50]
    elif prob_filter == "Critical (≥75%)":
        filtered_s = filtered_s[filtered_s["stockout_probability"] >= 0.75]

    if cat_filter != "All":
        filtered_s = filtered_s[filtered_s["category"] == cat_filter]

    # KPIs
    col1, col2, col3 = st.columns(3)
    col1.metric("Total Signals", len(filtered_s))
    col2.metric(
        "Critical (≥75%)",
        len(filtered_s[filtered_s["stockout_probability"] >= 0.75])
    )
    col3.metric(
        "Outlets Affected",
        filtered_s["outlet_osm_id"].nunique()
    )

    # Probability distribution
    st.subheader("Stockout Probability Distribution")
    bins = pd.cut(
        filtered_s["stockout_probability"],
        bins=[0, 0.25, 0.5, 0.75, 1.01],
        labels=["Low", "Medium", "High", "Critical"]
    ).value_counts().sort_index().reset_index()
    bins.columns = ["Risk Level", "Count"]

    color_seq = ["#2ecc71", "#f39c12", "#e67e22", "#e74c3c"]
    fig3 = px.bar(
        bins, x="Risk Level", y="Count",
        color="Risk Level",
        color_discrete_sequence=color_seq,
        height=300
    )
    fig3.update_layout(showlegend=False)
    st.plotly_chart(fig3, use_container_width=True)

    # Critical stockout map
    st.subheader("Critical Stockout Locations")
    critical = filtered_s[
        (filtered_s["stockout_probability"] >= 0.75) &
        filtered_s["outlet_lat"].notna()
    ]

    if len(critical) > 0:
        m2 = folium.Map(location=[-0.091, 34.769],
                        zoom_start=13, tiles="CartoDB positron")
        for _, row in critical.iterrows():
            folium.CircleMarker(
                location=[row["outlet_lat"], row["outlet_lon"]],
                radius=8,
                color="red",
                fill=True,
                fill_color="red",
                fill_opacity=0.8,
                popup=folium.Popup(
                    f"<b>{row['outlet_name']}</b><br>"
                    f"Category: {row['category']}<br>"
                    f"Product: {row['product_name']}<br>"
                    f"Stockout prob: {row['stockout_probability']*100:.0f}%<br>"
                    f"Days since delivery: {row['days_since_delivery']}",
                    max_width=220
                )
            ).add_to(m2)
        st_folium(m2, width=1100, height=400)
    else:
        st.info("No critical stockout locations match current filters.")

    # Table
    st.subheader("Stockout Detail Table")
    display_cols = [
        "outlet_name", "outlet_type", "suburb",
        "category", "product_name",
        "last_delivery_date", "days_since_delivery",
        "stockout_probability"
    ]
    st.dataframe(
        filtered_s[display_cols]
        .sort_values("stockout_probability", ascending=False)
        .reset_index(drop=True),
        use_container_width=True
    )

# -------------------------------------------------------
# PAGE 4: Coverage Gaps
# -------------------------------------------------------
elif page == "🗺️ Coverage Gaps":
    st.title("🗺️ Coverage Gap Analysis")
    st.markdown(
        "Outlets ranked by visit frequency over the 26-week period. "
        "Low frequency outlets in high-velocity suburbs represent "
        "the highest-priority distributor opportunities."
    )

    # Service level summary
    st.subheader("Outlet Service Level Distribution")
    service_counts = coverage["service_level"].value_counts().reset_index()
    service_counts.columns = ["Service Level", "Count"]

    color_map_s = {
        "Well served": "#2ecc71",
        "Moderately served": "#f39c12",
        "Underserved": "#e74c3c"
    }

    fig4 = px.pie(
        service_counts,
        names="Service Level", values="Count",
        color="Service Level",
        color_discrete_map=color_map_s,
        height=350
    )
    st.plotly_chart(fig4, use_container_width=True)

    # Visit frequency scatter map
    st.subheader("Visit Frequency by Outlet Location")
    map_data = coverage.dropna(subset=["outlet_lat", "outlet_lon"])

    m3 = folium.Map(location=[-0.091, 34.769],
                    zoom_start=13, tiles="CartoDB positron")

    for _, row in map_data.iterrows():
        freq = row["visit_frequency"]
        if freq >= 0.7:
            color = "green"
        elif freq >= 0.4:
            color = "orange"
        else:
            color = "red"

        folium.CircleMarker(
            location=[row["outlet_lat"], row["outlet_lon"]],
            radius=6,
            color=color,
            fill=True,
            fill_opacity=0.75,
            popup=folium.Popup(
                f"<b>{row['outlet_name']}</b><br>"
                f"Type: {row['outlet_type']}<br>"
                f"Suburb: {row.get('suburb', 'Unknown')}<br>"
                f"Visit frequency: {freq*100:.0f}%<br>"
                f"Weeks active: {row['weeks_active']}/26<br>"
                f"Revenue: KES {row['total_revenue']:,.0f}",
                max_width=220
            )
        ).add_to(m3)

    st_folium(m3, width=1100, height=500)

    # Bottom outlets table
    st.subheader("Most Underserved Outlets")
    st.markdown(
        "These outlets have the lowest visit frequency — "
        "highest priority for distributor outreach."
    )

    bottom_outlets = (
        coverage
        .sort_values("visit_frequency")
        .head(20)[["outlet_name", "outlet_type", "suburb",
                    "weeks_active", "visit_frequency",
                    "total_revenue", "skus_purchased"]]
        .reset_index(drop=True)
    )
    bottom_outlets["visit_frequency"] = (
        bottom_outlets["visit_frequency"] * 100
    ).round(1).astype(str) + "%"

    st.dataframe(bottom_outlets, use_container_width=True)