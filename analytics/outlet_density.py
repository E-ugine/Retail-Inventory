import geopandas as gpd
import pandas as pd
from sqlalchemy import create_engine, text
from pathlib import Path
from dotenv import load_dotenv
import os

load_dotenv()

DB_URL = os.getenv("DATABASE_URL")
OUTPUT_DIR = Path("data/processed")
OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

def get_engine():
    return create_engine(DB_URL)


"""
ANALYSIS 1: Grid-based density. So here, what we're doing is dividing the city into a regular grid then counting points per cell.
Divide Kisumu into a 500m x 500m grid, count outlets per cell.
"""

def grid_density_analysis(engine):
    print("\n=== Grid Density Analysis ===")
    
    # Load outlets from DB into a GeoDataFrame
    query = "SELECT osm_id, name, shop_type, amenity, latitude, longitude, geom FROM outlets;"
    gdf = gpd.read_postgis(query, engine, geom_col="geom", crs="EPSG:4326")
    print(f"Loaded {len(gdf)} outlets from database")
    
    """
    Reproject to a metre-based CRS for accurate distance calculations.
    EPSG:32636 is UTM Zone 36N. Covers Kenya
    """     
    gdf_metres = gdf.to_crs("EPSG:32636")
    
    # Create a 500m grid over the bounding box of all outlets
    from shapely.geometry import box
    import numpy as np
    
    bounds = gdf_metres.total_bounds  # (minx, miny, maxx, maxy)
    cell_size = 500  # This is in metres(500m)
    
    cols = int((bounds[2] - bounds[0]) / cell_size) + 1
    rows = int((bounds[3] - bounds[1]) / cell_size) + 1
    
    print(f"Creating {cols}x{rows} grid ({cell_size}m cells)...")
    
    grid_cells = []
    for i in range(cols):
        for j in range(rows):
            minx = bounds[0] + i * cell_size
            miny = bounds[1] + j * cell_size
            maxx = minx + cell_size
            maxy = miny + cell_size
            grid_cells.append({
                "grid_id": f"{i}_{j}",
                "col": i,
                "row": j,
                "geometry": box(minx, miny, maxx, maxy)
            })
    
    grid = gpd.GeoDataFrame(grid_cells, crs="EPSG:32636")
    
    # Spatial join — which outlets fall inside which grid cell?
    joined = gpd.sjoin(gdf_metres, grid, how="left", predicate="within")
    
    density = joined.groupby("grid_id").size().reset_index(name="outlet_count")
    grid_with_density = grid.merge(density, on="grid_id", how="left")
    grid_with_density["outlet_count"] = grid_with_density["outlet_count"].fillna(0).astype(int)
    

    active_cells = grid_with_density[grid_with_density["outlet_count"] > 0].copy()
    
    print(f"\nGrid cells with outlets: {len(active_cells)} of {len(grid)} total cells")
    print(f"Max outlets in a single 500m cell: {active_cells['outlet_count'].max()}")
    print(f"Average outlets per active cell: {active_cells['outlet_count'].mean():.1f}")
    

    print(f"\nTop 10 densest grid cells:")
    top = active_cells.nlargest(10, "outlet_count")[["grid_id", "col", "row", "outlet_count"]]
    print(top.to_string(index=False))
    
    # Save to GeoJSON for visualisation 
    active_cells_wgs84 = active_cells.to_crs("EPSG:4326")
    out_path = OUTPUT_DIR / "kisumu_outlet_density_grid.geojson"
    active_cells_wgs84.to_file(out_path, driver="GeoJSON")
    print(f"\nSaved grid density to {out_path}")
    
    return active_cells


"""
 ANALYSIS 2: Shop type distribution by zone
 What kinds of outlets cluster together?
"""

def shop_type_distribution(engine):
    print("\n=== Shop Type Distribution ===")
    
    with engine.connect() as conn:
        result = conn.execute(text("""
            SELECT 
                shop_type,
                COUNT(*) as count,
                ROUND(COUNT(*) * 100.0 / SUM(COUNT(*)) OVER (), 1) as pct,
                ROUND(AVG(latitude)::numeric, 4) as avg_lat,
                ROUND(AVG(longitude)::numeric, 4) as avg_lon
            FROM outlets
            GROUP BY shop_type
            ORDER BY count DESC;
        """))
        
        rows = result.fetchall()
        
        print(f"\n{'Shop Type':<20} {'Count':>6} {'%':>6} {'Avg Lat':>10} {'Avg Lon':>10}")
        print("-" * 56)
        for row in rows:
            print(f"{row[0]:<20} {row[1]:>6} {row[2]:>6} {row[3]:>10} {row[4]:>10}")

"""
# ANALYSIS 3: FMCG-relevant outlet filter
# Isolate the outlets actually relevant to FMCG distribution
"""
def fmcg_relevant_outlets(engine):
    print("\n=== FMCG-Relevant Outlets ===")
    
    fmcg_types = (
        'convenience', 'supermarket', 'kiosk', 
        'wholesale', 'general', 'grocery',
        'chemist', 'butcher'
    )
    
    with engine.connect() as conn:
        result = conn.execute(text("""
            SELECT 
                shop_type,
                COUNT(*) as count
            FROM outlets
            WHERE shop_type IN :types
               OR amenity IN ('marketplace', 'market')
            GROUP BY shop_type
            ORDER BY count DESC;
        """), {"types": fmcg_types})
        
        rows = result.fetchall()
        total = sum(r[1] for r in rows)
        
        print(f"\nFMCG-relevant outlet types:")
        for row in rows:
            print(f"  {row[0]:<20} {row[1]}")
        print(f"  {'TOTAL':<20} {total}")
        
        conn.execute(text("""
            DROP TABLE IF EXISTS outlets_fmcg;
            CREATE TABLE outlets_fmcg AS
            SELECT * FROM outlets
            WHERE shop_type IN :types
               OR amenity IN ('marketplace', 'market');
        """), {"types": fmcg_types})
        conn.commit()
        print(f"\nSaved FMCG subset to table: outlets_fmcg")

def main():
    engine = get_engine()
    grid_density_analysis(engine)
    shop_type_distribution(engine)
    fmcg_relevant_outlets(engine)

if __name__ == "__main__":
    main()