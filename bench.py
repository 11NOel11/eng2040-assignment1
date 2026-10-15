"""Step 1 engine comparison: same one-row-per-order table, eight ways, at 1x/3x/10x data.
uv run python bench.py   (3-8 min, run.py calls it, writes data/01_load/bench*.csv)"""
import shutil, sqlite3, subprocess, sys
from pathlib import Path
import pandas as pd

ROOT = Path(__file__).resolve().parent
DB = ROOT / "data" / "marketplace.sqlite"
OUT = ROOT / "data" / "01_load"
TMP = OUT / "_bench"
TABLES = ["orders", "customers", "order_items", "order_payments", "order_reviews"]
SQL = (ROOT / "sql" / "orders.sql").read_text()

def scaled(k):
    # k copies of the extract with new ids, same schema and indexes
    path = TMP / f"x{k}.sqlite"
    s = sqlite3.connect(path)
    s.execute(f"attach '{DB}' as src")
    for (ddl,) in s.execute(f"select sql from src.sqlite_master where tbl_name in {tuple(TABLES)} and sql is not null order by type desc"):
        s.execute(ddl)
    for t in TABLES:
        cols = [r[1] for r in s.execute(f"pragma src.table_info({t})")]
        for c in range(k):
            s.execute(f"insert into {t} select {', '.join(f'{x} || {chr(39)}_{c}{chr(39)}' if x in ('order_id', 'customer_id') else x for x in cols)} from src.{t}")
    s.commit(); s.close()
    pq = TMP / f"x{k}"
    pq.mkdir()
    for t in TABLES:  # columnar copy for the parquet run, its cost is timed too
        subprocess.run([sys.executable, "-c", f"import duckdb; duckdb.sql(\"copy (select * from sqlite_scan('{path}', '{t}')) to '{pq}/{t}.parquet'\")"], check=True)
    return path, pq

# each run is its own process: setup, then time + peak memory of the body only
HEAD = "import resource, sys, time\nimport pandas as pd\n"
CONNECT = {
    "adbc": "import adbc_driver_sqlite.dbapi as adbc\ncon = adbc.connect('file:' + sys.argv[1] + '?mode=ro')\n",
    "duckdb": "import duckdb\ncon = duckdb.connect()\ncon.execute('load sqlite')\n",
    "polars": "import polars as pl\n",
    "sqlite3": "import sqlite3\ncon = sqlite3.connect('file:' + sys.argv[1] + '?mode=ro', uri=True)\n",
}
RUNS = {
    "pandas (adbc reads whole tables)": ("adbc", """
r = lambda t: pd.read_sql(f"select * from {t}", con, dtype_backend="pyarrow")
o, c, i, p, rv = r("orders"), r("customers"), r("order_items"), r("order_payments"), r("order_reviews")
i["pn"], i["fn"], p["vn"] = i.price.isna(), i.freight_value.isna(), p.payment_value.isna()
it = i.groupby("order_id").agg(n_items=("order_item_id", "size"), n_products=("product_id", "nunique"), n_sellers=("seller_id", "nunique"),
    price_sum=("price", "sum"), freight_sum=("freight_value", "sum"), n_price_null=("pn", "sum"), n_freight_null=("fn", "sum"))
pay = p.groupby("order_id").agg(n_payments=("payment_sequential", "size"), payment_sum_centavos=("payment_value", "sum"), n_payment_null=("vn", "sum"))
rev = rv.groupby("order_id").size().rename("n_reviews")
df = o.merge(c, on="customer_id", how="left").join(it, on="order_id").join(pay, on="order_id").join(rev, on="order_id")
"""),
    "sqlite sql (adbc)": ("adbc", "df = pd.read_sql(open(sys.argv[3]).read(), con, dtype_backend='pyarrow')\n"),
    "sqlite sql (python sqlite3 driver)": ("sqlite3", "df = pd.read_sql(open(sys.argv[3]).read(), con)\n"),
    "duckdb sql on sqlite": ("duckdb", """con.execute(f"attach '{sys.argv[1]}' as db (type sqlite, read_only); use db")
df = con.sql(open(sys.argv[3]).read()).arrow().read_all().to_pandas(types_mapper=pd.ArrowDtype)
"""),
    "duckdb sql on parquet": ("duckdb", """for tb in ["orders", "customers", "order_items", "order_payments", "order_reviews"]:
    con.execute(f"create view {tb} as select * from '{sys.argv[2]}/{tb}.parquet'")
df = con.sql(open(sys.argv[3]).read()).arrow().read_all().to_pandas(types_mapper=pd.ArrowDtype)
"""),
}
RUNS["duckdb sql on parquet, 1 thread"] = ("duckdb", "con.execute('set threads=1')\n" + RUNS["duckdb sql on parquet"][1])
# polars runs the same sql lazily on the parquet copies with its streaming engine (lab 7)
RUNS["polars sql on parquet, streaming"] = ("polars", """ctx = pl.SQLContext({tb: pl.scan_parquet(f"{sys.argv[2]}/{tb}.parquet") for tb in ["orders", "customers", "order_items", "order_payments", "order_reviews"]})
df = ctx.execute(open(sys.argv[3]).read()).collect(engine="streaming").to_pandas(use_pyarrow_extension_array=True)
""")
# result written straight to a parquet file instead of into python
RUNS["duckdb sql on parquet, streamed to a file"] = ("duckdb", RUNS["duckdb sql on parquet"][1].split("df =")[0] + """con.execute(f"copy ({open(sys.argv[3]).read().rstrip().rstrip(';')}) to '{sys.argv[2]}/out.parquet'")
df = range(con.sql(f"select count(*) from '{sys.argv[2]}/out.parquet'").fetchone()[0])
""")
TAIL = "\nprint(time.perf_counter() - t, resource.getrusage(resource.RUSAGE_SELF).ru_maxrss / (1e6 if sys.platform == 'darwin' else 1e3), len(df))\n"

