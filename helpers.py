"""Small pieces every step of pipeline.ipynb uses: db access, resource tracking, rates, plot style."""
import json, threading, time
from pathlib import Path
import adbc_driver_sqlite.dbapi as adbc
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
import psutil

ROOT = Path(__file__).resolve().parent
DATA, DB = ROOT / "data", ROOT / "data" / "marketplace.sqlite"
con = adbc.connect(f"file:{DB}?mode=ro")  # read only
q = lambda s: pd.read_sql(s, con, dtype_backend="pyarrow")  # adbc hands results over as arrow columns
read = lambda name, **kw: pd.read_parquet(DATA / f"{name}.parquet", **kw)  # read("02_clean/orders_clean")
mb = lambda b: round(b / 1e6, 2)
size = lambda df: mb(df.memory_usage(deep=True).sum())
days = lambda td: td.dt.total_seconds() / 86400
proc = psutil.Process()

def track(step):
    # call at the start of a step, call the returned done() at the end
    out = DATA / step
    out.mkdir(parents=True, exist_ok=True)
    stop, start, t = threading.Event(), proc.memory_info().rss, time.perf_counter()
    peak = [start]
    def sample():
        while not stop.wait(0.01):
            peak[0] = max(peak[0], proc.memory_info().rss)
    threading.Thread(target=sample, daemon=True).start()
    def done(**extra):
        stop.set()
        res = {"step": step, "seconds": round(time.perf_counter() - t, 2), "rss_start_MB": mb(start), "rss_peak_MB": mb(peak[0]),
               "rss_peak_above_start_MB": mb(peak[0] - start), **extra,
               "saved_MB": {f.name: mb(f.stat().st_size) for f in sorted(out.iterdir()) if f.name != "resources.json"}}
        (out / "resources.json").write_text(json.dumps(res, indent=1))
        return res
    return out, done

# ---- rates with 95% wilson intervals
SPIKE = ["2017-11", "2018-02", "2018-03"]  # the three worst months, found in q1
WEEKS = ["<1 week", "1-2", "2-3", "3-4", "4-5", "5-6", "6+ weeks"]

def wilson(k, n, z=1.96):
    p = k / n
    c, h = (p + z**2 / (2 * n)) / (1 + z**2 / n), z * np.sqrt(p * (1 - p) / n + z**2 / (4 * n**2)) / (1 + z**2 / n)
    return c - h, c + h

def rate(df, by):
    r = df.groupby(by, observed=True).late.agg(orders="size", late="sum").reset_index()
    r["late_rate"] = r.late / r.orders
    r["ci_low"], r["ci_high"] = wilson(r.late, r.orders)
    return r

def add_lead(df):
    # lead time = estimated date - approval, in days and in week groups
    df["lead_days"] = days(df.order_estimated_delivery_date - df.order_approved_at)
    df["lead_week"] = pd.cut(df.lead_days, [0, 7, 14, 21, 28, 35, 42, np.inf], labels=WEEKS, right=False)
    return df

# ---- plots: one accent colour, grey for the rest, labels on the data instead of legends
RED, GREY = "#b03a2e", "#a6a6a6"
plt.rcParams.update({"figure.dpi": 120, "font.size": 9, "axes.spines.top": False, "axes.spines.right": False,
                     "axes.titlesize": 10, "axes.titlelocation": "left", "axes.titleweight": "bold"})

def save(fig, path):
    fig.tight_layout(); fig.savefig(path); plt.show()
