import pandas as pd
import numpy as np
from sqlalchemy import create_engine, text
from pathlib import Path
from dotenv import load_dotenv
from datetime import date, timedelta
import os

load_dotenv()
DB_URL = os.getenv("DATABASE_URL")
OUTPUT_DIR = Path("data/processed")
OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

SIMULATION_END = date(2024, 12, 23)

def get_engine():
    return create_engine(DB_URL)

# -------------------------------------------------------
# MODULE 1: Sales Velocity
# Rolling 4-week average units sold per SKU
# per geographic cluster (suburb)
# -------------------------------------------------------
def sales_velocity(engine):
    print("\n=== MODULE 1: Sales Velocity ===")

    df = pd.read_sql("""
        SELECT
            invoice_date,
            suburb,
            category,
            brand,
            sku,
            product_name,
            quantity,
            line_total,
            distributor_id
        FROM synthetic_invoices
        WHERE suburb IS NOT NULL
        ORDER BY invoice_date;
    """, engine)

    df["invoice_date"] = pd.to_datetime(df["invoice_date"])

    # 4-week rolling window ending at simulation end
    window_start = pd.Timestamp(SIMULATION_END) - timedelta(weeks=4)
    recent = df[df["invoice_date"] >= window_start]

    # Velocity = total units sold in last 4 weeks per suburb per category
    velocity = (
        recent.groupby(["suburb", "category"])
        .agg(
            total_units=("quantity", "sum"),
            total_revenue=("line_total", "sum"),
            transaction_count=("quantity", "count"),
            brands=("brand", lambda x: ", ".join(sorted(set(x))))
        )
        .reset_index()
        .sort_values("total_units", ascending=False)
    )

    # Save
    out_path = OUTPUT_DIR / "sales_velocity.csv"
    velocity.to_csv(out_path, index=False)

    print(f"\nTop 10 suburb-category combinations by 4-week velocity:")
    print(f"\n{'Suburb':<25} {'Category':<15} {'Units':>7} {'Revenue (KES)':>14}")
    print("-" * 65)
    for _, row in velocity.head(10).iterrows():
        print(f"{str(row['suburb'])[:24]:<25} {row['category']:<15} "
              f"{row['total_units']:>7.0f} {row['total_revenue']:>14,.0f}")

    return velocity

# -------------------------------------------------------
# MODULE 2: Stockout Probability
# For each outlet-SKU, estimate current inventory level
# based on last delivery date and average depletion rate
# -------------------------------------------------------
def stockout_probability(engine):
    print("\n=== MODULE 2: Stockout Probability ===")

    df = pd.read_sql("""
        SELECT
            outlet_osm_id,
            outlet_name,
            outlet_type,
            suburb,
            outlet_lat,
            outlet_lon,
            sku,
            category,
            product_name,
            invoice_date,
            quantity
        FROM synthetic_invoices
        ORDER BY outlet_osm_id, sku, invoice_date;
    """, engine)

    df["invoice_date"] = pd.to_datetime(df["invoice_date"])
    simulation_end = pd.Timestamp(SIMULATION_END)

    records = []

    for (outlet_id, sku), group in df.groupby(["outlet_osm_id", "sku"]):
        group = group.sort_values("invoice_date")

        if len(group) < 2:
            continue

        # Last delivery
        last_delivery_date = group["invoice_date"].max()
        last_delivery_qty = group[
            group["invoice_date"] == last_delivery_date
        ]["quantity"].sum()

        # Average weekly depletion — inferred from order frequency and quantity
        date_diffs = group["invoice_date"].diff().dt.days.dropna()
        avg_days_between_orders = date_diffs.mean()
        avg_order_qty = group["quantity"].mean()

        if avg_days_between_orders <= 0:
            continue

        # Daily depletion rate
        daily_depletion = avg_order_qty / avg_days_between_orders

        # Days since last delivery
        days_since_delivery = (simulation_end - last_delivery_date).days

        # Implied current stock
        implied_stock = last_delivery_qty - (daily_depletion * days_since_delivery)

        # Stockout probability — how far below zero are we?
        if implied_stock <= 0:
            stockout_prob = 1.0
        elif implied_stock < avg_order_qty * 0.25:
            stockout_prob = 0.75
        elif implied_stock < avg_order_qty * 0.5:
            stockout_prob = 0.5
        else:
            stockout_prob = 0.1

        records.append({
            "outlet_osm_id": outlet_id,
            "outlet_name": group["outlet_name"].iloc[0],
            "outlet_type": group["outlet_type"].iloc[0],
            "suburb": group["suburb"].iloc[0],
            "outlet_lat": group["outlet_lat"].iloc[0],
            "outlet_lon": group["outlet_lon"].iloc[0],
            "sku": sku,
            "category": group["category"].iloc[0],
            "product_name": group["product_name"].iloc[0],
            "last_delivery_date": last_delivery_date.date().isoformat(),
            "days_since_delivery": int(days_since_delivery),
            "implied_stock": round(implied_stock, 1),
            "daily_depletion": round(daily_depletion, 2),
            "stockout_probability": stockout_prob,
        })

    stockout_df = pd.DataFrame(records)

    # Save
    out_path = OUTPUT_DIR / "stockout_probability.csv"
    stockout_df.to_csv(out_path, index=False)

    # Summary by suburb
    print(f"\nStockout probability summary:")
    prob_counts = stockout_df.groupby(
        pd.cut(stockout_df["stockout_probability"],
               bins=[0, 0.25, 0.5, 0.75, 1.01],
               labels=["Low (<25%)", "Medium (25-50%)",
                       "High (50-75%)", "Critical (>75%)"])
    ).size()

    for label, count in prob_counts.items():
        bar = "█" * int(count / prob_counts.max() * 25)
        print(f"  {str(label):<20} {count:>6} outlet-SKUs  {bar}")

    # Top 10 critical stockouts
    critical = (
        stockout_df[stockout_df["stockout_probability"] >= 0.75]
        .groupby(["suburb", "category"])
        .agg(affected_outlets=("outlet_osm_id", "nunique"))
        .sort_values("affected_outlets", ascending=False)
        .head(10)
    )

    print(f"\nTop 10 critical stockout zones (suburb × category):")
    print(f"\n{'Suburb':<25} {'Category':<15} {'Outlets Affected':>16}")
    print("-" * 58)
    for (suburb, cat), row in critical.iterrows():
        print(f"{str(suburb)[:24]:<25} {cat:<15} {row['affected_outlets']:>16}")

    return stockout_df

