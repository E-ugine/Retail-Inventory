import pandas as pd
import geopandas as gpd
from sqlalchemy import create_engine, text
from pathlib import Path
from dotenv import load_dotenv
import os

load_dotenv()

DB_URL = os.getenv("DATABASE_URL", "postgresql://postgres@localhost:5432/retail_intelligence")
INPUT_FILE = Path("data/raw/kisumu_osm_outlets.csv")

def get_engine():
    engine = create_engine(DB_URL)
    return engine

def create_outlets_table(engine):
    """Create the outlets table with a PostGIS geometry column."""
    with engine.connect() as conn:
        conn.execute(text("""
            DROP TABLE IF EXISTS outlets;
            CREATE TABLE outlets (
                id          SERIAL PRIMARY KEY,
                osm_id      BIGINT UNIQUE,
                name        TEXT,
                shop_type   TEXT,
                amenity     TEXT,
                latitude    DOUBLE PRECISION,
                longitude   DOUBLE PRECISION,
                geom        GEOMETRY(Point, 4326)
            );
        """))
        conn.commit()
    print("Table created: outlets")

def load_outlets(engine):
    """Load CSV data into the outlets table."""
    df = pd.read_csv(INPUT_FILE)
    
    # Clean up. Fill missing values
    df["name"] = df["name"].fillna("Unknown")
    df["shop_type"] = df["shop_type"].fillna("unclassified")
    df["amenity"] = df["amenity"].fillna("none")
    
    print(f"Loading {len(df)} outlets into database...")
    
    with engine.connect() as conn:
        for _, row in df.iterrows():
            conn.execute(text("""
                INSERT INTO outlets 
                    (osm_id, name, shop_type, amenity, latitude, longitude, geom)
                VALUES 
                    (:osm_id, :name, :shop_type, :amenity, :lat, :lon,
                     ST_SetSRID(ST_MakePoint(:lon, :lat), 4326))
                ON CONFLICT (osm_id) DO NOTHING;
            """), {
                "osm_id": int(row["osm_id"]),
                "name": row["name"],
                "shop_type": row["shop_type"],
                "amenity": row["amenity"],
                "lat": float(row["latitude"]),
                "lon": float(row["longitude"])
            })
        conn.commit()
    
    print("Load complete.")

def verify_load(engine):
    with engine.connect() as conn:
        
        # Total count
        result = conn.execute(text("SELECT COUNT(*) FROM outlets;"))
        count = result.scalar()
        print(f"\n--- Verification ---")
        print(f"Total outlets in DB: {count}")
        
        # Shop type breakdown
        result = conn.execute(text("""
            SELECT shop_type, COUNT(*) as count
            FROM outlets
            GROUP BY shop_type
            ORDER BY count DESC
            LIMIT 8;
        """))
        print(f"\nTop shop types:")
        for row in result:
            print(f"  {row[0]}: {row[1]}")
        
        result = conn.execute(text("""
            SELECT name, shop_type,
                   ST_X(geom) as lon,
                   ST_Y(geom) as lat
            FROM outlets
            LIMIT 3;
        """))
        print(f"\nSample spatial query:")
        for row in result:
            print(f"  {row[0]} ({row[1]}) — lat:{row[3]:.4f} lon:{row[2]:.4f}")

def main():
    engine = get_engine()
    create_outlets_table(engine)
    load_outlets(engine)
    verify_load(engine)

if __name__ == "__main__":
    main()