# Contributing

This document is for anyone who want to extend, fix, or adapt this project. Read the README first — this document assumes you have the project running locally.

---

## What contributions are useful

The project is in early demo stage. The most valuable contributions are:

- **Real data integration** — replacing the synthetic invoice layer with a real distributor data connector
- **Additional cities** — extending the pipeline to Mombasa, Nakuru, or Eldoret
- **Data quality improvements** — better handling of OSM coverage gaps, improved reverse geocoding fallbacks
- **Pipeline robustness** — error handling, retries, logging
- **Dashboard improvements** — additional filters, export functionality, mobile layout fixes

If you are thinking of adding a feature that changes the product direction significantly, open an issue first before writing code.

---

## How to set up a development environment

Follow the README setup instructions exactly. Once the pipeline has run end to end and the dashboard loads locally, your environment is correct.

Verify with:

```bash
psql retail_intelligence -c "SELECT COUNT(*) FROM synthetic_invoices;"
# Should return 50605

cd demo && streamlit run app.py
# Dashboard should load at localhost:8501
```

---

## Project conventions

**One script, one job.**
Each pipeline script does exactly one thing. `extract_osm_outlets.py` extracts. `load_outlets_to_db.py` loads. Do not combine steps into a single script even if it feels redundant. The pipeline is designed to be re-run partially, if the geocoding step fails halfway through, you should be able to restart it without re-running the OSM extraction.

**Raw data is never modified.**
Anything in `data/raw/` is source data exactly as downloaded. If you need to clean or transform it, write the output to `data/processed/`. This makes it possible to re-run the entire pipeline from scratch without re-downloading source data.

**Synthetic data is clearly labelled.**
If you add new synthetic data generation, label it as synthetic in both the code and any output that surfaces in the dashboard. The demo disclaimer in the sidebar exists for a reason, do not remove it.

**Database schema changes require a migration comment.**
If you alter a table, add a comment at the top of the script explaining what changed and why. There is no formal migration system, this project is not at that scale, but undocumented schema changes break other scripts silently.

**No hardcoded credentials.**
All database URLs, API keys, and passwords go in `.env` for local development and Streamlit secrets for deployment. The `.gitignore` excludes both. If you accidentally commit a credential, rotate it immediately.

---

## Adding a new city

The pipeline is parameterised by bounding box coordinates. To add Mombasa:

**1. Update the Overpass query in `extract_osm_outlets.py`**

Replace the Kisumu bounding box with Mombasa coordinates:

```python
# Mombasa bounding box
OVERPASS_QUERY = """
[out:json][timeout:60];
(
  node["shop"](-4.1200,39.5800,-3.9800,39.7500);
  node["amenity"="marketplace"](-4.1200,39.5800,-3.9800,39.7500);
  node["amenity"="market"](-4.1200,39.5800,-3.9800,39.7500);
);
out body;
"""
```

**2. Update the output filenames** throughout the pipeline to avoid overwriting Kisumu data:

```python
OUTPUT_FILE = "data/raw/mombasa_osm_outlets.csv"
```

**3. Update the distributor locations** in `simulate_invoices.py` to reflect Mombasa's geography.

**4. Update the map centre** in `demo/app.py`:

```python
# Mombasa centre
folium.Map(location=[-4.043, 39.668], zoom_start=13)
```

A cleaner long-term approach is to make city a config parameter passed at runtime. That refactor is worthwhile once a second city is validated.

---

## Adding real distributor data

This is the highest-value contribution possible. The integration point is `simulate_invoices.py`. Real data replaces the simulation output, nothing downstream changes.

**Expected schema for the `synthetic_invoices` table:**

```sql
invoice_date    DATE
distributor_id  TEXT        -- your internal distributor identifier
outlet_osm_id   BIGINT      -- match to outlets_fmcg.osm_id if possible, else NULL
outlet_name     TEXT
outlet_type     TEXT        -- kiosk, chemist, wholesale, etc.
outlet_lat      FLOAT
outlet_lon      FLOAT
suburb          TEXT
sku             TEXT        -- match to product_catalog.sku if possible
product_name    TEXT
brand           TEXT
category        TEXT
quantity        INTEGER
unit_price      FLOAT
line_total      FLOAT
size_tier       TEXT        -- small / medium / large
week_number     INTEGER     -- week 1-26 relative to your data start date
```

**Practical notes on real data integration:**

Distributor invoice exports are almost always messy. Common issues you will encounter:

- Outlet names are inconsistent across exports (`"Boom Mart"`, `"BoomMart"`, `"BOOM MART LTD"` are the same outlet). You will need a normalisation step.
- Outlet locations are missing. You will need to geocode outlet names against OSM data or use Nominatim with the outlet name as a search query.
- SKU naming does not match the product catalog. Build a mapping table that translates distributor SKU codes to the catalog SKUs.
- Dates are in inconsistent formats. Normalise to `YYYY-MM-DD` before loading.

Write a separate ingestion script for each distributor data source, do not try to build a generic parser. Distributor data is idiosyncratic enough that a generic parser will be wrong in subtle ways.

---

## Improving OSM coverage

The current outlet universe is ~30–50% of actual informal retail in Kisumu. Three ways to improve it:

**1. Add more OSM tags to the Overpass query.**
The current query misses outlets tagged as `building=yes` with no shop tag, outlets tagged as `landuse=commercial`, and outlets with misspelled tags. Audit the raw OSM data in JOSM (the OSM desktop editor) to identify common tagging patterns in Kisumu that the current query misses.

**2. Contribute to OpenStreetMap.**
If you have field knowledge of Kisumu, adding outlets directly to OSM improves both this project and the global dataset. Use the OSM iD editor or StreetComplete mobile app.

**3. Implement the WorldPop synthetic outlet augmentation.**
The architecture document describes inferring outlet locations in high-population areas with low OSM tagging density using WorldPop population rasters. This was scoped for v2 but the groundwork is in `docs/CONTEXT.md`. The WorldPop dataset is freely available at worldpop.org.

---

## Running the tests

There are no automated tests yet. This is a known gap.

If you add tests, use `pytest`. Place test files in a `tests/` directory mirroring the structure of the module being tested:

```
tests/
├── pipelines/
│   └── test_simulate_invoices.py
└── analytics/
    └── test_demand_atlas.py
```

The most valuable tests to write first are:
- Schema validation on the `synthetic_invoices` table after simulation
- Assertion that stockout probability values are between 0 and 1
- Assertion that all outlet-SKU pairs in `demand_profiles` have `weekly_units >= 1`

---

## Submitting changes

This project does not have a formal PR review process yet. If you are working on a significant change:

1. Create a branch: `git checkout -b your-feature-name`
2. Make your changes
3. Test locally — run the full pipeline end to end and verify the dashboard loads
4. Commit with a clear message describing what changed and why
5. Push and open a pull request with a description of the change and any limitations

For small fixes, typos, minor bug fixes, documentation, commit directly to main it's fine.

---

## Questions

If something in the codebase is unclear, the best reference is `docs/CONTEXT.md` which documents the product decisions and architecture choices that shaped the implementation. If that does not answer your question, open an issue.