# -------------------------------------------------------
# MODULE 3: Coverage Gap Analysis
# Suburbs with high outlet density but low
# distributor transaction frequency
# -------------------------------------------------------
def coverage_gap_analysis(engine):
    print("\n=== MODULE 3: Coverage Gap Analysis ===")

    # Visit frequency per outlet — out of 26 possible weeks
    visit_freq = pd.read_sql("""
        SELECT
            outlet_osm_id,
            outlet_name,
            outlet_type,
            suburb,
            outlet_lat,
            outlet_lon,
            COUNT(DISTINCT DATE_TRUNC('week', invoice_date::timestamp)) as weeks_active,
            SUM(line_total) as total_revenue,
            COUNT(DISTINCT sku) as skus_purchased
        FROM synthetic_invoices
        GROUP BY outlet_osm_id, outlet_name, outlet_type,
                 suburb, outlet_lat, outlet_lon;
    """, engine)

    TOTAL_WEEKS = 26
    visit_freq["visit_frequency"] = (
        visit_freq["weeks_active"] / TOTAL_WEEKS
    ).round(3)

    # Classify outlets
    def classify(freq):
        if freq >= 0.7:
            return "Well served"
        elif freq >= 0.4:
            return "Moderately served"
        else:
            return "Underserved"

    visit_freq["service_level"] = visit_freq["visit_frequency"].apply(classify)

    # Save
    out_path = OUTPUT_DIR / "coverage_gaps.csv"
    visit_freq.to_csv(out_path, index=False)

    # Summary by service level
    service_summary = visit_freq.groupby("service_level").agg(
        outlet_count=("outlet_osm_id", "count"),
        avg_weeks_active=("weeks_active", "mean"),
        avg_revenue=("total_revenue", "mean")
    ).round(1)

    print(f"\nOutlet service level distribution:")
    print(f"\n{'Service Level':<20} {'Outlets':>8} {'Avg Weeks Active':>16} {'Avg Revenue (KES)':>18}")
    print("-" * 65)
    for level, row in service_summary.iterrows():
        print(f"{level:<20} {row['outlet_count']:>8} "
              f"{row['avg_weeks_active']:>16.1f} "
              f"{row['avg_revenue']:>18,.0f}")

    # Underserved outlets by suburb
    underserved = (
        visit_freq[visit_freq["service_level"] == "Underserved"]
        .groupby("suburb")
        .agg(
            underserved_outlets=("outlet_osm_id", "count"),
            avg_frequency=("visit_frequency", "mean")
        )
        .sort_values("underserved_outlets", ascending=False)
        .head(10)
    )

    print(f"\nTop 10 suburbs with underserved outlets:")
    print(f"\n{'Suburb':<25} {'Underserved Outlets':>20} {'Avg Visit Freq':>15}")
    print("-" * 62)
    for suburb, row in underserved.iterrows():
        print(f"{str(suburb)[:24]:<25} {row['underserved_outlets']:>20} "
              f"{row['avg_frequency']:>15.2%}")

    # Bottom 10 outlets by visit frequency — most neglected
    print(f"\nBottom 10 outlets by visit frequency:")
    print(f"\n{'Outlet':<28} {'Type':<14} {'Suburb':<20} {'Freq':>6}")
    print("-" * 72)
    bottom = visit_freq.nsmallest(10, "visit_frequency")
    for _, row in bottom.iterrows():
        print(f"{str(row['outlet_name'])[:27]:<28} "
              f"{row['outlet_type']:<14} "
              f"{str(row['suburb'])[:19]:<20} "
              f"{row['visit_frequency']:>6.1%}")

    return visit_freq

def main():
    engine = get_engine()

    velocity = sales_velocity(engine)
    stockout_df = stockout_probability(engine)
    coverage = coverage_gap_analysis(engine)

    # Load all three into database
    print("\nLoading intelligence tables into database...")
    with engine.connect() as conn:
        velocity.to_sql("intel_sales_velocity", conn,
                        if_exists="replace", index=False)
        stockout_df.to_sql("intel_stockout_probability", conn,
                           if_exists="replace", index=False)
        coverage.to_sql("intel_coverage_gaps", conn,
                        if_exists="replace", index=False)
        conn.commit()

    print("Loaded: intel_sales_velocity")
    print("Loaded: intel_stockout_probability")
    print("Loaded: intel_coverage_gaps")
    print("\nDemand Atlas intelligence layer complete.")

if __name__ == "__main__":
    main()