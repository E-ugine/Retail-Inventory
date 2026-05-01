import pandas as pd
import numpy as np
from sqlalchemy import create_engine, text
from pathlib import Path
from dotenv import load_dotenv
import os

load_dotenv()
DB_URL = os.getenv("DATABASE_URL")
OUTPUT_DIR = Path("data/processed")

"""
# Outlet size tiers — weekly base demand in units
# Calibrated against AfDB informal retail studies
"""
SIZE_TIERS = {
    "large":  {"types": ["wholesale", "supermarket"],                          "base_units": 120},
    "medium": {"types": ["chemist", "convenience", "grocery", "general",
                         "agrarian", "alcohol", "bakery", "water", "gas"],     "base_units": 45},
    "small":  {"types": ["kiosk", "butcher", "greengrocer", "dairy", "farm",
                         "unclassified"],                                       "base_units": 18},
}

def get_size_tier(shop_type):
    for tier, config in SIZE_TIERS.items():
        if shop_type in config["types"]:
            return tier
    return "small" 

def get_base_units(tier):
    return SIZE_TIERS[tier]["base_units"]

def build_density_scores(engine):
    """
    Score each outlet by the density of its surrounding area.
    Uses the grid density analysis from Month 1.
    Returns a dict of osm_id -> density_score (0.5 to 1.5)
    """
    print("Building location density scores...")
    
    with engine.connect() as conn:
        result = conn.execute(text("""
            SELECT osm_id, latitude, longitude, shop_type
            FROM outlets_fmcg
            ORDER BY osm_id;
        """))
        outlets = result.fetchall()
    """
    # For each outlet, count how many other outlets are within 500m
    # More neighbours = denser area = higher demand
    """
    # For each outlet, count how many other outlets are within 500m
    # More neighbours = denser area = higher demand
    outlet_df = pd.DataFrame(outlets, columns=["osm_id", "lat", "lon", "shop_type"])
    

    density_scores = {}
    for _, row in outlet_df.iterrows():
        neighbours = outlet_df[
            (abs(outlet_df["lat"] - row["lat"]) < 0.005) &
            (abs(outlet_df["lon"] - row["lon"]) < 0.005)
        ]
        count = len(neighbours) - 1  # exclude self
        density_scores[row["osm_id"]] = count
    
    scores = pd.Series(density_scores)
    min_s, max_s = scores.min(), scores.max()
    normalised = 0.5 + (scores - min_s) / (max_s - min_s + 1e-9)
    
    print(f"  Density scores: min={normalised.min():.2f} max={normalised.max():.2f} mean={normalised.mean():.2f}")
    return normalised.to_dict()

def build_demand_profiles(engine):
    print("\nBuilding demand profiles...")
    
    with engine.connect() as conn:
        outlets = pd.read_sql("SELECT osm_id, name, shop_type FROM outlets_fmcg;", conn)
        products = pd.read_sql("SELECT sku, category, category_weight FROM product_catalog;", conn)
    
    density_scores = build_density_scores(engine)
    
    profiles = []
    
    for _, outlet in outlets.iterrows():
        tier = get_size_tier(outlet["shop_type"])
        base = get_base_units(tier)
        density = density_scores.get(outlet["osm_id"], 1.0)
        
        for _, product in products.iterrows():
            """
            # Weekly demand = base units × category weight × density × random variance
            # Random variance ±20% — real outlets don't all sell exactly the same
            """
            
            variance = np.random.uniform(0.8, 1.2)
            weekly_units = base * product["category_weight"] * density * variance
            weekly_units = max(1, round(weekly_units))  # minimum 1 unit/week
            
            profiles.append({
                "osm_id": outlet["osm_id"],
                "outlet_name": outlet["name"],
                "shop_type": outlet["shop_type"],
                "size_tier": tier,
                "sku": product["sku"],
                "category": product["category"],
                "weekly_units": weekly_units,
                "density_score": round(density, 3)
            })
    
    df = pd.DataFrame(profiles)
    
    out_path = OUTPUT_DIR / "outlet_demand_profiles.csv"
    df.to_csv(out_path, index=False)
    print(f"Saved {len(df)} outlet-SKU demand profiles to {out_path}")
    
    return df

def analyse_profiles(df):
    print("\n=== Demand Profile Summary ===")
    
    # Weekly units by size tier
    tier_summary = df.groupby("size_tier").agg(
        outlets=("osm_id", "nunique"),
        avg_weekly_units=("weekly_units", "mean"),
        total_weekly_units=("weekly_units", "sum")
    ).round(1)
    
    print("\nWeekly demand by outlet size tier:")
    print(f"\n{'Tier':<10} {'Outlets':>8} {'Avg Units/SKU':>14} {'Total Units':>12}")
    print("-" * 48)
    for tier, row in tier_summary.iterrows():
        print(f"{tier:<10} {row['outlets']:>8} {row['avg_weekly_units']:>14.1f} {row['total_weekly_units']:>12.0f}")
    
    cat_summary = df.groupby("category")["weekly_units"].sum().sort_values(ascending=False)
    
    print("\nTotal weekly units by category (all outlets):")
    for cat, units in cat_summary.items():
        bar = "█" * int(units / cat_summary.max() * 30)
        print(f"  {cat:<15} {units:>6.0f}  {bar}")
    
    outlet_volume = df.groupby(["osm_id", "outlet_name", "shop_type", "size_tier"])[
        "weekly_units"].sum().sort_values(ascending=False).head(5)
    
    print("\nTop 5 highest volume outlets:")
    print(f"\n{'Name':<25} {'Type':<15} {'Tier':<8} {'Weekly Units':>12}")
    print("-" * 64)
    for (osm_id, name, stype, tier), units in outlet_volume.items():
        print(f"{name[:24]:<25} {stype:<15} {tier:<8} {units:>12.0f}")

def main():
    engine = create_engine(DB_URL)
    df = build_demand_profiles(engine)
    analyse_profiles(df)
    
    # Load into database
    with engine.connect() as conn:
        df.to_sql("demand_profiles", conn, if_exists="replace", index=False)
        conn.commit()
    print("\nLoaded demand profiles into database table: demand_profiles")

if __name__ == "__main__":
    main()