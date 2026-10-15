"""Every number typed into the notebook text and report.md, checked against the outputs it comes from.
uv run python check_claims.py   (run.py calls it last). A claim fails if its text is gone or its numbers moved."""
import json, re, sqlite3, subprocess, sys
from pathlib import Path
import nbformat
import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parent
D = ROOT / "data"
NB = "\n".join(c.source for c in nbformat.read(ROOT / "pipeline.ipynb", 4).cells if c.cell_type == "markdown")
REPORT = (ROOT / "report.md").read_text()
csv = lambda name, **kw: pd.read_csv(D / f"{name}.csv", **kw)
res = lambda step: json.loads((D / step / "resources.json").read_text())

# ---- values from the outputs
db = sqlite3.connect(D / "marketplace.sqlite")
n = lambda t: db.execute(f"select count(*) from {t}").fetchone()[0]
links = csv("01_load/key_links", index_col=0).n
checks = csv("01_load/checks", index_col=0).output
b = csv("01_load/bench").query("scale == 10").set_index("approach")
mbx = b.MB_above_baseline
it = pd.read_parquet(D / "01_load/items.parquet")
p, fr = it.price, it.freight_value
size = lambda c: it[c].astype(float)
L = ["product_length_cm", "product_height_cm", "product_width_cm"]
w = size("product_weight_g")
ev = csv("02_clean/fix_evidence", index_col=0)
acc = csv("02_clean/record_accounting", index_col=0).orders
prof = csv("02_clean/profile", index_col=0)["count"]
recon = csv("02_clean/payment_reconciliation", index_col=0).orders
summ = csv("02_clean/cleaning_summary").set_index(["column", "rule"])["values"]
o = pd.read_parquet(D / "02_clean/orders_clean.parquet")
lab = o[o.unlabelled_reason.isna()]
late = lab.days_late[lab.days_late > 0]
early = -lab.days_late[lab.days_late <= 0].median()
r = o[o.unlabelled_reason == "delivery dated before purchase or approval"]
shift = ((r.order_approved_at - r.order_delivered_customer_date) == pd.Timedelta(days=7)).sum()
rate = lab.delivered_after_estimate.mean()
months = csv("03_eda/q1_late_by_month").set_index("month").late_rate
calm = months.drop(["2017-11", "2018-02", "2018-03"])
q2 = csv("03_eda/q2_late_by_lead_time").set_index("lead_week")
q2s = csv("03_eda/q2_within_state_month", index_col=0).value
st = csv("03_eda/q3_late_by_state").set_index("customer_state")
drill = csv("03_eda/q3_drilldown").set_index(["state", "group"]).excess_late
sens = csv("03_eda/sensitivity", index_col=0)
canc = o[o.unlabelled_reason == "cancelled or unavailable"]
k, nl, c = lab.delivered_after_estimate.sum(), len(lab), len(canc)
outside = int(((st.ci_low > rate) | (st.ci_high < rate)).sum())
leak = csv("04_features/leakage_check", index_col=0).auc
feats = pd.read_parquet(D / "04_features/features.parquet")
model = csv("04_features/baseline_model", index_col=0)["test auc"]
test = lab[lab.order_purchase_timestamp.fillna(lab.order_approved_at) >= "2018-04-01"]
rs = csv("05_resources/resources_summary", index_col=0)
env = json.loads((D / "05_resources/environment.json").read_text())
wt, frv = w, fr.where((fr >= 0) & (fr <= 500))
lo, hi = (wt[wt > 100000] / 1000).quantile([0.25, 0.75])
fr_claims = [frv[wt > 100000].median(), lo / 1000, hi / 1000, frv[wt.between(lo, hi)].median(), 20, 30, frv[wt.between(20000, 30000)].median()]
fx = feats.drop(columns=feats.filter(like="_missing").columns).corr().abs()
ok_ = (p > 0) & (p <= 5000)
usual = p[ok_].groupby(it.product_id[ok_]).median()
usual_claims = []
for bad, fixed in [(p < 0, p.abs()), (p > 5000, p / 1000)]:
    u = it.product_id[bad.fillna(False)].map(usual)
    usual_claims += [(fixed[u.index].round(2) == u.round(2)).sum(), u.notna().sum()]
