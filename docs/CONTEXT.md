# Retail Intelligence — Project Context

## What this is
A data product that generates outlet-level FMCG demand intelligence
for informal retail markets in Kenya. Built on publicly
available data with a synthetic transaction layer, designed to
demonstrate value to FMCG brand owners and distributors.

## The problem it solves
FMCG brand owners in Kenya can see distributor sell-in numbers
(what left the warehouse) but not sell-out numbers (what left
the duka shelf). This product infers the gap using spatial,
demographic, and simulated transaction data.

## Who the customer is
Regional commercial managers at mid-size Kenyan consumer goods
companies (KES 500M–5B revenue). First target city: Kisumu.

## Architecture decisions
- Public data sources: OSM (outlets), WorldPop (population),
  KNBS (consumption weights)
- Synthetic invoice layer: discrete event simulation, clearly
  labelled as synthetic in the demo
- Stack: Python, PostgreSQL + PostGIS, dbt, Streamlit
- Hosting: DigitalOcean ($20/month)


## 3-Month Roadmap
- Month 1: Data foundation (OSM, WorldPop, KNBS → PostGIS)
- Month 2: Synthetic invoice generator
- Month 3: Analytics modules + Streamlit demo

## Key risk
Distributor willingness to share invoice data. Demo de-risks
this by making the value exchange concrete before the ask.~