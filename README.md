# ENG2040 Assignment 1: Marketplace Orders and Delivery Outcomes

Task brief: `supplied/assignment_01_brief.pdf`.

## Reproduce everything

Requires [uv](https://docs.astral.sh/uv/). The environment is pinned in `uv.lock` (Python 3.12).
`supplied/data/raw.sql` is not committed. Copy it in from the course package first (`mkdir -p supplied/data`); `run.py` stops if its sha256 differs.

```sh
uv run python run.py          # everything, about 5 min
uv run python run.py --fast   # reuse the last engine comparison, under 1 min
```

`run.py` checks `supplied/` against `supplied.sha256`, rebuilds `data/marketplace.sqlite` with the
supplied `setup_db.py`, runs `bench.py` (step 1 engine comparison), executes `pipeline.ipynb` top to
bottom on the `eng2040-a1` kernel (installed inside `.venv`), and writes `data/manifest.sha256` with a
hash of every output, then runs `check_claims.py`. Two fresh runs give the same manifest. Timing files are left out of it.
`bench.py` downloads DuckDB's sqlite extension on its first run (cached afterwards).

## Files

| File | What it is |
|---|---|
| `pipeline.ipynb` | the whole pipeline, one section per step, executed |
| `helpers.py` | what every step uses: db connection, resource tracking, late rates with intervals, plot style |
| `sql/orders.sql`, `sql/items.sql` | the SQL step 1 runs (one row per order, one row per item) |
| `bench.py` | step 1 engine comparison: pandas, sqlite SQL, DuckDB, at 1x/3x/10x data |
| `run.py` | the one command |
| `check_claims.py` | checks every number typed in the notebook text and `report.md` against the outputs, fails if one drifts |
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

## Where the brief is answered

Notebook sections are in `pipeline.ipynb`; files are under `data/`.

| Brief asks | Answered in |
|---|---|
| label: late after the estimated date, on the date is on time, unreliable outcomes unlabelled, local clock | step 2 "labels", `02_clean/record_accounting.csv` |
| predictors only what is known at approval | step 4 intro (forbidden columns dropped first), `04_features/leakage_check.csv`, `baseline_model.csv` |
| 1: access efficiently, one row per order | `sql/orders.sql`, step 1, `01_load/orders.parquet` |
| 1: what tables and keys represent | step 1 "tables and keys", `01_load/key_links.csv` |
| 1: records, counts and totals preserved | `01_load/checks.csv` (db vs output, all equal) |
| 1: most efficient in runtime, memory, storage | step 1 "why this way", `01_load/bench.csv`, `engine_comparison.png`, parquet vs csv |
| 2: profile, problems found and why | `02_clean/profile.csv`, step 2 "prices", "product sizes and weights", `fix_evidence.csv` |
| 2: traceable changes and exclusions | `02_clean/changes.parquet` (every value, old and new), `cleaning_summary.csv`, `record_accounting.csv` (all 20,000) |
| 2: unresolved issues and their effect | step 2 "unresolved", step 3 `sensitivity.csv` |
| 2: missing optional field does not drop an order | step 2 "unresolved", last bullet |
| 3: q1, q2, q3 | step 3 "q1", "q2", "q3" and "answers", `03_eda/q*` (chart + data) |
| 3: data quality, sensitivity, confidence | step 3 "how much the answers depend...", "answers", wilson intervals, cancelled-order bounds |
| 4: numeric table, one row per retained order, ids and labels separate | `04_features/features.parquet`, `ids_labels.parquet` |
| 4: numerical, categorical, date/time representation, new features, what was kept and why | step 4 intro, "which features to keep" |
| 4: meaning of each feature | `04_features/feature_descriptions.csv` (meaning and source columns) |
| 5: one command reproduces every step | `run.py`, `data/manifest.sha256` (fresh clone gives the same hashes) |
| 5: estimated vs measured memory, storage, intermediate data, runtime per step | step 5, `05_resources/resources_summary.csv`, `data/0*/resources.json` |
| 5: chart data, code, executed SQL, environment, checks | `03_eda/*.csv`, notebook, `sql/`, `05_resources/environment.json`, `01_load/checks.csv`, `check_claims.py` |
| 5: 6-8 page report | `report.md` (draft) |

