import requests
import pandas as pd
import time
from sqlalchemy import create_engine, text
from dotenv import load_dotenv
import os
from pathlib import Path

load_dotenv()
DB_URL = os.getenv("DATABASE_URL")
OUTPUT_DIR = Path("data/processed")

HEADERS = {"User-Agent": "kisumu-retail-intelligence/1.0 (research project)"}
NOMINATIM_URL = "https://nominatim.openstreetmap.org/reverse"

def reverse_geocode(lat, lon):
    """Get street/area name for a coordinate."""
    try:
        response = requests.get(
            NOMINATIM_URL,
            params={
                "lat": lat,
                "lon": lon,
                "format": "json",
                "zoom": 16,  # street level
                "addressdetails": 1
            },
            headers=HEADERS,
            timeout=10
        )
        if response.status_code == 200:
            data = response.json()
            address = data.get("address", {})
            return {
                "road": address.get("road") or address.get("pedestrian") or address.get("path"),
                "suburb": address.get("suburb") or address.get("neighbourhood") or address.get("quarter"),
                "display_name": data.get("display_name", "")[:80]
            }
    except Exception as e:
        print(f"  Geocode error: {e}")
    return {"road": None, "suburb": None, "display_name": None}

def geocode_fmcg_outlets(engine):
    with engine.connect() as conn:
        result = conn.execute(text("""
            SELECT id, osm_id, name, shop_type, latitude, longitude
            FROM outlets_fmcg
            ORDER BY id;
        """))
        rows = result.fetchall()
    
    print(f"Reverse geocoding {len(rows)} FMCG outlets...")
    print("This will take a few minutes (Nominatim rate limit: 1 request/second)\n")
    
    records = []
    for i, row in enumerate(rows):
        geo = reverse_geocode(row[4], row[5])
        records.append({
            "id": row[0],
            "osm_id": row[1],
            "name": row[2],
            "shop_type": row[3],
            "latitude": row[4],
            "longitude": row[5],
            "road": geo["road"],
            "suburb": geo["suburb"],
            "display_name": geo["display_name"]
        })
        
        # Progress update every 20 outlets
        if (i + 1) % 20 == 0:
            print(f"  Processed {i + 1}/{len(rows)}...")
        
        time.sleep(1)
    
    df = pd.DataFrame(records)
    
    out_path = OUTPUT_DIR / "kisumu_fmcg_outlets_geocoded.csv"
    df.to_csv(out_path, index=False)
    print(f"\nSaved to {out_path}")
    
    return df

def analyse_corridors(df):
    print("\n=== FMCG Corridor Analysis ===")
    
    # By road
    road_counts = (
        df[df["road"].notna()]
        .groupby("road")
        .agg(
            outlet_count=("id", "count"),
            shop_types=("shop_type", lambda x: ", ".join(sorted(set(x))))
        )
        .sort_values("outlet_count", ascending=False)
        .head(15)
    )
    
    print("\nTop 15 roads by FMCG outlet count:")
    print(f"\n{'Road':<40} {'Outlets':>7}  Shop Types")
    print("-" * 80)
    for road, row in road_counts.iterrows():
        print(f"{road:<40} {row['outlet_count']:>7}  {row['shop_types'][:35]}")
    
    # By suburb
    suburb_counts = (
        df[df["suburb"].notna()]
        .groupby("suburb")
        .agg(
            outlet_count=("id", "count"),
            shop_types=("shop_type", lambda x: ", ".join(sorted(set(x))))
        )
        .sort_values("outlet_count", ascending=False)
        .head(10)
    )
    
    print("\nTop 10 suburbs/neighbourhoods by FMCG outlet count:")
    print(f"\n{'Suburb':<30} {'Outlets':>7}  Shop Types")
    print("-" * 70)
    for suburb, row in suburb_counts.iterrows():
        print(f"{suburb:<30} {row['outlet_count']:>7}  {row['shop_types'][:35]}")

def main():
    engine = create_engine(DB_URL)
    df = geocode_fmcg_outlets(engine)
    analyse_corridors(df)

if __name__ == "__main__":
    main()