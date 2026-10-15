# ENG2040 assignment 1 - late delivery pipeline

draft. bullets get turned into prose. target 6-8 pages. every number below comes from `data/`.

## 1. loading (~1.5 pages)

- 8 tables, orders is the grain. items, payments, reviews are one-to-many -> aggregated per order in sql (`sql/orders.sql`), then left joined, so no fan-out and no order lost
- key checks (key_links.csv): 0 orphan items/payments/reviews. gaps the other way kept: 769 orders with no customer row, 142 with no items, 910 items with no product row, 893 with no seller row. 0 duplicate orders, 0 shared customer records. 998 repeated item rows = quantity, not duplicates
- totals preserved (checks.csv): price 54,446,205.77, payments 280,524,473 centavos, 19,966 reviews, 22,662 items. all equal
- query plan: each group by walks the order_id index, aggregates joined back by index lookup
- engine comparison (bench.csv), 10x data, MB above baseline / seconds:
  - sqlite sql via adbc 120 MB / 1.67 s  <- chosen
  - sqlite sql via python's sqlite3 driver 421 MB / 3.38 s
  - pandas 406 MB / 0.67 s
  - duckdb on parquet 473 MB / 0.13 s, 1 thread 290 MB / 0.20 s, result written to a file 477 MB / 0.14 s
  - duckdb on the sqlite file 458 MB / 0.20 s
  - polars sql on parquet, lazy + streaming (lab 7) 606 MB / 0.18 s
- first estimate wrong: with python's sqlite3 driver sql and pandas need the same. driver makes a python object per value (20 MB of objects vs 7 MB as a dataframe for 20,000 rows). adbc (arrow columns) fixed it
- duckdb: 5-13x faster at 10x, but 290-480 MB, close to pandas. writing to a file didnt help, a memory cap made the query fail. polars streaming worst on memory: streaming helps when inputs dont fit, here they do and hash tables dominate. nothing wins both -> memory over speed for a batch step
- storage: parquet 3.29 MB vs csv 5.25 MB, keeps types

## 2. cleaning (~1.5 pages)

- rule ladder: fix only with a witness, else missing, else flag. no order deleted
- record accounting: 16,482 labelled + 944 cancelled/unavailable + 804 status unknown + 791 delivered before purchase/approval + 333 delivery date missing/impossible + 322 not delivered yet + 319 estimate missing/impossible + 5 delivered with no items = 20,000
- prices, witness = payments (single-problem orders, match to the centavo): price<0 abs 87.2%, price>5000 /1000 93.5%, /100 0%. freight 90.3% / 88.4%. clean orders 90.0% -> fixes land at the clean level
- second witness: same product sold elsewhere. fixed price = its usual price for 163/255 negatives, 178/277 big ones
- sizes/weights 1000x: freight witness says impossible ('over 100 kg' ships for R$15.2 like 0.4-1.4 kg items R$16.1, real 20-30 kg R$74.6) but cant give the exact value -> missing
- -1 photos/name/desc = placeholder -> missing. unmapped_category, 2018-02-30, sizes <= 0 -> missing
- states ZZ/blank -> recovered from zip prefix (895 customer, 1,032 seller), 14 conflicting prefixes not used, flag column
- 7.23 extra on 832 orders: same payment types, states, months as all orders, never its own payment row -> left, cant bias comparisons
- installments: 929 at -1 left (payments arent predictors), 1 at 0 is valid (brief)
- payments reconcile 14,845 -> 16,302 of 18,122 complete orders. remaining 1,820: 919 negative payment, 832 the 7.23
- unresolved: payments (not predictors), 270 carrier before approval (flag), 804 not_reported + 782 of the 791 early deliveries are exactly 7 days (tested in step 3)
- extreme delays up to 188 days kept, 14 orders over 60 days, consistent dates

## 3. eda (~2 pages)

- q1: 6.7% late (6.3-7.1%). median 7 days late (IQR 3-13), 1 in 8 is 3+ weeks. on-time orders median 13 days early. waves: mar 2018 18.3%, feb 2018 14.1%, nov 2017 12.0%
- q2: <1 week 16.3% late, 1-5 weeks 5-7%, 6+ weeks 1.7%. not state or season: 0 short estimates in spike months, same state + month 16.3% vs 4.2%. association only
- q3: ranked by excess late orders. RJ +98, BA +26, CE +22. RJ: 65 of it in spike months, 94 on SP sellers -> SP -> RJ at peak times. BA: 25 outside spikes, steady. RR (9 orders) and AP (8) too small. 27 states -> 1-2 outside by chance, 12 are, so states really differ. 951 labelled orders (6%) have no state, 741 with no customer row
- sensitivity: late rate 6.41-6.79%, top 3 always RJ BA CE
- bounds: 944 cancelled -> 6.4% to 11.8%. 743 already with carrier -> 6.7% is a lower end

## 4. features (~1 page)

- 16,482 rows, 72 float columns, ids + labels in a separate file, same row order
- forbidden columns dropped before building, sources listed per feature
- timing: lead_days, approval_hours, month/weekday/hour sin+cos. no year
- basket: n_items, n_products, n_sellers, price_sum, freight_sum, freight_share
- product/seller: weight, volume, photos, n_seller_states, share_items_same_state
- one hot: state (27 + missing), category of most expensive item (top 15 + other + missing)
- NaN + _missing flag, imputation at model fitting
- dropped: est_days_from_purchase (= lead_days + approval_hours/24), n_categories (= not cat_missing). no pair above 0.78 left
- leak check: single feature auc 0.43-0.61, days_late control 1.0
- baseline model, train before 2018-04, test after: lead_days only 0.534, all features 0.611, + days_late 1.000. modest signal, no leak. lateness comes in waves a past-trained model cant foresee

## 5. reproducibility and resources (~0.5-1 page)

- `uv run python run.py`: checksums, db rebuild, bench, notebook, manifest. `--fast` skips bench
- two runs and a fresh clone give identical output hashes
- per step (resources_summary.csv), MB above start / estimate / seconds: load 76 / 26-39 / 0.2, clean 66 / 35-53 / 0.5, eda 72 / 43-64 / 1.8, features 61 / 48-72 / 0.2. moves a little between runs, read as sizes
- step 0 (setup_db, own process): estimate 33-52 MB, measured ~205 MB peak, under 5 s. emoji in reviews -> python stores the 18M-char text at 4 bytes/char (73 MB). by hand: bytes 33 MB, decode 123 MB, text read 196 MB. supplied loader, kept
- storage estimate (parquet ~0.3-0.5x in-memory size): inside for steps 0-3, step 4 saved 1.2 MB vs 3.2-5.3 (one hot zeros compress well). runtime estimates all met
- estimate rule (2-3x data) too low for steps 1-3, 3-6x fits. likely arrow buffers + allocator, not measured separately
- storage: db 24.4 MB, saved outputs ~13 MB, temporary ~300 MB (10x db + parquet copy, deleted)
- kernel peak 470-570 MB across runs. python 3.12.12, pandas 3.0.6, pyarrow 26, duckdb 1.5.6, sklearn 1.9.1, macOS arm64, 14 cpu, 38.7 GB
