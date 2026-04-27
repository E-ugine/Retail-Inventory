import requests
import json
import pandas as pd
import geopandas as gpd
from shapely.geometry import Point
from pathlib import Path

OUTPUT_DIR = Path("data/raw")
OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

OVERPASS_URL = "https://overpass.kumi.systems/api/interpreter"


OVERPASS_QUERY = """
[out:json][timeout:60];
(
  node["shop"](-0.1942,34.6784,0.0614,34.8784);
  node["amenity"="marketplace"](-0.1942,34.6784,0.0614,34.8784);
  node["amenity"="market"](-0.1942,34.6784,0.0614,34.8784);
);
out body;
"""

def fetch_osm_outlets():
    print("Querying Overpass API for Kisumu retail outlets...")

    
    response = requests.post(
        OVERPASS_URL,
        data={"data": OVERPASS_QUERY},
        timeout=90
    )
    
    print(f"Status code: {response.status_code}")
    print(f"Response text (first 500 chars): {response.text[:500]}")
    
    if response.status_code != 200:
        raise Exception(f"Overpass API error: {response.status_code}")
    
    data = response.json()
    elements = data.get("elements", [])
    print(f"Raw elements returned: {len(elements)}")
    return elements

def parse_outlets(elements):
    records = []
    
    for el in elements:
        # Only process nodes (points), not ways or relations
        if el.get("type") != "node":
            continue
        
        tags = el.get("tags", {})
        
        record = {
            "osm_id": el["id"],
            "latitude": el["lat"],
            "longitude": el["lon"],
            "name": tags.get("name", None),
            "shop_type": tags.get("shop", None),
            "amenity": tags.get("amenity", None),
            "opening_hours": tags.get("opening_hours", None),
        }
        records.append(record)
    
    return records

def save_outlets(records):
    # Save as CSV
    df = pd.DataFrame(records)
    csv_path = OUTPUT_DIR / "kisumu_osm_outlets.csv"
    df.to_csv(csv_path, index=False)
    print(f"Saved {len(df)} outlets to {csv_path}")
    
    geometry = [Point(r["longitude"], r["latitude"]) for r in records]
    gdf = gpd.GeoDataFrame(pd.DataFrame(records), geometry=geometry, crs="EPSG:4326")
    geojson_path = OUTPUT_DIR / "kisumu_osm_outlets.geojson"
    gdf.to_file(geojson_path, driver="GeoJSON")
    print(f"Saved GeoJSON to {geojson_path}")
    
    return df

def main():
    elements = fetch_osm_outlets()
    records = parse_outlets(elements)
    df = save_outlets(records)
    

if __name__ == "__main__":
    main()