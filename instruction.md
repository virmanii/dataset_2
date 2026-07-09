# Multi-Warehouse Inventory Reconciliation & Replenishment Planning

You work with inventory data for a retail operator running five warehouses. You are given
three CSV files describing the warehouses, the products (SKUs) they stock, and a raw
transaction log pulled directly from the warehouse management system. The transaction log
is a real export: it was not cleaned before being handed to you.

Your job is to reconstruct accurate current stock levels from the transaction log and
produce a replenishment plan.

## Input files

- `/app/data/warehouses.csv` — `warehouse_id, name, region, storage_capacity_units`
- `/app/data/skus.csv` — `sku_id, category, unit_cost, avg_daily_demand, lead_time_days, safety_stock_days, moq`
- `/app/data/transactions.csv` — `transaction_id, timestamp, warehouse_id, sku_id, type, quantity, reference_transaction_id`

Not every row in the master files describes a real production entity. Some are internal
sandbox/test records that were never cleaned out of the export and must not appear in the
replenishment plan or count toward any warehouse's capacity. There is no single reliable
flag for this — different fake rows give themselves away through different combinations of
signals (an implausible cost/demand/MOQ profile, a suspicious name or category, an outlier
capacity). Inspect the master files yourself and use your judgment.

`type` is one of `RECEIPT`, `SALE`, `RETURN`, `ADJUSTMENT`, or `CANCEL`. `timestamp` values
are ISO 8601 and carry an explicit UTC offset (they are not all in the same timezone —
don't assume the raw string ordering reflects the true chronological order of events).
`reference_transaction_id` is only populated for `CANCEL` rows.

## What the transaction types mean

- `RECEIPT` — stock arriving at a warehouse. Quantity is the number of units received.
- `SALE` — stock leaving a warehouse. Quantity is the number of units sold.
- `RETURN` — stock coming back into a warehouse. Quantity is the number of units returned.
- `ADJUSTMENT` — the result of a physical stock count / audit. Unlike the other types, its
  quantity is not a movement — it is a statement of the true on-hand quantity at that
  warehouse for that SKU at that moment in time, superseding everything that happened
  before it.
- `CANCEL` — voids another transaction, identified by `reference_transaction_id`, as if it
  had never happened. Only `RECEIPT`, `SALE`, and `RETURN` transactions are cancellable —
  the system has no concept of canceling a stock count.

`transaction_id` uniquely identifies a real-world transaction. `RECEIPT` and `SALE`
quantities represent physical unit movements and are always non-negative in a valid
record. A transaction is only meaningful if it refers to a `warehouse_id` and `sku_id`
that actually exist in the master files above. You should treat the log as untrusted and
use your judgment about what constitutes a usable record.

## Reconciling current stock

For every `(warehouse_id, sku_id)` combination among the real production warehouses and
SKUs, determine the current on-hand stock as of the end of the
log. Stock is not artificially floored at zero — a warehouse can be legitimately
oversold and show a negative current stock.

## Replenishment logic

For each `(warehouse_id, sku_id)` pair:

- `reorder_point = ceil(avg_daily_demand * (lead_time_days + safety_stock_days))`
- If `current_stock < reorder_point`, the pair needs an order. The raw quantity needed is
  `reorder_point - current_stock`, which must be rounded **up** to the nearest multiple of
  that SKU's `moq` to get the recommended order quantity. Partial-MOQ orders are never
  placed. If `current_stock >= reorder_point`, the recommended order quantity is `0`.

## Warehouse capacity constraint

Each warehouse has a fixed `storage_capacity_units`. Within a single warehouse, the sum of
(current stock, floored at zero for this check only) across all its SKUs plus the sum of
all recommended order quantities must not exceed `storage_capacity_units`.

If it would be exceeded, orders must be cut back on a per-warehouse basis until the
warehouse fits within capacity, prioritizing the most urgent SKUs first — urgency is
`current_stock / reorder_point`, ascending (lower ratio = more urgent), with ties broken
by `sku_id` in ascending alphabetical order. Go down the priority list adding each SKU's
full recommended order; the first SKU whose order would push the warehouse over capacity,
and every SKU after it in priority order, gets its recommended order quantity reduced to
`0` instead — never a partial amount below the MOQ-rounded figure.

## Output

Write `/app/output/replenishment_plan.csv` with exactly these columns, in this order:

`warehouse_id, sku_id, current_stock, reorder_point, recommended_order_qty`

- One row per real `(warehouse_id, sku_id)` pair — production warehouses and SKUs only,
  per the exclusion requirement above.
- Sorted by `warehouse_id` ascending, then `sku_id` ascending.
- `current_stock` and `reorder_point` are integers (round `reorder_point` up as specified
  above; `current_stock` is naturally an integer). `recommended_order_qty` is an integer.

## Data quality write-up

Separately from the cleaning rules above, inspect the transaction log for evidence of a
system-level data quality issue — a specific `(warehouse_id, sku_id)` pair whose recorded
transaction history shows a pattern that isn't organic activity. This is not one of the
cleaning cases already described (it isn't a duplicate `transaction_id`, an invalid
reference, or a sign error — every transaction in this cluster is individually valid and
should still count toward `current_stock` in your output as normal).

Write 2–4 sentences to `/app/anomaly_report.txt` identifying which warehouse and SKU are
affected, roughly how many transactions are involved and on what date, and what you
believe caused the pattern. Justify your answer with the specific evidence you found —
don't just assert a conclusion.
