# ENG2040 Assignment 1: Marketplace Orders and Delivery Outcomes

Task brief: `supplied/assignment_01_brief.pdf`.

## Reproduce everything

`supplied/data/raw.sql` is not committed. Copy it in from the course package first (`mkdir -p supplied/data`). Then either:

**With [uv](https://docs.astral.sh/uv/)** (environment pinned in `uv.lock`, Python 3.12):

```sh
uv run --locked python run.py          # everything, about 6 min
uv run --locked python run.py --fast   # reuse the last engine comparison, under 1 min
```

**Without uv** (same pins, exported from `uv.lock` with hashes):

```sh
python3.12 -m venv .venv
.venv/bin/pip install --require-hashes -r requirements.txt
.venv/bin/python run.py
```

`run.py` fails loudly unless every check passes:

1. Python is 3.12, and with `uv run --locked` the lock file matches `pyproject.toml`
2. `supplied/` matches `supplied.sha256` (the brief, the loader and `raw.sql`)
3. `data/` is deleted first, so nothing from an earlier run survives
4. `data/marketplace.sqlite` is rebuilt with the supplied `setup_db.py`, `bench.py` runs the engine comparison, `pipeline.ipynb` runs top to bottom on the `eng2040-a1` kernel and stops at the first failing assert (row counts, totals, every order accounted for, feature types, id/label alignment)
5. every cell ran exactly once, in order, with no error output
6. every output file matches `expected.sha256` byte for byte. Timing files are left out, they differ every run. Charts are compared too but only warned on, since font rendering can differ between machines while the data behind each chart does not

`bench.py` downloads DuckDB's sqlite extension on its first run (needs internet once).

## Files

| File | What it is |
|---|---|
| `pipeline.ipynb` | the whole pipeline, one section per step, executed |
| `sql/orders.sql`, `sql/items.sql` | the SQL step 1 runs (one row per order, one row per item) |
| `bench.py` | step 1 engine comparison: pandas, sqlite SQL (two drivers), DuckDB, Polars, at 1x/3x/10x data |
| `run.py` | the one command, with the checks above |
| `expected.sha256` | hash of every output from a verified run |
| `requirements.txt` | the `uv.lock` pins for pip |
| `report/report.pdf` | the report (LaTeX source `report/report.tex`, figures read from `data/`) |

## Steps

| Step | Input | Output (`data/`) | One row is |
|---|---|---|---|
| 0 setup | `supplied/data/raw.sql` | `marketplace.sqlite`, `00_setup_db/resources.json` | as in the raw tables |
| 1 load | `marketplace.sqlite` | `01_load/orders.parquet` | one order |
| | | `01_load/items.parquet` | one order item with product + seller attributes |
| | | `01_load/checks.csv`, `key_links.csv` | one check / one key relationship |
| | | `01_load/storage.csv` | one storage format (csv, parquet with each codec) and its size |
| | | `01_load/bench.csv` (+ `_raw`), `engine_comparison.png` | one scale x engine (median of 3) |
| 2 clean | `01_load/*.parquet`, db payments + translation | `02_clean/orders_clean.parquet` | one order, all 20,000, label or `unlabelled_reason` |
| | | `02_clean/items_clean.parquet` | one order item |
| | | `02_clean/changes.parquet` | one changed value (key, column, rule, old, new) |
| | | `02_clean/cleaning_summary.csv`, `record_accounting.csv` (+ `.png`), `fix_evidence.csv`, `payment_reconciliation.csv`, `profile.csv` | one rule / one outcome / one problem / one check / one issue |
| 3 eda | `02_clean/orders_clean.parquet`, `items_clean.parquet` | `03_eda/q1_*`, `q2_*`, `q3_*` (`.png` + the data behind it as `.csv`) | one bar / point / group |
| | | `03_eda/q3_drilldown.csv` (+ `.png`), `sensitivity.csv` (+ `.png`), `cancelled_bounds.csv` | one state x group / one inclusion choice / one bound |
| 4 features | `02_clean/*_clean.parquet` | `04_features/features.parquet` | one labelled order, numbers only (no id, no label) |
| | | `04_features/ids_labels.parquet` | same row order: `order_id`, `delivered_after_estimate` |
| | | `04_features/feature_descriptions.csv`, `leakage_check.csv` | one feature |
| | | `04_features/baseline_model.csv` | one check model (time split test auc) |
| 5 resources | `data/0*/resources.json` | `05_resources/resources_summary.csv`, `environment.json`, `executed_sql.sql` | one step / one setting / one query |
| check | all outputs | `manifest.sha256` | one output file and its hash |

Each step folder also has `resources.json`: runtime, peak memory, saved file sizes.
`features.parquet` and `ids_labels.parquet` line up row by row; join them only when fitting a model.

Load a parquet output with `pd.read_parquet(path, dtype_backend="pyarrow")`. All parquet files are zstd compressed (`01_load/storage.csv` shows why).

## Where the brief is answered

Every question in the brief and every "Excellent" line of the rubric, and where it is met. Notebook sections are in `pipeline.ipynb`, files under `data/`, report sections in `report/report.pdf`.

| Brief or rubric asks | Met by |
|---|---|
| **Business goal** | |
| cleaned order data | `02_clean/orders_clean.parquet` (all 20,000 orders, label or reason) |
| business findings | step 3 "answers", report section 3 |
| reusable pipeline: inputs and labels for a future model | `run.py` (one command), `04_features/features.parquet` + `ids_labels.parquet` |
| label: late after the estimated date, on the date is on time, local clock | step 2 "labels" (calendar dates, no time zone shift) |
| cancelled, unknown or unreliable outcomes unlabelled | step 2 "labels", `02_clean/record_accounting.csv` (reason per order) |
| predictors only what is known at approval | step 4 intro (forbidden columns dropped before building), `feature_descriptions.csv` (source columns) |
| **1 Loading (20%)** | |
| access efficiently, one row per order | `sql/orders.sql` (aggregate per order in sqlite, then left join), step 1 |
| what tables and keys represent | step 1 "tables and keys", report table 1 |
| records, counts and totals preserved | `01_load/key_links.csv` (both directions), `01_load/checks.csv` (db vs output, all equal) |
| most efficient in runtime, memory, storage | `bench.py` + `01_load/bench.csv` (8 engines, 1x/3x/10x), `engine_comparison.png`, `01_load/storage.csv` (csv vs parquet codecs) |
| Excellent: evidence that meanings, relationships and totals are preserved | as above, plus `EXPLAIN QUERY PLAN` in step 1 |
| **2 Cleaning (20%)** | |
| profile the data | `02_clean/profile.csv` |
| problems found and why each fix | step 2 "prices", "product sizes and weights", `fix_evidence.csv` (witness match rates), report table 2 |
| traceable changes and exclusions | `02_clean/changes.parquet` (every value: key, column, rule, old, new), `cleaning_summary.csv`, `record_accounting.csv` |
| unresolved issues and their effect | step 2 "unresolved", step 3 `sensitivity.csv` |
| missing optional field does not drop an order | step 2 "unresolved", last bullet |
| Excellent: decisions backed by evidence | fix only with a witness (payments, the product's usual price, freight), else missing |
| Excellent: preserves uncertainty and valid exceptions | missing instead of guessed, extreme delays kept, 40-100 kg weights kept, 0 instalments valid |
| Excellent: accounts for every record | `record_accounting.csv` + `.png`, asserts on 20,000 orders and 22,662 items |
| **3 Analysis (30%)** | |
| q1 how often late, how long | step 3 "q1", `q1_*.png` + `.csv` |
| q2 lead time vs lateness | step 3 "q2", `q2_late_by_lead_time.png`, `q2_within_state_month.csv` (same state and month) |
| q3 states, where to investigate first | step 3 "q3", `q3_late_by_state.png`, `q3_drilldown.png` + `.csv` |
| data quality effect, sensitivity, confidence | `sensitivity.png` + `.csv`, `cancelled_bounds.csv`, 95% Wilson intervals on every rate |
| associations, not causation | step 3 "answers", report section 3 and limitations |
| Excellent: limitations and uncertainty explained | as above |
| **4 Features (20%)** | |
| numeric table, one row per retained order | `04_features/features.parquet` (16,482 x 72, all float64, asserted) |
| numerical, categorical, date/time representation | step 4 intro (sums, one hot with top 15 + other + missing, sin/cos for cyclic time) |
| new features, which were kept and why | step 4 "which features to keep" (two copies dropped, correlation check) |
| meaning of each feature | `04_features/feature_descriptions.csv` (meaning and source columns) |
| ids and labels matching but separate | `04_features/ids_labels.parquet`, same row order (asserted) |
| Excellent: evidence of reliability and no leakage | `leakage_check.csv` (single-feature AUC with a control), `baseline_model.csv` (time split, leak control) |
| **5 Reproducibility (10%)** | |
| one command reproduces every step | `run.py` checks every output against `expected.sha256` (a fresh clone, and a clean Linux container without uv, give the same hashes) |
| estimated vs measured: memory, temporary and saved storage, intermediate data, runtime, every step | step 5, `05_resources/resources_summary.csv`, `data/0*/resources.json` |
| chart data, code, executed SQL, environment, checks | `03_eda/*.csv`, notebook + `bench.py`, `05_resources/executed_sql.sql` + `sql/`, `environment.json`, `01_load/checks.csv` |
| README: inputs, outputs, row meaning, loading | the tables above |
| 6-8 page report justifying decisions, findings, limitations | `report/report.pdf` |
| **Throughout** | |
| choices justified against reasonable alternatives | engines (8), storage codecs (5), fixes (none / abs / 100 / 1000), interval (Wald vs Wilson), ranking (rate vs excess late orders) |
| estimated and measured memory and storage, with units and scope | step 5 "scope of the numbers", every number in MB or seconds |

## Decisions

| Decision | Alternatives tried | Why this one | Evidence |
|---|---|---|---|
| aggregate in sqlite through adbc | pandas, sqlite3 driver, duckdb (4 ways), polars streaming | least memory at every scale, speed is fine for a batch step | `01_load/bench.csv` |
| parquet with zstd | csv, parquet none / snappy / gzip | smallest at the same read and write speed, keeps types | `01_load/storage.csv` |
| fix a value only with a witness | always fix, always drop | fixes land at the clean-order match rate, nothing is guessed | `02_clean/fix_evidence.csv` |
| sizes over 100 kg / 200 cm to missing, not /1000 | divide by 1000 | freight shows they are wrong but cannot confirm the exact value | step 2 freight table |
| keep every order, give a reason | drop unusable orders | every record accounted for, sensitivity can put them back | `02_clean/record_accounting.csv`, `03_eda/sensitivity.csv` |
| Wilson intervals | normal approximation | stays valid for small states (0 of 8) | step 3 intro |
| rank states by excess late orders | late rate | counts the late deliveries a state adds, small states do not dominate | `03_eda/q3_late_by_state.csv` |
| missing stays NaN + flag, no imputation | median fill | a fill computed now would use test orders | step 4 intro |
| time split check model | random split | a model learns from the past and predicts the future | `04_features/baseline_model.csv` |
