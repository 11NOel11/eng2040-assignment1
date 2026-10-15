# ENG2040 Assignment 1: Marketplace Orders and Delivery Outcomes

Task brief: `supplied/assignment_01_brief.pdf`.

## Reproduce everything

Requires [uv](https://docs.astral.sh/uv/). The environment is pinned in `uv.lock` (Python 3.12).
`supplied/data/raw.sql` is not committed. Copy it in from the course package first (`mkdir -p supplied/data`); `run.py` stops if its sha256 differs.

```sh
uv run python run.py          # everything, about 4 min
uv run python run.py --fast   # reuse the last engine comparison, under 1 min
```

`run.py` checks `supplied/` against `supplied.sha256`, rebuilds `data/marketplace.sqlite` with the
supplied `setup_db.py`, runs `bench.py` (step 1 engine comparison), executes `pipeline.ipynb` top to
bottom on the `eng2040-a1` kernel (installed inside `.venv`), and writes `data/manifest.sha256` with a
hash of every output. Two fresh runs give the same manifest. Timing files are left out of it.
`bench.py` downloads DuckDB's sqlite extension on its first run (cached afterwards).

## Files

| File | What it is |
|---|---|
| `pipeline.ipynb` | the whole pipeline, one section per step, executed |
| `helpers.py` | what every step uses: db connection, resource tracking, late rates with intervals, plot style |
| `sql/orders.sql`, `sql/items.sql` | the SQL step 1 runs (one row per order, one row per item) |
| `bench.py` | step 1 engine comparison: pandas, sqlite SQL, DuckDB, at 1x/3x/10x data |
| `run.py` | the one command |
| `report.md` | report draft |

## Steps

| Step | Input | Output (`data/`) | One row is |
|---|---|---|---|
| 0 setup | `supplied/data/raw.sql` | `marketplace.sqlite`, `00_setup_db/resources.json` | as in the raw tables |
| 1 load | `marketplace.sqlite` | `01_load/orders.parquet` | one order |
| | | `01_load/items.parquet` | one order item with product + seller attributes |
| | | `01_load/checks.csv`, `key_links.csv` | one check / one key relationship |
| | | `01_load/bench.csv` (+ `_raw`), `engine_comparison.png` | one scale x engine (median of 3) |
| 2 clean | `01_load/*.parquet`, db payments + translation | `02_clean/orders_clean.parquet` | one order, all 20,000, label or `unlabelled_reason` |
| | | `02_clean/items_clean.parquet` | one order item |
| | | `02_clean/changes.parquet` | one changed value (key, column, rule, old, new) |
| | | `02_clean/cleaning_summary.csv`, `record_accounting.csv` (+ `.png`), `fix_evidence.csv`, `payment_reconciliation.csv`, `profile.csv` | one rule / one outcome / one problem / one check / one issue |
| 3 eda | `02_clean/orders_clean.parquet`, `items_clean.parquet` | `03_eda/q1_*`, `q2_*`, `q3_*` (`.png` + the data behind it as `.csv`) | one bar / point / group |
| | | `03_eda/q3_drilldown.csv`, `sensitivity.csv` | one state x group / one inclusion choice |
| 4 features | `02_clean/*_clean.parquet` | `04_features/features.parquet` | one labelled order, numbers only (no id, no label) |
| | | `04_features/ids_labels.parquet` | same row order: `order_id`, `delivered_after_estimate` |
| | | `04_features/feature_descriptions.csv`, `leakage_check.csv` | one feature |
| | | `04_features/baseline_model.csv` | one model check (time split test auc) |
| 5 resources | `data/0*/resources.json` | `05_resources/resources_summary.csv`, `environment.json` | one step / one setting |
| check | all outputs | `manifest.sha256` | one output file and its hash |

Each step folder also has `resources.json`: runtime, peak memory, saved file sizes.
`features.parquet` and `ids_labels.parquet` line up row by row; join them only when fitting a model.

Load a parquet output with `pd.read_parquet(path, dtype_backend="pyarrow")`.
