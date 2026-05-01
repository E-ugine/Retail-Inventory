import pandas as pd
from pathlib import Path

OUTPUT_DIR = Path("data/processed")
OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

"""
# FMCG Product Catalog for Kenya informal retail
# Sources: brand websites, Jumia Kenya, trade press
# Prices in KES at wholesale (approx 20% below retail)
"""

PRODUCTS = [
    # COOKING OIL
    {"sku": "OIL001", "brand": "Bidco", "name": "Golden Fry Cooking Oil",
     "size": "500ml", "category": "cooking_oil", "wholesale_price": 135,
     "retail_price": 165, "weight_g": 460},
    
    {"sku": "OIL002", "brand": "Bidco", "name": "Golden Fry Cooking Oil",
     "size": "1L", "category": "cooking_oil", "wholesale_price": 265,
     "retail_price": 320, "weight_g": 920},
    
    {"sku": "OIL003", "brand": "Kapa", "name": "Soya King Cooking Oil",
     "size": "500ml", "category": "cooking_oil", "wholesale_price": 128,
     "retail_price": 158, "weight_g": 460},
    
    {"sku": "OIL004", "brand": "Kapa", "name": "Soya King Cooking Oil",
     "size": "1L", "category": "cooking_oil", "wholesale_price": 252,
     "retail_price": 310, "weight_g": 920},

    # FLOUR
    {"sku": "FLR001", "brand": "Unga", "name": "Jogoo Maize Flour",
     "size": "1kg", "category": "flour", "wholesale_price": 145,
     "retail_price": 175, "weight_g": 1000},
    
    {"sku": "FLR002", "brand": "Unga", "name": "Jogoo Maize Flour",
     "size": "2kg", "category": "flour", "wholesale_price": 285,
     "retail_price": 345, "weight_g": 2000},
    
    {"sku": "FLR003", "brand": "Unga", "name": "Pembe Maize Flour",
     "size": "1kg", "category": "flour", "wholesale_price": 140,
     "retail_price": 170, "weight_g": 1000},
    
    {"sku": "FLR004", "brand": "Kabras", "name": "Kabras Maize Flour",
     "size": "2kg", "category": "flour", "wholesale_price": 275,
     "retail_price": 335, "weight_g": 2000},

    # SUGAR
    {"sku": "SUG001", "brand": "Mumias", "name": "Mumias Sugar",
     "size": "1kg", "category": "sugar", "wholesale_price": 168,
     "retail_price": 200, "weight_g": 1000},
    
    {"sku": "SUG002", "brand": "Mumias", "name": "Mumias Sugar",
     "size": "2kg", "category": "sugar", "wholesale_price": 330,
     "retail_price": 395, "weight_g": 2000},
    
    {"sku": "SUG003", "brand": "Nzoia", "name": "Nzoia Sugar",
     "size": "1kg", "category": "sugar", "wholesale_price": 162,
     "retail_price": 195, "weight_g": 1000},

    # SOAP 
    {"sku": "SOP001", "brand": "Unilever", "name": "Omo Detergent",
     "size": "500g", "category": "soap", "wholesale_price": 145,
     "retail_price": 175, "weight_g": 500},
    
    {"sku": "SOP002", "brand": "Unilever", "name": "Sunlight Bar Soap",
     "size": "175g", "category": "soap", "wholesale_price": 42,
     "retail_price": 55, "weight_g": 175},
    
    {"sku": "SOP003", "brand": "Bidco", "name": "Bidco Bar Soap",
     "size": "800g", "category": "soap", "wholesale_price": 115,
     "retail_price": 140, "weight_g": 800},
    
    {"sku": "SOP004", "brand": "Reckitt", "name": "Dettol Bar Soap",
     "size": "100g", "category": "soap", "wholesale_price": 58,
     "retail_price": 75, "weight_g": 100},

    # BEVERAGES
    {"sku": "BEV001", "brand": "Kevian", "name": "Afia Juice",
     "size": "500ml", "category": "beverages", "wholesale_price": 48,
     "retail_price": 60, "weight_g": 500},
    
    {"sku": "BEV002", "brand": "Kevian", "name": "Pick n Peel Juice",
     "size": "300ml", "category": "beverages", "wholesale_price": 32,
     "retail_price": 40, "weight_g": 300},
    
    {"sku": "BEV003", "brand": "EABL", "name": "Tusker Lager",
     "size": "500ml", "category": "beverages", "wholesale_price": 175,
     "retail_price": 210, "weight_g": 500},
    
    {"sku": "BEV004", "brand": "Coca-Cola", "name": "Coca-Cola Soda",
     "size": "500ml", "category": "beverages", "wholesale_price": 58,
     "retail_price": 70, "weight_g": 500},

    # PERSONAL CARE 
    {"sku": "PC001", "brand": "Unilever", "name": "Vaseline Body Lotion",
     "size": "200ml", "category": "personal_care", "wholesale_price": 175,
     "retail_price": 215, "weight_g": 200},
    
    {"sku": "PC002", "brand": "Unilever", "name": "Dove Bar Soap",
     "size": "100g", "category": "personal_care", "wholesale_price": 98,
     "retail_price": 120, "weight_g": 100},
    
    {"sku": "PC003", "brand": "Colgate", "name": "Colgate Toothpaste",
     "size": "100ml", "category": "personal_care", "wholesale_price": 118,
     "retail_price": 145, "weight_g": 100},

    # SANITARY 
    {"sku": "SAN001", "brand": "P&G", "name": "Always Pads",
     "size": "8 pack", "category": "sanitary", "wholesale_price": 88,
     "retail_price": 110, "weight_g": 80},
    
    {"sku": "SAN002", "brand": "Kimberly-Clark", "name": "Huggies Diapers",
     "size": "10 pack", "category": "sanitary", "wholesale_price": 285,
     "retail_price": 350, "weight_g": 400},
]

