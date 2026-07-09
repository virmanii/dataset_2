"""
GOLDEN SOLUTION for the "Silent Merge" task.
Reads the raw CSVs in environment/data/, produces quarterly_store_revenue.csv
and prints the answer to the growth-driver question.
This file encodes every correct decision the task is designed to test.
"""
import pandas as pd
import numpy as np
import sys
import os

DATA_DIR = sys.argv[1] if len(sys.argv) > 1 else "environment/data"
OUT_PATH = sys.argv[2] if len(sys.argv) > 2 else "quarterly_store_revenue.csv"

stores = pd.read_csv(f"{DATA_DIR}/store_metadata.csv")
tx23 = pd.read_csv(f"{DATA_DIR}/transactions_2023.csv", dtype={"pos_terminal_id": str})
tx24 = pd.read_csv(f"{DATA_DIR}/transactions_2024.csv", dtype={"pos_terminal_id": str})
returns = pd.read_csv(f"{DATA_DIR}/returns_log.csv")
fx = pd.read_csv(f"{DATA_DIR}/regional_calendar.csv")

tx = pd.concat([tx23, tx24], ignore_index=True)
tx["date"] = pd.to_datetime(tx["date"])
tx["pos_terminal_id"] = tx["pos_terminal_id"].fillna("").astype(str).str.strip()

# ---------------------------------------------------------------------
# 1. Dedup transactions that appear in both yearly extracts.
# Rule: same transaction_id -> keep the row with a non-null/non-empty
# pos_terminal_id (prefer the "real" POS-confirmed row).
# ---------------------------------------------------------------------
tx["has_pos"] = tx["pos_terminal_id"] != ""
tx = tx.sort_values("has_pos", ascending=False).drop_duplicates(subset="transaction_id", keep="first")
tx = tx.drop(columns="has_pos")

# ---------------------------------------------------------------------
# 2. Exclude test/dummy stores -- union of THREE independent signals.
# ---------------------------------------------------------------------
is_test = (
    (stores["store_type"] == "TEST")
    | (stores["store_name"].str.contains("DEMO", case=False, na=False))
    | (stores["store_id"].between(9000, 9099))
)
test_store_ids = set(stores.loc[is_test, "store_id"])
real_stores = stores.loc[~is_test].copy()

tx = tx[~tx["store_id"].isin(test_store_ids)].copy()
returns = returns[~returns["store_id"].isin(test_store_ids)].copy()

# ---------------------------------------------------------------------
# 3. Currency conversion to USD using the rate IN EFFECT on the
# transaction date (as-of / backward merge per currency), not the
# latest rate and not a nearest-date rate.
# ---------------------------------------------------------------------
fx["date"] = pd.to_datetime(fx["date"])
fx = fx.dropna(subset=["currency"])
fx = fx.sort_values("date")

def convert_to_usd(df):
    out_parts = []
    for cur, grp in df.groupby("currency"):
        if cur == "USD":
            grp = grp.copy()
            grp["usd_exchange_rate"] = 1.0
        else:
            rate_tbl = fx[fx["currency"] == cur][["date", "usd_exchange_rate"]].sort_values("date")
            grp = pd.merge_asof(
                grp.sort_values("date"), rate_tbl, on="date", direction="backward"
            )
        out_parts.append(grp)
    return pd.concat(out_parts, ignore_index=True)

tx = convert_to_usd(tx)
tx["amount_usd"] = tx["amount"] * tx["usd_exchange_rate"]

# ---------------------------------------------------------------------
# 4. Match returns: exact by transaction_id first; unmatched returns
# are fuzzy-matched to a transaction at the SAME store, within 3 days,
# with the closest amount (must be within $1 tolerance to count as a
# plausible match). Returns whose store_id doesn't exist in tx are
# dropped (no crash).
# ---------------------------------------------------------------------
returns["date"] = pd.to_datetime(returns["date"])
returns["transaction_id"] = pd.to_numeric(returns["transaction_id"], errors="coerce")

exact = returns.dropna(subset=["transaction_id"]).copy()
fuzzy = returns[returns["transaction_id"].isna()].copy()

matched_return_amounts_usd = []  # list of (store_id, date_used_for_quarter, usd_amount)

# Exact matches: pull the matched transaction's currency conversion rate
tx_by_id = tx.set_index("transaction_id")
for _, r in exact.iterrows():
    tid = r["transaction_id"]
    if tid in tx_by_id.index:
        matched_tx = tx_by_id.loc[tid]
        rate = matched_tx["usd_exchange_rate"] if r["currency"] == matched_tx["currency"] else 1.0
        usd_amt = r["amount"] * rate
        matched_return_amounts_usd.append((r["store_id"], matched_tx["date"], usd_amt))

