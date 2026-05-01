import pandas as pd
import numpy as np
from sqlalchemy import create_engine, text
from pathlib import Path
from dotenv import load_dotenv
from datetime import date, timedelta
import os
import random

load_dotenv()
DB_URL = os.getenv("DATABASE_URL")
OUTPUT_DIR = Path("data/synthetic")
OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

# Simulation parameters
START_DATE = date(2024, 7, 1)
WEEKS = 26  # 6 months
REORDER_THRESHOLD = 0.25  # reorder when stock drops below 25% of weekly demand

"""
# Distributors — 5 synthetic distributors covering
# different geographic zones of Kisumu
"""

DISTRIBUTORS = [
    {"id": "DIST_001", "name": "Kisumu Central Distributors",
     "lat": -0.091, "lon": 34.769, "zone": "CBD"},
    
    {"id": "DIST_002", "name": "Manyatta FMCG Supplies",
     "lat": -0.068, "lon": 34.794, "zone": "Manyatta"},
    
    {"id": "DIST_003", "name": "Kondele Wholesale Agency",
     "lat": -0.105, "lon": 34.763, "zone": "Kondele"},
    
    {"id": "DIST_004", "name": "Kibos Road Distributors",
     "lat": -0.078, "lon": 34.812, "zone": "Kibos"},
    
    {"id": "DIST_005", "name": "Nyalenda General Supplies",
     "lat": -0.115, "lon": 34.748, "zone": "Nyalenda"},
]

def assign_distributors(outlets_df):
    """Assign each outlet to nearest distributor."""
    dist_df = pd.DataFrame(DISTRIBUTORS)
    
    assignments = []
    for _, outlet in outlets_df.iterrows():
        # Calculate distance to each distributor
        distances = np.sqrt(
            (dist_df["lat"] - outlet["latitude"]) ** 2 +
            (dist_df["lon"] - outlet["longitude"]) ** 2
        )
        nearest = dist_df.iloc[distances.idxmin()]
        assignments.append(nearest["id"])
    
    outlets_df = outlets_df.copy()
    outlets_df["distributor_id"] = assignments
    return outlets_df

def simulate_outlet_invoices(outlet, profiles_for_outlet, products):
    """
    Simulate 26 weeks of purchases for one outlet.
    Returns a list of invoice records.
    """
    invoices = []
    
    # Build initial stock — start with 2 weeks of supply
    stock = {}
    weekly_demand = {}
    for _, profile in profiles_for_outlet.iterrows():
        sku = profile["sku"]
        weekly_demand[sku] = profile["weekly_units"]
        stock[sku] = profile["weekly_units"] * 2
    
    current_date = START_DATE
    
    for week in range(WEEKS):
        week_date = current_date + timedelta(weeks=week)
        
        """
        # Add some irregular ordering behaviour
        # 5% chance outlet skips ordering this week (stockout/holiday)
        """
        if random.random() < 0.05:
            # Deplete stock but don't order
            for sku in stock:
                stock[sku] = max(0, stock[sku] - weekly_demand[sku])
            continue
        
        # Check each SKU — does outlet need to reorder?
        order_items = []
        for sku, current_stock in stock.items():
            threshold = weekly_demand[sku] * REORDER_THRESHOLD
            
            if current_stock <= threshold:
                weeks_to_order = random.randint(2, 4) #2-4 wks
                order_qty = round(weekly_demand[sku] * weeks_to_order)
                order_qty = max(1, order_qty)
                order_items.append((sku, order_qty))
                stock[sku] += order_qty
        
        for sku, qty in order_items:
            product = products[products["sku"] == sku].iloc[0]
            
            price_variance = random.uniform(0.95, 1.05)
            unit_price = round(product["wholesale_price"] * price_variance, 2)
            
            invoices.append({
                "invoice_date": week_date.isoformat(),
                "distributor_id": outlet["distributor_id"],
                "outlet_osm_id": outlet["osm_id"],
                "outlet_name": outlet["name"],
                "outlet_type": outlet["shop_type"],
                "outlet_lat": outlet["latitude"],
                "outlet_lon": outlet["longitude"],
                "suburb": outlet.get("suburb", None),
                "sku": sku,
                "product_name": product["name"],
                "brand": product["brand"],
                "category": product["category"],
                "quantity": qty,
                "unit_price": unit_price,
                "line_total": round(qty * unit_price, 2),
                "size_tier": outlet.get("size_tier", "small"),
                "week_number": week + 1,
            })
        
        # Deplete stock for the week regardless
        for sku in stock:
            stock[sku] = max(0, stock[sku] - weekly_demand[sku])
    
    return invoices