"""
# KNBS-derived category demand weights
# Based on KIHBS household expenditure proportions
# for Kisumu County
"""
CATEGORY_WEIGHTS = {
    "flour":        0.22,   # Staple — highest demand
    "cooking_oil":  0.18,   # Staple
    "sugar":        0.16,   # Staple
    "soap":         0.12,   # Household essential
    "beverages":    0.14,   # Mid demand
    "personal_care":0.10,   # Lower demand in informal retail
    "sanitary":     0.08,   # Lower but consistent
}

def build_catalog():
    df = pd.DataFrame(PRODUCTS)
    
    # Add category demand weight to each SKU
    df["category_weight"] = df["category"].map(CATEGORY_WEIGHTS)
    
    # Add margin column
    df["margin_pct"] = ((df["retail_price"] - df["wholesale_price"]) 
                        / df["retail_price"] * 100).round(1)
    
    out_path = OUTPUT_DIR / "fmcg_product_catalog.csv"
    df.to_csv(out_path, index=False)
    print(f"Saved {len(df)} SKUs to {out_path}")
    
    # Summary
    print("\n=== Catalog Summary ===")
    print(f"\nTotal SKUs: {len(df)}")
    
    cat_summary = df.groupby("category").agg(
        sku_count=("sku", "count"),
        avg_wholesale=("wholesale_price", "mean"),
        avg_margin=("margin_pct", "mean"),
        demand_weight=("category_weight", "first")
    ).sort_values("demand_weight", ascending=False)
    
    print(f"\n{'Category':<15} {'SKUs':>5} {'Avg Price':>10} {'Margin%':>8} {'Demand Wt':>10}")
    print("-" * 52)
    for cat, row in cat_summary.iterrows():
        print(f"{cat:<15} {row['sku_count']:>5} "
              f"{row['avg_wholesale']:>10.0f} "
              f"{row['avg_margin']:>8.1f} "
              f"{row['demand_weight']:>10.2f}")
    
    print(f"\nBrands represented: {', '.join(sorted(df['brand'].unique()))}")
    
    return df

if __name__ == "__main__":
    df = build_catalog()