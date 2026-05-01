# Retail Intelligence

A data pipeline and analytics demo that currently(aiming to expand to other towns) generates outlet-level FMCG demand intelligence for informal retail markets in Kisumu, Kenya. Built on publicly available data with a synthetic transaction layer.

---

## What this is

FMCG brand owners in Kenya can see distributor sell-in numbers, what left the warehouse, but not sell-out numbers, what left the duka shelf. This project infers that gap using spatial data, demographic consumption weights, and a simulated transaction layer, then surfaces the results in an interactive dashboard.

The output is three intelligence modules:

- **Sales velocity** — which product categories move fastest in which neighbourhoods
- **Stockout probability** — which outlets are likely out of stock right now based on last delivery and depletion rate
- **Coverage gaps** — which outlets are being underserved by distributor visit frequency

The demo runs on synthetic data modelled on real Kisumu retail geography. The pipeline is designed so that real distributor invoice data can replace the synthetic layer without changing anything downstream.

---

## What this is not

This is not a production system. There is no authentication, no multi-tenancy, no real-time ingestion. It is a functional demo built to validate a market hypothesis and open conversations with potential data partners.

---

## Stack

| Layer | Technology |
|---|---|
| Spatial database | PostgreSQL 17 + PostGIS |
| Data processing | Python 3.12, Pandas, GeoPandas |
| Simulation | Custom discrete event simulator |
| Dashboard | Streamlit, Plotly, Folium |
| Hosted database | Supabase |
| Deployment | Streamlit Cloud |

---

## Prerequisites

- Python 3.10+
- PostgreSQL 17 with PostGIS extension
- Git

If you are on Mac with Homebrew:

```bash
brew install postgresql@17 postgis
brew services start postgresql@17
```

---

## Local setup

**1. Clone the repository** (My bad on the clash of names. Should have been intelligence not inventory)

```bash
git clone https://github.com/E-ugine/Retail-Inventory.git
cd Retail-Inventory
```

**2. Create and activate a virtual environment**

```bash
python3 -m venv venv
source venv/bin/activate
```

**3. Install dependencies**

```bash
pip install -r requirements.txt
```

**4. Create the database**

```bash
psql postgres -c "CREATE DATABASE retail_intelligence;"
psql retail_intelligence -c "CREATE EXTENSION postgis;"
```

**5. Set up environment variables**

Create a `.env` file in the project root:

```
DATABASE_URL=postgresql://username@localhost:5432/retail_intelligence
```

**6. Run the pipeline end to end**

Run each script in order. Each one DEPENDS on the output of the PREVIOUS. 

```bash
# Step 1 — Extract outlet locations from OpenStreetMap
python pipelines/extract_osm_outlets.py

# Step 2 — Load outlets into PostGIS
python pipelines/load_outlets_to_db.py

# Step 3 — Filter and tag FMCG-relevant outlets
python pipelines/update_fmcg_filter.py

# Step 4 — Reverse geocode outlets to get suburb and road names
python pipelines/reverse_geocode_outlets.py

# Step 5 — Build the product catalog
python pipelines/build_product_catalog.py

# Step 6 — Build outlet demand profiles
python pipelines/build_demand_profiles.py

# Step 7 — Run the invoice simulator
python pipelines/simulate_invoices.py

# Step 8 — Run the intelligence layer
python analytics/demand_atlas.py
```

Step 4 takes 4–5 minutes due to Nominatim rate limiting (1 request/second). All other steps should be quick run.

**7. Run the dashboard**

```bash
cd demo
streamlit run app.py
```

The app opens at `http://localhost:8501`.

---

## Pipeline flow

```
OpenStreetMap (Overpass API)
        │
        ▼
extract_osm_outlets.py
  → data/raw/kisumu_osm_outlets.csv
  → data/raw/kisumu_osm_outlets.geojson
        │
        ▼
load_outlets_to_db.py
  → PostgreSQL: outlets table (864 rows, PostGIS geometry)
        │
        ▼
update_fmcg_filter.py
  → PostgreSQL: outlets_fmcg table (256 rows)
        │
        ▼
reverse_geocode_outlets.py (Nominatim API)
  → data/processed/kisumu_fmcg_outlets_geocoded.csv
  → Updates outlets_fmcg with suburb and road columns
        │
        ▼
build_product_catalog.py
  → data/processed/fmcg_product_catalog.csv
  → PostgreSQL: product_catalog table (24 SKUs)
        │
        ▼
build_demand_profiles.py
  → data/processed/outlet_demand_profiles.csv
  → PostgreSQL: demand_profiles table (6,144 outlet-SKU pairs)
        │
        ▼
simulate_invoices.py
  → data/synthetic/kisumu_synthetic_invoices.parquet
  → PostgreSQL: synthetic_invoices table (50,605 rows)
        │
        ▼
demand_atlas.py
  → PostgreSQL: intel_sales_velocity
  → PostgreSQL: intel_stockout_probability
  → PostgreSQL: intel_coverage_gaps
        │
        ▼
demo/app.py (Streamlit)
  → Four-page interactive dashboard
```

---

## Folder structure