def run(driver, body, db, pq):
    code = HEAD + CONNECT[driver] + "t = time.perf_counter()\n" + body + TAIL
    out = subprocess.run([sys.executable, "-c", code, str(db), str(pq), str(ROOT / "sql" / "orders.sql")], capture_output=True, text=True, check=True)
    s, peak, n = out.stdout.split()
    return float(s), float(peak), int(n)

if __name__ == "__main__":
    shutil.rmtree(TMP, ignore_errors=True); TMP.mkdir(parents=True)
    rows = []
    for k in [1, 3, 10]:
        db, pq = scaled(k)
        mb = db.stat().st_size / 1e6, sum(f.stat().st_size for f in pq.iterdir()) / 1e6
        jobs = [(d, "baseline", "df = []\n") for d in CONNECT] + [(d, name, body) for name, (d, body) in RUNS.items()]
        rows += [(k, d, name, rep, *run(d, body, db, pq), *mb) for rep in range(3) for d, name, body in jobs]
        shutil.rmtree(pq); db.unlink()
    shutil.rmtree(TMP)
    raw = pd.DataFrame(rows, columns=["scale", "driver", "approach", "rep", "seconds", "peak_MB", "rows", "sqlite_MB", "parquet_MB"])
    med = raw.groupby(["scale", "driver", "approach"])[["seconds", "peak_MB", "rows", "sqlite_MB", "parquet_MB"]].median().reset_index()
    base = med[med.approach == "baseline"].set_index(["scale", "driver"]).peak_MB
    med = med[med.approach != "baseline"]
    med["MB_above_baseline"] = med.peak_MB - base.loc[list(zip(med.scale, med.driver))].values
    raw.to_csv(OUT / "bench_raw.csv", index=False)
    med.round(2).to_csv(OUT / "bench.csv", index=False)
    print(med.pivot_table(index="approach", columns="scale", values=["MB_above_baseline", "seconds"]).round(2).to_string())
