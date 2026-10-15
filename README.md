# ENG2040 Assignment 1: Marketplace Orders and Delivery Outcomes

Task brief: `supplied/assignment_01_brief.pdf`.

## Reproduce everything

Requires [uv](https://docs.astral.sh/uv/). The environment is pinned in `uv.lock`.

```sh
uv run python run.py
```

This checks `supplied/` against `supplied.sha256`, rebuilds `data/marketplace.sqlite` from
`supplied/data/raw.sql` with the supplied loader, then executes `pipeline.ipynb` top to bottom on
the `eng2040-a1` kernel (installed inside `.venv`). One notebook, one section per step. `supplied/data/raw.sql` is not committed; put it
there from the course package first.

## Steps

| Step | Code | Input | Output (`data/`) | One row is |
|---|---|---|---|---|
| 0 setup | `supplied/setup_db.py` | `supplied/data/raw.sql` | `marketplace.sqlite` | as in the raw tables |
| 1 load | `pipeline.ipynb` step 1 | `marketplace.sqlite` | `01_load/orders.parquet` | one order |
| | | | `01_load/items.parquet` | one order item |
| | | | `01_load/checks.csv`, `key_links.csv`, `load_comparison.csv` (+ `_raw`), `resources.json` | one check / one key link / one scale x driver x approach / step resources |
| 2 clean | `pipeline.ipynb` step 2 | `01_load/*.parquet`, db payments + translation | `02_clean/orders_clean.parquet` | one order (all 20000, label or reason) |
| | | | `02_clean/items_clean.parquet` | one order item |
| | | | `02_clean/changes.parquet` | one changed value (old, new, rule) |
| | | | `02_clean/cleaning_summary.csv`, `record_accounting.csv`, `fix_evidence.csv`, `payment_reconciliation.csv`, `profile.csv`, `resources.json` | one rule / one outcome / one problem / one check / one issue / step resources |
| 3 eda | `pipeline.ipynb` step 3 | `02_clean/orders_clean.parquet` | `03_eda/q1_*.csv`, `q2_*.csv`, `q3_*.csv` + `.png` | one chart bar / group (the data behind each chart) |
| | | | `03_eda/sensitivity.csv` | one inclusion choice |
| | | | `03_eda/q1_late_by_month.*`, `q2_within_state_month.csv`, `late_rate_bounds.csv` | one month / one comparison / one bound |
| 4 features | `pipeline.ipynb` step 4 | `02_clean/orders_clean.parquet`, `items_clean.parquet` | `04_features/features.parquet` | one labelled order, numbers only (no id, no label) |
| | | | `04_features/ids_labels.parquet` | same row order: `order_id`, `delivered_after_estimate` |
| | | | `04_features/feature_descriptions.csv`, `leakage_check.csv` | one feature |
| 5 resources | `pipeline.ipynb` step 5 | `data/0*/resources.json` | `resources_summary.csv`, `environment.json` | one step / one setting |
| check | `run.py` | all outputs | `manifest.sha256` | one output file and its hash |

`features.parquet` and `ids_labels.parquet` line up row by row. Join them with
`pd.concat([ids, feats], axis=1)` only when fitting a model. Two runs of `run.py` give the same
`manifest.sha256`, so every output is reproduced byte for byte (timing files are left out of it).

Load a parquet output with `pd.read_parquet(path, dtype_backend="pyarrow")`.
