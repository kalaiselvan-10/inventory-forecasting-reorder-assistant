"""Imports a REAL-WORLD retail dataset and prepares the project's input files in data/.

Dataset: UCI "Online Retail" - real transactions of a UK online gift retailer, 01/12/2010-09/12/2011
(Chen, Sain & Guo, 2012; UCI Machine Learning Repository, id 352, CC BY 4.0). This script downloads a
public GitHub mirror of the original file (databricks/Spark-The-Definitive-Guide) .

What is REAL:      invoice lines (date, product code, description, quantity, unit price).
What is SIMULATED: the dataset contains no supplier lead times and no stock levels, so
                   products.csv `lead_time_days`/`supplier` and current_stock.csv are generated with a fixed
                   random seed (documented in data/DATA_NOTES.md). Replace them if you have real values.

Usage:  python fetch_dataset.py [--top 50] [--out data] [--csv path/to/online-retail.csv]
"""
import argparse
import io
import urllib.request
from pathlib import Path
import numpy as np
import pandas as pd

URL = ("https://raw.githubusercontent.com/databricks/Spark-The-Definitive-Guide/master/"
       "data/retail-data/all/online-retail-dataset.csv")
PRODUCT_CODE = r"^\d{5}[A-Za-z]{0,2}$"          # real products; excludes POST, DOT, M, BANK CHARGES ...
SUPPLIERS = ["Hartley Wholesale", "Northern Gifts Ltd", "Kensington Imports", "Albion Supplies", "Thames Trading Co"]


def load_raw(path=None):
    if path:
        return pd.read_csv(path, encoding="ISO-8859-1")
    print("Downloading Online Retail dataset (~45 MB) ...")
    with urllib.request.urlopen(URL, timeout=180) as r:
        return pd.read_csv(io.BytesIO(r.read()), encoding="ISO-8859-1")


def main(top=50, out="data", csv=None):
    raw = load_raw(csv)
    raw["InvoiceDate"] = pd.to_datetime(raw["InvoiceDate"], format="%m/%d/%Y %H:%M")
    raw["StockCode"] = raw["StockCode"].astype(str).str.strip().str.upper()
    is_prod = raw["StockCode"].str.match(PRODUCT_CODE)

    # choose the best-selling products that sell regularly (>= 200 distinct days)
    ok = raw[is_prod & (raw["Quantity"] > 0) & ~raw["InvoiceNo"].astype(str).str.startswith("C")]
    stats = ok.groupby("StockCode").agg(units=("Quantity", "sum"), days=("InvoiceDate", lambda s: s.dt.normalize().nunique()))
    chosen = stats[stats.days >= 200].nlargest(top, "units").index

    # sales file: raw invoice lines of the chosen products (incl. cancellations & repeated lines) plus
    # non-product codes, so the project's own cleaning step has real dirty data to remove
    keep = raw[raw["StockCode"].isin(chosen) | ~is_prod]
    sales = pd.DataFrame({"invoice_no": keep["InvoiceNo"].astype(str), "date": keep["InvoiceDate"],
                          "product_id": keep["StockCode"], "quantity": keep["Quantity"]})

    names = (raw[raw.StockCode.isin(chosen)].dropna(subset=["Description"])
             .groupby("StockCode")["Description"].agg(lambda s: s.str.strip().mode().iloc[0]))
    price = raw[raw.StockCode.isin(chosen) & (raw.UnitPrice > 0)].groupby("StockCode")["UnitPrice"].median()
    rng = np.random.default_rng(42)
    products = pd.DataFrame({"product_id": chosen, "product_name": names.reindex(chosen).values,
                             "category": "Gift & Homeware", "unit_price_gbp": price.reindex(chosen).round(2).values})
    products["supplier"] = rng.choice(SUPPLIERS, len(products))          # SIMULATED
    products["lead_time_days"] = rng.integers(5, 22, len(products))      # SIMULATED

    last90 = ok[(ok.StockCode.isin(chosen)) & (ok.InvoiceDate > ok.InvoiceDate.max() - pd.Timedelta(days=90))]
    avg = (last90.groupby("StockCode")["Quantity"].sum() / 90).reindex(chosen).fillna(0.1)
    mult = rng.choice([0.4, 0.8, 1.2, 1.6, 2.5, 4, 8], len(products))   # SIMULATED stock snapshot
    stock = pd.DataFrame({"product_id": chosen,
                          "current_stock": (avg.values * products.lead_time_days.values * mult).round().astype(int)})

    out = Path(out); out.mkdir(exist_ok=True)
    sales.to_csv(out / "sales_history.csv", index=False)
    products.to_csv(out / "products.csv", index=False)
    stock.to_csv(out / "current_stock.csv", index=False)
    (out / "DATA_NOTES.md").write_text(
        "# Data notes\n\n**Real data:** UCI Online Retail (UK online gift retailer, Dec 2010 - Dec 2011), "
        f"{len(sales):,} invoice lines for {len(chosen)} best-selling products plus non-product codes "
        "(postage, fees, manual entries), uncleaned (cancellations, repeated lines included).\n\n"
        "**Simulated (seed 42):** `lead_time_days` and `supplier` in products.csv, and all of current_stock.csv - "
        "the dataset has no supplier or inventory information. Replace with real values if available.\n")
    print(f"Saved {len(chosen)} products, {len(sales):,} invoice lines "
          f"({sales.date.min().date()} to {sales.date.max().date()}) -> {out}/")


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--top", type=int, default=50)
    ap.add_argument("--out", default="data")
    ap.add_argument("--csv", help="use a local copy of the Online Retail csv instead of downloading")
    a = ap.parse_args()
    main(a.top, a.out, a.csv)
