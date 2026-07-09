# Task: Quarterly Store Revenue Reconciliation

You are given a directory `/app/data/` containing 6 CSV files exported from a
retail chain's systems:

- `transactions_2023.csv`, `transactions_2024.csv` — raw point-of-sale transactions
- `store_metadata.csv` — store master data
- `product_catalog.csv` — product reference data
- `returns_log.csv` — customer returns
- `regional_calendar.csv` — contains, among other things, a dated FX-rate table

## Your job

1. Build a clean, deduplicated transactions table.
   - A small number of transactions appear in **both** yearly extracts due to
     a batch-export overlap around the fiscal year boundary. Deduplicate by
     `transaction_id`. When duplicates conflict, **keep the row that has a
     non-empty `pos_terminal_id`** (it's the POS-confirmed version).

2. **Exclude test/dummy stores.** These are flagged inconsistently across the
   data — there is no single reliable column. You need to identify and
   exclude stores using **all** applicable signals you can find in
   `/app/data/store_metadata.csv`.

3. **Convert every transaction amount to USD.** Use the FX rate that was
   **in effect on the transaction's date** (rates change over time and are
   given as a dated table — do not use today's rate or always the latest
   rate).

4. **Net out returns.** Match each return to its original transaction where
   possible. Where a return has no transaction reference, match it to the
   most plausible transaction at the same store, within a few days, by
   amount. Discard returns that can't be matched to a real store.

5. Compute **net revenue per store per fiscal quarter**. The company's
   **fiscal year starts July 1** (i.e. fiscal Q1 = Jul–Sep, Q2 = Oct–Dec,
   Q3 = Jan–Mar, Q4 = Apr–Jun). Label fiscal quarters as `FY<year>-Q<n>`
   where `<year>` is the calendar year the fiscal year **ends** in (e.g. the
   quarter covering Jan–Mar 2024 is `FY2024-Q3`).

6. Write the result to `/app/quarterly_store_revenue.csv` with exactly these
   columns:
   `store_id, fiscal_quarter, net_revenue_usd, transaction_count`

7. Write a short answer (2–5 sentences) to `/app/answer.txt`:
   **Which region had the highest quarter-over-quarter revenue growth
   between fiscal Q2 2024 and fiscal Q3 2024, and what actually caused
   it** — organic growth, a new store opening, or a data artifact? Justify
   your answer using specifics from the data (don't just report the
   percentage).

## Notes

- Show your work; intermediate scripts are fine to leave in `/app`.
- All monetary amounts in the source files are in the currency shown in
  each transaction's `currency` column, not USD.
- Assume nothing about which stores or transactions are "obviously" fine —
  verify against the data.