ic = pd.read_parquet(D / "02_clean/items_clean.parquet")
zs = pd.concat([o[["customer_zip_code_prefix", "customer_state"]].set_axis(["zip", "state"], axis=1), ic[["seller_zip_code_prefix", "seller_state"]].set_axis(["zip", "state"], axis=1)]).dropna()
zip_conflicts = (zs.groupby("zip").state.nunique() > 1).sum()
corr_max = fx.where(np.triu(np.ones(fx.shape, bool), 1)).stack().max()
z = 1.96 ** 2
raw = (ROOT / "supplied/data/raw.sql")

def peak(code):
    # peak rss of a fresh python running code, MB
    out = subprocess.run([sys.executable, "-c", code + "\nimport resource,sys;print(resource.getrusage(resource.RUSAGE_SELF).ru_maxrss/(1e6 if sys.platform=='darwin' else 1e3))"],
                         capture_output=True, text=True, check=True)
    return float(out.stdout)

def objects_mb():
    import tracemalloc
    con = sqlite3.connect(D / "marketplace.sqlite")
    tracemalloc.start()
    rows = con.execute((ROOT / "sql/orders.sql").read_text()).fetchall()
    return tracemalloc.get_traced_memory()[0] / 1e6

# ---- claims: (where, text exactly as written, values of the numbers in that text in order, relative tolerance)
# values can also be True/False for a claim like "under 2%"
# tolerance 0 = must match at the precision written. timings and memory get 10-20%, they move between runs
C = [
    # step 1
    ("nb", "| orders | 20,000 |", [n("orders")], 0),
    ("nb", "| order_items | 22,662 |", [n("order_items")], 0),
    ("nb", "| order_payments | 20,875 |", [n("order_payments")], 0),
    ("nb", "| order_reviews | 19,966 |", [n("order_reviews")], 0),
    ("nb", "| 11,334 / 2,071 |", [n("products"), n("sellers")], 0),
    ("nb", "| category_translation | 73 |", [n("category_translation")], 0),
    ("nb", "the same one-row-per-order table built 7 ways, at 1x, 3x and 10x", [len(b), 1, 3, 10], 0),
    ("nb", "(about 420 vs 405 MB at 10x)", [mbx["sqlite sql (python sqlite3 driver)"], mbx["pandas (adbc reads whole tables)"], 10], 0.1),
    ("nb", "take about 20 MB as python objects against 7 MB as a dataframe", [objects_mb(), res("01_load")["in_memory_MB"]["orders"]], 0.15),
    ("nb", "(120 vs 405 MB at 10x)", [mbx["sqlite sql (adbc)"], mbx["pandas (adbc reads whole tables)"], 10], 0.1),
    ("nb", "at 10x it is 6-16x faster than pandas and sqlite sql", [10, b.seconds["pandas (adbc reads whole tables)"] / b.seconds["duckdb sql on parquet"],
                                                                    b.seconds["sqlite sql (adbc)"] / b.seconds["duckdb sql on parquet"]], 0.2),
    ("nb", "but holds 310-480 MB", [mbx.filter(like="duckdb").min(), mbx.filter(like="duckdb").max()], 0.1),
    ("nb", "doesnt help either (480 MB)", [mbx["duckdb sql on parquet, streamed to a file"]], 0.1),
    ("nb", "2 seconds at 10x", [b.seconds["sqlite sql (adbc)"], 10], 0.2),
    # step 2
    ("nb", "normal prices top out at 4,690 and the big ones start at 6,499. freight 314 vs 1,000", [p[p <= 5000].max(), p[p > 5000].min(), fr[fr <= 500].max(), fr[fr > 500].min()], 0),
    ("nb", "on clean orders this holds for about 90%", [ev.none["clean orders (reference)"] * 100], 0),
    ("nb", "lengths top out at 105-118 cm and the big ones start at 2,000 cm", [min(size(c)[size(c) <= 200].max() for c in L), max(size(c)[size(c) <= 200].max() for c in L),
                                                                               min(size(c)[size(c) > 200].min() for c in L)], 0),
    ("nb", "weights run to 30 kg, then three values (40.4, 50, 100 kg)", [w[w <= 40000].max() / 1000, *sorted(w[(w > 40000) & (w <= 100000)].unique() / 1000)], 0),
    ("nb", "7.23 extra on ~830 orders", [7.23, recon["  paid exactly 7.23 more"]], 0.01),
    ("nb", "carrier pickup before approval (270)", [int(prof["carrier pickup before approval"])], 0),
    ("nb", "`not_reported` (804) and the deliveries dated exactly 7 days before approval (782 of the 791", [int(prof["status not_reported"]), 7, shift, len(r)], 0),
    ("nb", "the extreme delays (up to 188 days late)", [lab.days_late.max()], 0),
    ("nb", "they are 14 orders", [(lab.days_late > 60).sum()], 0),
    # step 3
    ("nb", "0 late out of 8 gives 0-0%), wilson doesnt (0-32%)", [0, 8, 0, 0, 0, 100 * z / (8 + z)], 0),
    ("nb", "(6.7%, 95% interval 6.3-7.1%)", [100 * rate, 95, *[100 * float(x) for x in sens.ci["baseline"].split("-")]], 0),
    ("nb", "(median 7 days, middle half 3-13)", [late.median(), late.quantile(.25), late.quantile(.75)], 0),
    ("nb", "1 in 8 is 3+ weeks late", [1, 1 / (late >= 21).mean(), 3], 0.03),
    ("nb", "the typical on-time order arrives 13 days early", [early], 0),
    ("nb", "march 2018 were late 18% of the time, february 2018 14%, november 2017 (black friday) 12%, against 1-8% in other months",
     [2018, 100 * months["2018-03"], 2018, 100 * months["2018-02"], 2017, 100 * months["2017-11"], 100 * calm.min(), 100 * calm.max()], 0),
    ("nb", "estimates under a week are late 16% of the time", [100 * q2.late_rate["<1 week"]], 0),
    ("nb", "from 1 to 5 weeks it sits at 5-7%", [1, 5, 100 * q2.late_rate[["1-2", "2-3", "3-4", "4-5"]].min(), 100 * q2.late_rate[["1-2", "2-3", "3-4", "4-5"]].max()], 0),
    ("nb", "beyond 6 weeks under 2%", q2.late_rate["6+ weeks"] < 0.02, 0),
    ("nb", "short estimates are late 16.3% vs 4.2%", [100 * q2s["late rate, short"], 100 * q2s["late rate, longer, same state and month"]], 0),
    ("nb", "RJ's rate (11.5%)", [100 * st.late_rate["RJ"]], 0),
    ("nb", "about 98 more late deliveries", [st.excess_late["RJ"]], 0),
    ("nb", "1-2 would sit outside the overall rate by chance, 12 do", [1, 27 * 0.05, outside], 0.4),
    ("nb", "951 labelled orders (6%) have no state, 741 of them", [lab.customer_state.isna().sum(), 100 * lab.customer_state.isna().mean(),
                                                               (lab.customer_state.isna() & ~lab.has_customer.astype(bool)).sum()], 0),
    ("nb", "every variant gives 6.4-6.8%", [100 * sens.late_rate.min(), 100 * sens.late_rate.max()], 0),
    ("nb", "18% of orders have no label", [100 * (1 - len(lab) / len(o))], 0),
    ("nb", "the 944 cancelled ones could move the late rate anywhere from 6.4% (none would have been late) to 11.8%", [c, 100 * k / (nl + c), 100 * (k + c) / (nl + c)], 0),
    ("nb", "743 of them were already with the carrier", [canc.order_delivered_carrier_date.notna().sum()], 0),
    # step 4
    ("nb", "rows: the 16,482 labelled orders", [len(feats)], 0),
    ("nb", "customer state one hot (27 + missing)", [len([x for x in feats.columns if x.startswith("state_") and x != "state_missing"])], 0),
    ("nb", "top 15 + other + missing", [len([x for x in feats.columns if x.startswith("cat_") and x not in ("cat_other", "cat_missing")])], 0),
    ("nb", "a test auc of 0.61 is modest", [model["all features"]], 0),
    ("nb", "above lead time alone (0.53), and far below the leak control (1.0)", [model["lead_days only"], model["all features + days_late (leak control)"]], 0),
    ("nb", "the test months (apr-aug 2018, 4.5% late)", [2018, 100 * test.delivered_after_estimate.mean()], 0),
    # step 5
    ("nb", "step 0 was the big miss: 33-52 MB estimated, about 205 MB measured", [0, *map(float, res("00_setup_db")["estimate_peak_MB"].split("-")), res("00_setup_db")["rss_peak_MB"]], 0.1),
    ("nb", "the whole 18 million character text at 4 bytes per character (73 MB)", [len(raw.read_text("utf-8")) / 1e6, 4, sys.getsizeof(raw.read_text("utf-8")) / 1e6], 0.05),
    ("nb", "reading `raw.sql` as bytes peaks at 33 MB, decoding it at 123 MB, reading it as text like `setup_db.py` does at 196 MB",
     [peak(f"b=open('{raw}','rb').read()"), peak(f"s=open('{raw}','rb').read().decode('utf-8')"), peak(f"s=open('{raw}',encoding='utf-8').read()")], 0.15),
    ("nb", "every notebook step stays under 100 MB above start and under 2 seconds", rs.rss_peak_above_start_MB.max() < 100 and rs.seconds.drop("00_setup_db").max() < 2, 0),

    # report.md
    ("r", "0 orphan items/payments/reviews", [links[["items without an order", "payments without an order", "reviews without an order"]].max()], 0),
    ("r", "769 orders with no customer row, 142 with no items, 910 items with no product row, 893 with no seller row", [links["orders without a customer row"], links["orders with no items"],
     links["items without a product row"], links["items without a seller row"]], 0),
    ("r", "0 duplicate orders, 0 shared customer records. 998 repeated item rows", [links["duplicate orders (same customer, time, status)"], links["customer_id on 2+ orders"],
     links["repeated item rows (same order, product, seller, price)"]], 0),
    ("r", "price 54,446,205.77, payments 280,524,473 centavos, 19,966 reviews, 22,662 items", [checks["price BRL"], checks["payment centavos"], checks["reviews"], checks["items"]], 0),
    ("r", "sqlite sql via adbc 120 MB / 1.86 s", [mbx["sqlite sql (adbc)"], b.seconds["sqlite sql (adbc)"]], 0.2),
    ("r", "sqlite3 driver 421 MB / 3.97 s", [3, mbx["sqlite sql (python sqlite3 driver)"], b.seconds["sqlite sql (python sqlite3 driver)"]], 0.2),
    ("r", "pandas 405 MB / 0.68 s", [mbx["pandas (adbc reads whole tables)"], b.seconds["pandas (adbc reads whole tables)"]], 0.2),
    ("r", "duckdb on parquet 470 MB / 0.12 s, 1 thread 314 MB / 0.22 s, result written to a file 482 MB / 0.15 s", [mbx["duckdb sql on parquet"], b.seconds["duckdb sql on parquet"], 1,
     mbx["duckdb sql on parquet, 1 thread"], b.seconds["duckdb sql on parquet, 1 thread"], mbx["duckdb sql on parquet, streamed to a file"], b.seconds["duckdb sql on parquet, streamed to a file"]], 0.2),
    ("r", "duckdb on the sqlite file 457 MB / 0.25 s", [mbx["duckdb sql on sqlite"], b.seconds["duckdb sql on sqlite"]], 0.2),
    ("r", "(20 MB of objects vs 7 MB as a dataframe for 20,000 rows)", [objects_mb(), res("01_load")["in_memory_MB"]["orders"], n("orders")], 0.15),
    ("r", "duckdb: 6-16x faster at 10x, but 310-480 MB", [b.seconds["pandas (adbc reads whole tables)"] / b.seconds["duckdb sql on parquet"],
     b.seconds["sqlite sql (adbc)"] / b.seconds["duckdb sql on parquet"], 10, mbx.filter(like="duckdb").min(), mbx.filter(like="duckdb").max()], 0.2),
    ("r", "parquet 3.29 MB vs csv 5.25 MB", [res("01_load")["saved_MB"]["orders.parquet"], len(pd.read_parquet(D / "01_load/orders.parquet").to_csv(index=False).encode()) / 1e6], 0),
    ("r", "16,482 labelled + 944 cancelled/unavailable + 804 status unknown + 791 delivered before purchase/approval + 333 delivery date missing/impossible + 322 not delivered yet + 319 estimate missing/impossible + 5 delivered with no items = 20,000",
     [*acc.values, acc.sum()], 0),
    ("r", "price<0 abs 87.2%, price>5000 /1000 93.5%, /100 0%. freight 90.3% / 88.4%. clean orders 90.0%", [0, 100 * ev["abs"]["price < 0"], 5000, 1000, 100 * ev["/1000"]["price > 5000"], 100, 100 * ev["/100"].max(),
     100 * ev["abs"]["freight < 0"], 100 * ev["/1000"]["freight > 500"], 100 * ev.none["clean orders (reference)"]], 0),
    ("r", "fixed price = its usual price for 163/255 negatives, 178/277 big ones", usual_claims, 0),
    ("r", "ships for R$15.2 like 0.4-1.4 kg items R$16.1, real 20-30 kg R$74.6", [*fr_claims], 0),
    ("r", "recovered from zip prefix (895 customer, 1,032 seller), 14 conflicting prefixes", [summ["customer_state", "missing state -> from zip prefix"], summ["seller_state", "missing state -> from zip prefix"], zip_conflicts], 0),
    ("r", "7.23 extra on 832 orders", [7.23, recon["  paid exactly 7.23 more"]], 0),
    ("r", "installments: 929 at -1 left (payments arent predictors), 1 at 0", [*map(int, prof["payment installments -1 / 0"].split(" / ")[:1]), 1, *map(int, prof["payment installments -1 / 0"].split(" / ")[1:]), 0], 0),
    ("r", "payments reconcile 14,845 -> 16,302 of 18,122 complete orders. remaining 1,820: 919 negative payment, 832 the 7.23", [recon["match before cleaning"], recon["match after cleaning"], recon["complete orders"],
     recon["still not matching"], recon["  with a negative payment"], recon["  paid exactly 7.23 more"], 7.23], 0),
    ("r", "270 carrier before approval (flag), 804 not_reported + 782 of the 791 early deliveries are exactly 7 days (tested in step 3)", [int(prof["carrier pickup before approval"]), int(prof["status not_reported"]), shift, len(r), 7, 3], 0),
    ("r", "extreme delays up to 188 days kept, 14 orders over 60 days", [lab.days_late.max(), (lab.days_late > 60).sum(), 60], 0),
    ("r", "q1: 6.7% late (6.3-7.1%). median 7 days late (IQR 3-13), 1 in 8 is 3+ weeks. on-time orders median 13 days early. waves: mar 2018 18.3%, feb 2018 14.1%, nov 2017 12.0%",
     [1, 100 * rate, *[100 * float(x) for x in sens.ci["baseline"].split("-")], late.median(), late.quantile(.25), late.quantile(.75), 1, 1 / (late >= 21).mean(), 3, early,
      2018, 100 * months["2018-03"], 2018, 100 * months["2018-02"], 2017, 100 * months["2017-11"]], 0.03),
    ("r", "q2: <1 week 16.3% late, 1-5 weeks 5-7%, 6+ weeks 1.7%", [2, 1, 100 * q2.late_rate["<1 week"], 1, 5, 100 * q2.late_rate[["1-2", "2-3", "3-4", "4-5"]].min(),
     100 * q2.late_rate[["1-2", "2-3", "3-4", "4-5"]].max(), 6, 100 * q2.late_rate["6+ weeks"]], 0),
    ("r", "0 short estimates in spike months, same state + month 16.3% vs 4.2%", [q2s["short estimates in the 3 spike months"], 100 * q2s["late rate, short"], 100 * q2s["late rate, longer, same state and month"]], 0),
    ("r", "RJ +98, BA +26, CE +22. RJ: 65 of it in spike months, 94 on SP sellers", [st.excess_late["RJ"], st.excess_late["BA"], st.excess_late["CE"], drill["RJ", "spike months"], drill["RJ", "seller in SP"]], 0),
    ("r", "BA: 25 outside spikes", [drill["BA", "other months"]], 0),
    ("r", "RR (9 orders) and AP (8)", [st.orders["RR"], st.orders["AP"]], 0),
    ("r", "27 states -> 1-2 outside by chance, 12 are", [len(st), 1, 27 * 0.05, outside], 0.4),
    ("r", "951 labelled orders (6%) have no state, 741 with no customer row", [lab.customer_state.isna().sum(), 100 * lab.customer_state.isna().mean(),
     (lab.customer_state.isna() & ~lab.has_customer.astype(bool)).sum()], 0),
    ("r", "sensitivity: late rate 6.41-6.79%", [100 * sens.late_rate.min(), 100 * sens.late_rate.max()], 0),
    ("r", "top 3 always RJ BA CE", (sens.top3_states == "RJ BA CE").all(), 0),
    ("r", "bounds: 944 cancelled -> 6.4% to 11.8%. 743 already with carrier -> 6.7%", [c, 100 * k / (nl + c), 100 * (k + c) / (nl + c), canc.order_delivered_carrier_date.notna().sum(), 100 * rate], 0),
    ("r", "16,482 rows, 72 float columns", [len(feats), feats.shape[1]], 0),
    ("r", "no pair above 0.78 left", [corr_max], 0),
    ("r", "single feature auc 0.43-0.61, days_late control 1.0", [leak.drop(leak.index[0]).min(), leak.drop(leak.index[0]).max(), leak.iloc[0]], 0),
    ("r", "lead_days only 0.534, all features 0.611, + days_late 1.000", [model["lead_days only"], model["all features"], model["all features + days_late (leak control)"]], 0),
    ("r", "load 77 / 26-39 / 0.2, clean 68 / 35-53 / 0.6, eda 65 / 43-64 / 1.7, features 60 / 48-72 / 0.3", [x for st_ in ["01_load", "02_clean", "03_eda", "04_features"]
     for x in [rs.rss_peak_above_start_MB[st_], *map(float, rs.estimate_MB[st_].split("-")), rs.seconds[st_]]], 0.25),
    ("r", "estimate 33-52 MB, measured ~205 MB peak", [*map(float, res("00_setup_db")["estimate_peak_MB"].split("-")), res("00_setup_db")["rss_peak_MB"]], 0.1),
    ("r", "under 3 s", res("00_setup_db")["seconds"] < 3, 0),
    ("r", "storage: db 24.4 MB, saved outputs ~13 MB, temporary ~300 MB", [res("00_setup_db")["saved_MB"]["marketplace.sqlite"], rs.saved_MB.drop("00_setup_db").sum(), rs.temporary_MB.max()], 0.05),
    ("r", "kernel peak 565 MB", [json.loads((D / "05_resources/environment.json").read_text())["kernel_peak_rss_MB"]], 0.1),
    # found by sweeping every sentence with a number in it
    ("nb", "about 1 in 15 labelled orders arrives late", [1, 1 / rate], 0.03),
    ("nb", "estimates under a week are late 16% of the time, twice any other group", q2.late_rate["<1 week"] >= 2 * q2.late_rate.drop("<1 week").max(), 0),
    ("nb", "but on 2,000+ orders", st.orders["RJ"] >= 2000, 0),
    ("nb", "RR and AP look extreme but rest on under 10 orders", max(st.orders["RR"], st.orders["AP"]) < 10, 0),
    ("nb", "one modified extract from 2016-2018", [o.order_purchase_timestamp.dt.year.min(), o.order_purchase_timestamp.dt.year.max()], 0),
    ("nb", "labels the 780 of the 804 status-unknown orders", [sens.orders["+ not_reported"] - sens.orders["baseline"], acc["status unknown"]], 0),
    ("nb", "moves the deliveries dated exactly 7 days before approval forward 7 days", sens.orders["+ 7 day shift undone"] - sens.orders["baseline"] == shift, 0),
    ("nb", "steps 1 and 2 went over it, using 4-6x their data", [1, 2, *sorted(rs.rss_peak_above_start_MB[s_] / rs.data_MB[s_] for s_ in ["01_load", "02_clean"])], 0.15),
    ("nb", "steps 3 and 4 land inside or right at their estimates", all(rs.rss_peak_above_start_MB[s_] <= 1.1 * float(rs.estimate_MB[s_].split("-")[1]) for s_ in ["03_eda", "04_features"]), 0),
    ("nb", "step 0: python (~15 MB)", [0, peak("pass")], 0.2),
    ("r", "- 8 tables", [len(db.execute("select name from sqlite_master where type='table'").fetchall())], 0),
    ("r", "python 3.12.12, pandas 3.0.6, pyarrow 26, duckdb 1.5.6, sklearn 1.9.1, macOS arm64, 14 cpu, 38.7 GB", [float(x.replace(",", "")) for x in re.findall(r"\d[\d,]*(?:\.\d+)?",
     "python {python}, pandas {pandas}, pyarrow {pa}, duckdb {duckdb}, sklearn {sk}, macOS arm64, {cpu_count} cpu, {ram_GB} GB".format(pa=env["pyarrow"].split(".")[0], sk=env["scikit-learn"], **env))], 0),
    ("nb", "saved storage lands inside the estimate for steps 0-3 and every step meets its runtime estimate", all(float(rs.estimate_saved_MB[s_].split("-")[0]) <= rs.saved_MB[s_] <= float(rs.estimate_saved_MB[s_].split("-")[1])
     for s_ in ["00_setup_db", "01_load", "02_clean"]) and rs.saved_MB["03_eda"] < 1 and (rs.seconds < [5, 1, 1, 3, 1]).all(), 0),
    ("nb", "step 4 saved 1.2 MB against 3.2-5.3", [4, rs.saved_MB["04_features"], *map(float, rs.estimate_saved_MB["04_features"].split("-"))], 0),
    ("r", "inside for steps 0-3, step 4 saved 1.2 MB vs 3.2-5.3", [0, 3, 4, rs.saved_MB["04_features"], *map(float, rs.estimate_saved_MB["04_features"].split("-"))], 0),
]

def numbers(text):
    return [float(x.replace(",", "")) for x in re.findall(r"\d[\d,]*(?:\.\d+)?", text)]

def ok(written, actual, rtol):
    d = len(written.split(".")[1]) if "." in written else 0
    a, w = float(actual), float(written.replace(",", ""))
    return round(a, d) == w or abs(a - w) <= rtol * abs(w)

fails = 0
for where, text, values, rtol in C:
    doc = NB if where == "nb" else REPORT
    found = re.findall(r"\d[\d,]*(?:\.\d+)?", text)
    if isinstance(values, (bool, np.bool_)):
        problem = "text not found" if text not in doc else "" if values else "condition is false"
    else:
        problem = "text not found" if text not in doc else f"{len(found)} numbers written, {len(values)} computed" if len(found) != len(values) else \
            ", ".join(f"wrote {w}, data says {float(v):.4g}" for w, v in zip(found, values) if not ok(w, v, rtol))
    if problem:
        fails += 1
        print(f"FAIL [{where}] {text!r}: {problem}")
print(f"{len(C) - fails} of {len(C)} claims match the outputs")
sys.exit(fails > 0)
