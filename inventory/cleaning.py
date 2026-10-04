"""Step 2: clean missing/duplicate records and aggregate demand by day or week."""
import pandas as pd


def _norm_id(s):
    return s.astype("string").str.strip().str.upper()


def clean_products(products):
    df = products.copy()
    df["product_id"] = _norm_id(df["product_id"])
    df = df.dropna(subset=["product_id"]).drop_duplicates("product_id", keep="first")
    df["lead_time_days"] = pd.to_numeric(df["lead_time_days"], errors="coerce")
    df["lead_time_days"] = df["lead_time_days"].fillna(df["lead_time_days"].median()).clip(lower=1)
    return df.reset_index(drop=True)


def clean_stock(stock, product_ids):
    df = stock.copy()
    df["product_id"] = _norm_id(df["product_id"])
    df["current_stock"] = pd.to_numeric(df["current_stock"], errors="coerce")
    df = df.dropna(subset=["product_id"]).drop_duplicates("product_id", keep="last")
    df = df[df["product_id"].isin(product_ids)]
    df["current_stock"] = df["current_stock"].fillna(0).clip(lower=0)
    return df.reset_index(drop=True)


def clean_sales(sales, product_ids):
    """Returns (clean_df, report). Removes duplicates, unparseable/missing values,
    negative quantities and products absent from the master data."""
    report = {"raw_rows": len(sales)}
    df = sales.copy()
    df["date"] = pd.to_datetime(df["date"], errors="coerce")   # keep time of day for duplicate detection
    df["quantity"] = pd.to_numeric(df["quantity"], errors="coerce")
    df["product_id"] = _norm_id(df["product_id"])

    n = len(df)
    df = df.drop_duplicates()
    report["duplicates_removed"] = n - len(df)
    df["date"] = df["date"].dt.normalize()

    n = len(df)
    df = df.dropna(subset=["date", "product_id", "quantity"])
    report["missing_removed"] = n - len(df)

    n = len(df)
    df = df[df["quantity"] >= 0]
    report["negative_removed"] = n - len(df)

    n = len(df)
    df = df[df["product_id"].isin(product_ids)]
    report["unknown_product_removed"] = n - len(df)

    report["clean_rows"] = len(df)
    return df.reset_index(drop=True), report


def aggregate_demand(sales, freq="D"):
    """Daily (D) or weekly (W) demand matrix: index=date, columns=product_id.
    Days with no sales are filled with 0 so averages are not inflated."""
    daily = sales.groupby(["date", "product_id"])["quantity"].sum().unstack(fill_value=0)
    full = pd.date_range(daily.index.min(), daily.index.max(), freq="D")
    daily = daily.reindex(full, fill_value=0).astype(float)
    daily.index.name = "date"
    return daily if freq == "D" else daily.resample("W").sum()


def cap_outliers(daily, quantile=0.99):
    """Winsorise one-off bulk orders: each product's daily demand is capped at the given quantile
    of its non-zero days. Returns (capped_daily, number_of_capped_days)."""
    capped, n = daily.copy(), 0
    for pid in capped.columns:
        pos = capped[pid][capped[pid] > 0]
        if len(pos) < 20:
            continue
        cap = float(pos.quantile(quantile))
        n += int((capped[pid] > cap).sum())
        capped[pid] = capped[pid].clip(upper=cap)
    return capped, n
