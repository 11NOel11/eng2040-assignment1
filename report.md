# ENG2040 assignment 1 - late delivery pipeline

draft. bullets get turned into prose once step 4 and 5 are done. target 6-8 pages.

## 1. loading (~1.5 pages)

- one row per order, 20000 orders. items, payments, reviews aggregated per order in sql, then joined with left joins so no order is lost
- checks: totals in the db equal totals after loading (price 54,446,205.77, payments 280,524,473 centavos, 19,966 reviews). 0 orphan items/payments/reviews
- key gaps found, kept not dropped: 769 orders with no customer, 142 with no items, 910 items with no product, 893 with no seller
- read through adbc. sqlite3 driver vs adbc, 1x/3x/10x copies, 3 reps, baseline subtracted. at 10x sql 120 MB vs pandas 419 MB above baseline, pandas faster (0.71 s vs 1.76 s). chose sql + adbc, memory over speed
- the estimate that sql scales better was wrong with the sqlite3 driver. the driver was the cost, not the sql
- parquet 3.29 MB vs csv 5.25 MB. supplied files checked by sha256

## 2. cleaning (~1.5 pages)

- no order deleted. 16,482 labelled, 3,518 with an unlabelled_reason (table from record_accounting.csv)
- rule: fix only with a witness, else set missing, else flag
- prices: negative -> abs (87.2% then match payments), > 5000 -> /1000 (93.5%). /100 matches 0%. clean orders match payments 89.9%, so the fixes recover close to the normal rate
- second witness: same product sold in other orders at a normal price. fixed price equals that products median for 163 of 255 negatives and 178 of 277 huge ones
- states ZZ/blank recovered from zip prefix (895 customer, 1032 seller), 14 conflicting prefixes skipped
- set missing: invalid date 2018-02-30, unmapped_category, sizes <= 0
- product sizes/weights 1000x (all multiples of 1000 above a gap). witness is freight: 'over 100 kg' items ship for R$15.2, same as 0.4-1.4 kg items (R$16.1), real 20-30 kg items R$74.6. so raw values are wrong, but freight cant confirm the exact value -> missing, not /1000
- photos / name / description length = -1 is a placeholder -> missing
- unresolved: 7.23 extra on ~830 orders, 270 carrier pickups before approval, negative payments

## 3. eda (~2 pages)

- q1: 6.7% late (6.3-7.1%). median 7 days late, typical order 12 days early. bunched in time: mar 2018 18.3%, feb 2018 14.1%, nov 2017 12.0%
- q2: <7 day estimates 16.3% late, 42+ days 1.7%. tested the confound: none of the short estimates are in spike months, and inside the same state + month short 16.3% vs longer 4.2%. still association only
- q3: ranked by excess late orders. RJ, BA, CE. RR/AP too small to trust
- sensitivity: late rate 6.41-6.79% across variants, top 3 states unchanged
- bounds for the 944 cancelled: 6.4% (none late) to 11.8% (all late). 743 of them were already with the carrier, so 6.7% is a lower end
- figures: q1, q2, q3 pngs from data/03_eda

## 4. features (~1 page)

- 16,482 rows (labelled orders), 75 numeric columns. ids + labels in a separate file, same row order
- forbidden columns dropped before any feature is built, so a mistake fails loudly
- timing: lead_days, est_days_from_purchase, approval_hours, month/weekday/hour as sin+cos. no year
- basket: n_items, n_products, n_sellers, price_sum, freight_sum, freight_share
- product/seller: weight, volume, photos, n_categories, n_seller_states, share_items_same_state
- one hot: customer state (27 + missing), category of most expensive item (top 15 + other + missing)
- missing kept as NaN + _missing flag. imputation left to model fitting so test orders dont leak into fill values
- leakage check: single feature auc, all within 0.39-0.61. control days_late gives 1.0, so the check can catch a leak
- strongest single signals: purchase month (0.61), customer in SP (0.43), seller in same state (0.44)

## 5. reproducibility and resources (~0.5-1 page)

- one command `uv run python run.py`: checksum supplied files, rebuild db, run notebook, hash every output
- two fresh runs -> identical manifest.sha256 (byte for byte)
- per step (resources_summary.csv): step 1 85 MB above start (est 26-39), step 2 96 (36-53), step 3 48, step 4 58 (49-73). all < 0.5 s
- estimate rule (2-3x data size) too low for db-reading steps, 4-6x fits better. likely arrow buffers + allocator, not measured separately
- storage: db 24.4 MB, saved outputs ~13 MB, temporary 240 MB (10x scaling copy, deleted)
- environment.json: python 3.12.12, pandas 3.0.6, pyarrow 26, macOS arm64, 14 cpu, 38.7 GB
