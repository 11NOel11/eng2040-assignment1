# ENG2040 Assignment 1: Marketplace Orders and Delivery Outcomes

Noel Thomas (25011152). Cleans 20,000 marketplace orders, answers three delivery questions and builds a model-ready feature table, all from one command.

- Report: [`report/report.pdf`](report/report.pdf)
- Pipeline: [`pipeline.ipynb`](pipeline.ipynb) (executed, one section per step)
- Repository: https://github.com/11NOel11/eng2040-assignment1
- Brief: `supplied/assignment_01_brief.pdf`

## Run it

Copy `raw.sql` from the course package into `supplied/data/` first (`mkdir -p supplied/data`). Then either:

```sh
# with uv (pins in uv.lock, Python 3.12)
uv run --locked python run.py          # everything, 5-10 min
uv run --locked python run.py --fast   # reuse the last engine comparison, under 1 min

# without uv (the same pins, with hashes)
python3.12 -m venv .venv
.venv/bin/pip install --require-hashes -r requirements.txt
.venv/bin/python run.py
```

`run.py` stops unless every check passes:

1. Python is 3.12 and `supplied/` matches `supplied.sha256`
2. `data/` is deleted and rebuilt from nothing
3. every notebook assert passes (row counts, totals, every order accounted for, feature types, id/label alignment), and every cell runs once, in order, with no error
4. every output matches `expected.sha256` byte for byte (charts only warn: fonts render differently between machines)

A fresh clone passes on macOS with uv and on clean Linux without uv. `bench.py` downloads DuckDB's sqlite extension once (needs internet).

Load any output with `pd.read_parquet(path, dtype_backend="pyarrow")`. Parquet files are zstd compressed.

## Files

| File | What it is |
|---|---|
| `pipeline.ipynb` | the pipeline, steps 1-5 |
| `sql/orders.sql`, `sql/items.sql` | the SQL step 1 runs |
| `bench.py` | step 1 engine comparison (8 engines, 1x/3x/10x data) |
| `run.py` | the one command and its checks |
| `pyproject.toml`, `uv.lock`, `requirements.txt` | the environment |
| `supplied.sha256`, `expected.sha256` | hashes of the inputs and of every output |
| `report/report.pdf` | the report |

## Steps

| Step | Input | Output in `data/` | One row is |
|---|---|---|---|
| 0 setup | `supplied/data/raw.sql` | `marketplace.sqlite` | as in the raw tables |
| 1 load | `marketplace.sqlite` | `01_load/orders.parquet` | one order |
| | | `01_load/items.parquet` | one item, with product and seller attributes |
| | | `01_load/checks.csv`, `key_links.csv` | one count or total check / one key relationship |
| | | `01_load/bench.csv`, `storage.csv`, `engine_comparison.png` | one engine x scale / one storage format |
| 2 clean | `01_load/*.parquet`, payments and translation from the db | `02_clean/orders_clean.parquet` | one order (all 20,000): label, or `unlabelled_reason` |
| | | `02_clean/items_clean.parquet` | one item |
| | | `02_clean/changes.parquet` | one changed value: key, column, rule, old, new |
| | | `02_clean/profile.csv`, `fix_evidence.csv`, `cleaning_summary.csv`, `record_accounting.csv`, `payment_reconciliation.csv` | one issue / fix / rule / outcome / check |
| 3 analysis | `02_clean/*_clean.parquet` | `03_eda/*.png` with the data behind each chart as `.csv` | one bar, point or group |
| | | `03_eda/sensitivity.csv`, `cancelled_bounds.csv` | one inclusion choice / one bound |
| 4 features | `02_clean/*_clean.parquet` | `04_features/features.parquet` | one labelled order, numbers only |
| | | `04_features/ids_labels.parquet` | same row order: `order_id`, `delivered_after_estimate` |
| | | `04_features/feature_descriptions.csv`, `leakage_check.csv` | one feature |
| | | `04_features/baseline_model.csv` | one time cutoff x model: test AUC and 95% interval |
| 5 resources | every step's `resources.json` | `05_resources/resources_summary.csv`, `environment.json`, `executed_sql.sql` | one step / one setting / one query |

Every step folder has a `resources.json`: runtime, peak memory and saved file sizes.

## Where the brief is answered

| Brief | Report | Evidence |
|---|---|---|
| 1 tables and keys, records and totals preserved, most efficient approach | §1 | `key_links.csv`, `checks.csv`, `bench.csv`, `storage.csv` |
| 2 problems found and why, traceable changes, unresolved issues | §2 | `profile.csv`, `fix_evidence.csv`, `changes.parquet`, `record_accounting.csv` |
| 3 q1, q2, q3, data quality, sensitivity, confidence | §3 | `03_eda/`, `sensitivity.csv`, `cancelled_bounds.csv` |
| 4 representation, new and kept features, meanings, ids and labels, no leakage | §4 | `feature_descriptions.csv`, `leakage_check.csv`, `baseline_model.csv` |
| 5 one command, estimated vs measured resources, environment, executed SQL | §5 | `run.py`, `expected.sha256`, `resources_summary.csv`, `environment.json`, `executed_sql.sql` |
