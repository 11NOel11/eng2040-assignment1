# ENG2040 Assignment 1: Marketplace Orders and Delivery Outcomes

Task brief: `supplied/assignment_01_brief.pdf`.

## Reproduce everything

Requires [uv](https://docs.astral.sh/uv/). The environment is pinned in `uv.lock`.

```sh
uv run python run.py
```

This checks `supplied/` against `supplied.sha256`, rebuilds `data/marketplace.sqlite` from
`supplied/data/raw.sql` with the supplied loader, then executes each notebook in order on the
`eng2040-a1` kernel (installed inside `.venv`). `supplied/data/raw.sql` is not committed; put it
there from the course package first.

## Steps

| Step | Notebook | Input | Output (`data/`) | One row is |
|---|---|---|---|---|
| 0 setup | `supplied/setup_db.py` | `supplied/data/raw.sql` | `marketplace.sqlite` | as in the raw tables |
| 1 load | `notebooks/01_load.ipynb` | `marketplace.sqlite` | `01_load/orders.parquet` | one order |
| | | | `01_load/items.parquet` | one order item |
| | | | `01_load/checks.csv`, `key_links.csv`, `resources.json` | one check / one key link / step resources |

Load a parquet output with `pd.read_parquet(path, dtype_backend="pyarrow")`.