# Fuzzy matches: same store, within 3 days, closest amount within $1 tolerance
for _, r in fuzzy.iterrows():
    cand = tx[(tx["store_id"] == r["store_id"]) & (tx["date"].between(r["date"] - pd.Timedelta(days=3), r["date"] + pd.Timedelta(days=3)))]
    if cand.empty:
        continue
    cand = cand.copy()
    cand["amt_diff"] = (cand["amount"] - r["amount"]).abs()
    best = cand.sort_values("amt_diff").iloc[0]
    if best["amt_diff"] <= 1.0:
        rate = best["usd_exchange_rate"] if r["currency"] == best["currency"] else 1.0
        usd_amt = r["amount"] * rate
        matched_return_amounts_usd.append((r["store_id"], best["date"], usd_amt))

returns_df = pd.DataFrame(matched_return_amounts_usd, columns=["store_id", "date", "return_usd"])

# ---------------------------------------------------------------------
# 5. Fiscal quarter assignment. Fiscal year starts July 1.
# fiscal_year label = the calendar year the fiscal year ENDS in.
#   Jul-Sep -> Q1, Oct-Dec -> Q2, Jan-Mar -> Q3, Apr-Jun -> Q4
#   month>=7: fiscal_year = year+1 ; else fiscal_year = year
# ---------------------------------------------------------------------
def fiscal_quarter(d):
    m, y = d.month, d.year
    if m >= 7:
        fy = y + 1
        q = 1 if m <= 9 else 2
    else:
        fy = y
        q = 3 if m <= 3 else 4
    return f"FY{fy}-Q{q}"

tx["fiscal_quarter"] = tx["date"].apply(fiscal_quarter)
returns_df["fiscal_quarter"] = returns_df["date"].apply(fiscal_quarter) if not returns_df.empty else []

# ---------------------------------------------------------------------
# 6. Aggregate.
# ---------------------------------------------------------------------
rev = tx.groupby(["store_id", "fiscal_quarter"]).agg(
    net_revenue_usd=("amount_usd", "sum"),
    transaction_count=("transaction_id", "count"),
).reset_index()

if not returns_df.empty:
    ret_agg = returns_df.groupby(["store_id", "fiscal_quarter"])["return_usd"].sum().reset_index()
    rev = rev.merge(ret_agg, on=["store_id", "fiscal_quarter"], how="left")
    rev["return_usd"] = rev["return_usd"].fillna(0.0)
    rev["net_revenue_usd"] = rev["net_revenue_usd"] - rev["return_usd"]
    rev = rev.drop(columns="return_usd")

rev["net_revenue_usd"] = rev["net_revenue_usd"].round(2)
rev = rev.sort_values(["store_id", "fiscal_quarter"]).reset_index(drop=True)
rev.to_csv(OUT_PATH, index=False)

# ---------------------------------------------------------------------
# 7. Region growth analysis for the free-text question.
# ---------------------------------------------------------------------
rev_region = rev.merge(real_stores[["store_id", "region"]], on="store_id", how="left")
q2 = rev_region[rev_region["fiscal_quarter"] == "FY2024-Q2"].groupby("region")["net_revenue_usd"].sum()
q3 = rev_region[rev_region["fiscal_quarter"] == "FY2024-Q3"].groupby("region")["net_revenue_usd"].sum()
growth = ((q3 - q2) / q2 * 100).sort_values(ascending=False)

print("Wrote", OUT_PATH)
print("\nQoQ growth FY2024 Q2->Q3 by region (%):")
print(growth)
print("\nTop growth region:", growth.index[0])

answer_text = (
    "North shows the largest apparent quarter-over-quarter revenue growth between "
    "fiscal Q2 2024 and fiscal Q3 2024, but this is a data artifact rather than "
    "organic growth: a one-day backfill dump of roughly 55 transactions landed at "
    "store 103 on 2024-03-15, identifiable by pos_terminal_id values starting with "
    "'BACKFILL-'. Excluding that single-day batch, North's underlying growth is "
    "unremarkable. The genuine organic growth story for the period is West's "
    "increase, which is explained by new store 305 opening on 2023-10-01 and "
    "ramping up sales through fiscal Q3 2024."
)

answer_path = os.path.join(os.path.dirname(OUT_PATH) or ".", "answer.txt")
with open(answer_path, "w") as f:
    f.write(answer_text)
print("Wrote", answer_path)
