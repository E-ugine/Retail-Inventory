from sqlalchemy import create_engine, text
from dotenv import load_dotenv
import os

load_dotenv()
DB_URL = os.getenv("DATABASE_URL")

def update_fmcg_table(engine):
    with engine.connect() as conn:
        conn.execute(text("""
            DROP TABLE IF EXISTS outlets_fmcg;
            CREATE TABLE outlets_fmcg AS
            SELECT * FROM outlets
            WHERE shop_type IN (
                'convenience', 'supermarket', 'kiosk',
                'wholesale', 'general', 'grocery',
                'chemist', 'butcher', 'greengrocer',
                'dairy', 'alcohol', 'bakery', 'water',
                'agrarian', 'farm', 'gas'
            )
            OR amenity IN ('marketplace', 'market');
        """))
        
        result = conn.execute(text("SELECT COUNT(*) FROM outlets_fmcg;"))
        count = result.scalar()
        conn.commit()
        print(f"FMCG table updated: {count} outlets")
        
        result = conn.execute(text("""
            SELECT shop_type, COUNT(*) as count
            FROM outlets_fmcg
            GROUP BY shop_type
            ORDER BY count DESC;
        """))
        print("\nBreakdown:")
        for row in result:
            print(f"  {row[0]:<20} {row[1]}")

if __name__ == "__main__":
    engine = create_engine(DB_URL)
    update_fmcg_table(engine)