```
kisumu-retail-intelligence/
│
├── pipelines/                  # Ingestion and transformation scripts
│   ├── extract_osm_outlets.py  # Pulls retail nodes from Overpass API
│   ├── load_outlets_to_db.py   # Loads CSV into PostGIS
│   ├── update_fmcg_filter.py   # Filters outlets relevant to FMCG
│   ├── reverse_geocode_outlets.py  # Nominatim reverse geocoding
│   ├── build_product_catalog.py    # Builds SKU catalog with prices
│   ├── build_demand_profiles.py    # Assigns weekly demand per outlet-SKU
│   └── simulate_invoices.py        # Discrete event invoice simulator
│
├── analytics/
│   └── demand_atlas.py         # Three intelligence modules
│
├── demo/
│   ├── app.py                  # Streamlit dashboard
│   ├── requirements.txt        # Deployment dependencies
│   └── .streamlit/
│       └── secrets.toml        # Database URL (not committed)
│
├── data/
│   ├── raw/                    # Source data, never modified
│   ├── processed/              # Cleaned and enriched outputs
│   └── synthetic/              # Simulated invoice data (parquet)
│
├── docs/
│   └── CONTEXT.md              # Product and architecture context
│
├── requirements.txt            # Full dependency list
├── .env                        # Local environment variables (not committed)
├── .gitignore
├── README.md
└── CONTRIBUTING.md
```

---

## Database tables

| Table | Description | Rows |
|---|---|---|
| `outlets` | All OSM retail nodes with PostGIS geometry | 864 |
| `outlets_fmcg` | Filtered FMCG-relevant outlets with suburb/road | 256 |
| `product_catalog` | 24 SKUs across 7 categories, 14 Kenyan brands | 24 |
| `demand_profiles` | Weekly unit demand per outlet-SKU pair | 6,144 |
| `synthetic_invoices` | 26 weeks of simulated distributor invoices | 50,605 |
| `intel_sales_velocity` | 4-week rolling velocity by suburb and category | — |
| `intel_stockout_probability` | Implied stock level and stockout risk per outlet-SKU | — |
| `intel_coverage_gaps` | Visit frequency and service level per outlet | — |

---

## Data sources

| Source | What it provides | Access |
|---|---|---|
| OpenStreetMap / Overpass API | Retail outlet locations in Kisumu | Free, no key required |
| Nominatim | Reverse geocoding — suburb and road names | Free, 1 req/sec rate limit |
| KNBS KIHBS | Household consumption weights by category | Public download |
| Brand websites / Jumia Kenya | SKU names and wholesale price estimates | Public |
| WorldPop | Population density raster (used in demand profiling) | Free download |

---

## Key design decisions

**Why synthetic data?**
Real distributor invoice data requires trust relationships that take months to build. The synthetic layer lets the pipeline and dashboard be built and demonstrated before those relationships exist. When real data becomes available, it replaces the `simulate_invoices.py` output — nothing else changes.

**Why Kisumu over Nairobi?**
Nairobi's informal retail is split across 30+ distinct micro-markets with different supply chain dynamics. Kisumu has a more legible structure — a dominant wholesale corridor, clear catchment neighbourhoods, and distributors small enough to engage directly. It is the right city to prove the concept before expanding.

**Why PostGIS over a flat file approach?**
The core intelligence modules — stockout proximity, coverage gap detection, outlet density — all require spatial joins. Doing these in PostGIS is faster, more correct, and more maintainable than approximating them in Pandas with lat/lon arithmetic.

**Why outlet type determines demand tier?**
Wholesale shops and supermarkets move 5–7x the volume of kiosks in informal retail markets. This is documented in AfDB and IFC informal retail studies. The tiering (large/medium/small) is a simplified but defensible proxy for volume.

---

## Known limitations

- OSM coverage in Kisumu is partial — estimated 30–50% of actual informal retail outlets are tagged. The synthetic outlet augmentation layer addresses this partially but does not eliminate the gap.
- Reverse geocoding returns `None` for ~15% of outlets in areas with poor OSM street tagging. These outlets appear as `NaN` suburb in the intelligence outputs.
- The invoice simulator assigns outlets to distributors by geographic proximity only. Real distributor-outlet relationships are determined by brand portfolio, credit terms, and history — factors this model does not capture.
- Stockout probability is a directional estimate, not a precise measurement. It is accurate enough to prioritise field visits but should not be treated as ground truth.

---

## Running against real data

If you have access to real distributor invoice data, the integration point is `simulate_invoices.py`. Replace the simulation output with a script that:

1. Reads real invoice records from whatever format the distributor uses (CSV export from QuickBooks, Sage, or Excel)
2. Normalises to the `synthetic_invoices` schema (see table above)
3. Loads into the `synthetic_invoices` table

The analytics and dashboard layers require no changes. The schema is:

```
invoice_date, distributor_id, outlet_osm_id, outlet_name,
outlet_type, outlet_lat, outlet_lon, suburb, sku,
product_name, brand, category, quantity, unit_price,
line_total, size_tier, week_number
```

---

## Deployment

The demo is deployed on Streamlit Cloud connected to a Supabase PostgreSQL instance.

To deploy your own instance:

1. Export the local database: `pg_dump retail_intelligence > backup.sql`
2. Create a Supabase project and import: `psql YOUR_SUPABASE_URL < backup.sql` If you're on Mac, you might face DNS failures while using the direct connection string. I used the session pooler string instead to complete the connection.
3. Push the repository to GitHub
4. Connect the repo to share.streamlit.io
5. Set `DATABASE_URL` in Streamlit Cloud secrets
6. Set main file path to `demo/app.py`