def run_simulation(engine):
    print("Loading data...")
    
    with engine.connect() as conn:
        outlets = pd.read_sql("""
            SELECT f.osm_id, f.name, f.shop_type, f.latitude, f.longitude
            FROM outlets_fmcg f
            ORDER BY f.osm_id;
        """, conn)
        
        profiles = pd.read_sql("""
            SELECT osm_id, sku, category, weekly_units, size_tier
            FROM demand_profiles;
        """, conn)
        
        products = pd.read_sql("SELECT * FROM product_catalog;", conn)
    
    # Try to load geocoded suburb data
    geocoded_path = Path("data/processed/kisumu_fmcg_outlets_geocoded.csv")
    if geocoded_path.exists():
        geocoded = pd.read_csv(geocoded_path)[["osm_id", "suburb", "road"]]
        outlets = outlets.merge(geocoded, on="osm_id", how="left")
    
    # Merge size tier from profiles
    tier_map = profiles.drop_duplicates("osm_id")[["osm_id", "size_tier"]]
    outlets = outlets.merge(tier_map, on="osm_id", how="left")
    
    # Assign distributors
    outlets = assign_distributors(outlets)
    
    print(f"Simulating {WEEKS} weeks for {len(outlets)} outlets × {len(products)} SKUs...")
    print(f"Period: {START_DATE} to {START_DATE + timedelta(weeks=WEEKS)}\n")
    
    all_invoices = []
    
    for i, (_, outlet) in enumerate(outlets.iterrows()):
        outlet_profiles = profiles[profiles["osm_id"] == outlet["osm_id"]]
        invoices = simulate_outlet_invoices(outlet, outlet_profiles, products)
        all_invoices.extend(invoices)
        
        if (i + 1) % 50 == 0:
            print(f"  Simulated {i + 1}/{len(outlets)} outlets "
                  f"({len(all_invoices):,} invoice lines so far)...")
    
    df = pd.DataFrame(all_invoices)
    print(f"\nTotal invoice lines generated: {len(df):,}")
    return df

def analyse_invoices(df):
    print("\n=== Simulation Summary ===")
    
    # Overall stats
    print(f"\nDate range: {df['invoice_date'].min()} → {df['invoice_date'].max()}")
    print(f"Total invoice lines: {len(df):,}")
    print(f"Total simulated revenue: KES {df['line_total'].sum():,.0f}")
    print(f"Unique outlets transacting: {df['outlet_osm_id'].nunique()}")
    print(f"Unique SKUs sold: {df['sku'].nunique()}")
    
    # Revenue by distributor
    print("\nRevenue by distributor:")
    dist_rev = df.groupby("distributor_id")["line_total"].sum().sort_values(ascending=False)
    for dist_id, rev in dist_rev.items():
        dist_name = next(d["name"] for d in DISTRIBUTORS if d["id"] == dist_id)
        print(f"  {dist_name:<35} KES {rev:>12,.0f}")
    
    # Revenue by category
    print("\nRevenue by category:")
    cat_rev = df.groupby("category")["line_total"].sum().sort_values(ascending=False)
    for cat, rev in cat_rev.items():
        bar = "█" * int(rev / cat_rev.max() * 25)
        print(f"  {cat:<15} KES {rev:>10,.0f}  {bar}")
    
    # Top 5 outlets by revenue
    print("\nTop 5 outlets by total revenue:")
    outlet_rev = df.groupby(["outlet_osm_id", "outlet_name", "outlet_type"])[
        "line_total"].sum().sort_values(ascending=False).head(5)
    print(f"\n{'Outlet':<28} {'Type':<14} {'Revenue (KES)':>14}")
    print("-" * 58)
    for (_, name, otype), rev in outlet_rev.items():
        print(f"{name[:27]:<28} {otype:<14} {rev:>14,.0f}")
    
    # Stockout signal. Outlets with gaps > 3 weeks in any category
    print("\nStockout signals (outlets with ordering gaps > 3 weeks):")
    df["invoice_date"] = pd.to_datetime(df["invoice_date"])
    gaps = (df.groupby(["outlet_osm_id", "category"])["invoice_date"]
              .apply(lambda x: x.sort_values().diff().dt.days.max())
              .reset_index(name="max_gap_days"))
    stockout_signals = gaps[gaps["max_gap_days"] > 21].shape[0]
    print(f"  {stockout_signals} outlet-category combinations with gaps > 21 days")
    print(f"  (These are probable stockout events in the synthetic data)")

def save_and_load(df, engine):
    out_path = OUTPUT_DIR / "kisumu_synthetic_invoices.parquet"
    df.to_parquet(out_path, index=False)
    print(f"\nSaved to {out_path} ({out_path.stat().st_size / 1024:.0f} KB)")

    print("Loading into database...")
    df.to_sql("synthetic_invoices", engine, if_exists="replace",
              index=False, chunksize=1000)
    print("Loaded into database table: synthetic_invoices")

def main():
    engine = create_engine(DB_URL)
    df = run_simulation(engine)
    analyse_invoices(df)
    save_and_load(df, engine)

if __name__ == "__main__":
    np.random.seed(42)
    random.seed(42)
    main()