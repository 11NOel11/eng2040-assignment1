# ENG2040 Assignment 1: Marketplace Orders and Delivery Outcomes

Task brief: `supplied/assignment_01_brief.pdf`.

## Setup

Requires [uv](https://docs.astral.sh/uv/). The environment is pinned in `uv.lock`.

```sh
uv sync                                                  # create .venv from the lockfile
uv run python supplied/setup_db.py --db marketplace.sqlite
```

`supplied/` holds the files as distributed, unchanged. `supplied/data/raw.sql` is not
committed; place it there from the course package and check it with
`shasum -a 256 -c supplied.sha256`.
