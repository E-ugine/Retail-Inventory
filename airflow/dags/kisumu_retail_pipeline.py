from airflow import DAG
from airflow.operators.python import PythonOperator
from datetime import datetime, timedelta
import subprocess
import os
from pathlib import Path

default_args = {
    "owner": "eugine",
    "retries": 1,
    "retry_delay": timedelta(minutes=2),
    "email_on_failure": False,
}

PROJECT_ROOT = "/Users/eugineagolla/Projects/Retail-Inventory"
PYTHON = os.path.join(PROJECT_ROOT, "venv", "bin", "python")

def run_script(script_path, skip_if_exists=None):
    if skip_if_exists:
        check_path = Path(skip_if_exists)
        if check_path.exists():
            print(f"Skipping — output already exists: {check_path}")
            return "Skipped"

    result = subprocess.run(
        [PYTHON, os.path.join(PROJECT_ROOT, script_path)],
        capture_output=True,
        text=True,
        cwd=PROJECT_ROOT,
        env={**os.environ, "PYTHONPATH": PROJECT_ROOT}
    )

    print(result.stdout)
    if result.stderr:
        print(result.stderr)

    if result.returncode != 0:
        raise Exception(f"{script_path} failed:\n{result.stderr}")

    return f"{script_path} done"


# Individual callables defined explicitly
# Lambda functions inside DAGs cause Airflow serialisation issues
def task_extract_osm():
    return run_script(
        "pipelines/extract_osm_outlets.py",
        skip_if_exists=f"{PROJECT_ROOT}/data/raw/kisumu_osm_outlets.csv"
    )

def task_load_to_db():
    return run_script(
        "pipelines/load_outlets_to_db.py",
        skip_if_exists=f"{PROJECT_ROOT}/data/raw/kisumu_osm_outlets.geojson"
    )

def task_fmcg_filter():
    return run_script("pipelines/update_fmcg_filter.py")

def task_geocode():
    return run_script(
        "pipelines/reverse_geocode_outlets.py",
        skip_if_exists=f"{PROJECT_ROOT}/data/processed/kisumu_fmcg_outlets_geocoded.csv"
    )

def task_product_catalog():
    return run_script(
        "pipelines/build_product_catalog.py",
        skip_if_exists=f"{PROJECT_ROOT}/data/processed/fmcg_product_catalog.csv"
    )

def task_demand_profiles():
    return run_script(
        "pipelines/build_demand_profiles.py",
        skip_if_exists=f"{PROJECT_ROOT}/data/processed/outlet_demand_profiles.csv"
    )

def task_simulate():
    return run_script(
        "pipelines/simulate_invoices.py",
        skip_if_exists=f"{PROJECT_ROOT}/data/synthetic/kisumu_synthetic_invoices.parquet"
    )

def task_demand_atlas():
    return run_script("analytics/demand_atlas.py")


with DAG(
    dag_id="kisumu_retail_pipeline",
    description="End-to-end Kisumu retail intelligence pipeline",
    default_args=default_args,
    start_date=datetime(2024, 1, 1),
    schedule_interval=None,
    catchup=False,
    tags=["kisumu", "retail", "fmcg"],
) as dag:

    extract_osm = PythonOperator(
        task_id="extract_osm_outlets",
        python_callable=task_extract_osm,
    )

    load_to_db = PythonOperator(
        task_id="load_outlets_to_db",
        python_callable=task_load_to_db,
    )

    fmcg_filter = PythonOperator(
        task_id="update_fmcg_filter",
        python_callable=task_fmcg_filter,
    )

    geocode = PythonOperator(
        task_id="reverse_geocode_outlets",
        python_callable=task_geocode,
        execution_timeout=timedelta(minutes=30),
    )

    product_catalog = PythonOperator(
        task_id="build_product_catalog",
        python_callable=task_product_catalog,
    )

    demand_profiles = PythonOperator(
        task_id="build_demand_profiles",
        python_callable=task_demand_profiles,
    )

    simulate = PythonOperator(
        task_id="simulate_invoices",
        python_callable=task_simulate,
    )

    demand_atlas = PythonOperator(
        task_id="demand_atlas",
        python_callable=task_demand_atlas,
    )

    (
        extract_osm
        >> load_to_db
        >> fmcg_filter
        >> geocode
        >> product_catalog
        >> demand_profiles
        >> simulate
        >> demand_atlas
    )