"""Step 1: import sales history, current stock and product master data (supplier lead time).

Supports CSV and Excel (.xlsx/.xls), flexible column names (e.g. Order Date / SKU / Qty),
a manual column map, and sensible defaults (with warnings) when stock or lead times are not provided."""
from pathlib import Path
import re
import pandas as pd

ALIASES = {
    "date": ["date", "order_date", "invoicedate", "invoice_date", "sale_date", "sales_date",
             "transaction_date", "day", "timestamp", "datetime"],
    "product_id": ["product_id", "productid", "sku", "item_id", "itemid", "stockcode", "stock_code",
                   "item_code", "product_code", "product", "item"],
    "quantity": ["quantity", "qty", "quantity_sold", "units_sold", "units", "sold", "sales_qty", "demand", "sales"],
    "invoice_no": ["invoice_no", "invoiceno", "invoice", "order_id", "order_no"],
    "current_stock": ["current_stock", "stock", "stock_on_hand", "on_hand", "quantity_on_hand",
                      "closing_stock", "inventory", "available_stock"],
    "product_name": ["product_name", "name", "description", "item_name", "title"],
    "category": ["category", "product_category", "department", "type"],
    "supplier": ["supplier", "supplier_name", "vendor"],
    "lead_time_days": ["lead_time_days", "lead_time", "leadtime", "lead_days", "supplier_lead_time"],
}
EXTS = (".csv", ".xlsx", ".xls", ".xlsm")
REQUIRED = {"sales_history": ["date", "product_id", "quantity"],
            "current_stock": ["product_id", "current_stock"],
            "products": ["product_id"]}


def _norm(c):
    return re.sub(r"[^a-z0-9]+", "_", str(c).strip().lower()).strip("_")


def _read_table(src):
    name = str(getattr(src, "name", src)).lower()
    if name.endswith((".xlsx", ".xls", ".xlsm")):
        return pd.read_excel(src)
    try:
        return pd.read_csv(src)
    except UnicodeDecodeError:
        if hasattr(src, "seek"):
            src.seek(0)
        return pd.read_csv(src, encoding="latin-1")


def _standardise(df, column_map=None):
    """Rename columns to the canonical names using the manual map first, then aliases."""
    column_map = column_map or {}
    df = df.copy()
    df.columns = [_norm(c) for c in df.columns]
    manual = {_norm(v): k for k, v in column_map.items()}
    rename, used = {}, set()
    for col in df.columns:
        if col in manual:
            rename[col] = manual[col]; used.add(manual[col])
    for canon, names in ALIASES.items():
        if canon in used or canon in df.columns:
            continue
        for a in names:
            if a in df.columns and a not in rename:
                rename[a] = canon; used.add(canon); break
    return df.rename(columns=rename)


def _find(data_dir, name):
    for ext in EXTS:
        p = Path(data_dir) / f"{name}{ext}"
        if p.exists():
            return p
    return None


def load_all(data_dir="data", sources=None, column_map=None, default_lead_time=7):
    """Returns dict(sales_history, current_stock|None, products, warnings).
    `sources`: {dataset name: path or uploaded file}; `column_map`: {canonical: your column name}."""
    sources, warnings = sources or {}, []
    column_map = column_map or {}

    explicit_sales = sources.get("sales_history") is not None  # user supplied their own data:
    # do not mix it with the sample master/stock files lying in data_dir

    def get(name):
        src = sources.get(name) or (None if explicit_sales else _find(data_dir, name))
        return None if src is None else _standardise(_read_table(src), column_map)

    sales = get("sales_history")
    if sales is None:
        raise FileNotFoundError(f"sales_history (csv/xlsx) not found in '{data_dir}' and not uploaded.")
    missing = [c for c in REQUIRED["sales_history"] if c not in sales.columns]
    if missing:
        raise ValueError(f"Sales file is missing {missing}. Columns found: {list(sales.columns)}. "
                         f"Use a column map, e.g. {{'{missing[0]}': 'YourColumnName'}}.")

    products, stock = get("products"), get("current_stock")

    if products is None:  # build the master from the sales file
        cols = ["product_id"] + [c for c in ("product_name", "category", "supplier", "lead_time_days")
                                 if c in sales.columns]
        products = sales[cols].dropna(subset=["product_id"]).drop_duplicates("product_id")
        warnings.append("No product master file: built from the sales file.")
    if "product_id" not in products.columns:
        raise ValueError(f"Product master needs a product id column. Found: {list(products.columns)}")
    for col, default, msg in [("product_name", None, None), ("category", "General", None),
                              ("supplier", "Unknown", "No supplier column: set to 'Unknown'.")]:
        if col not in products.columns:
            products[col] = products["product_id"].astype(str) if col == "product_name" else default
            if msg:
                warnings.append(msg)
    if "lead_time_days" not in products.columns:
        products["lead_time_days"] = float(default_lead_time)
        warnings.append(f"No lead-time data: assumed {default_lead_time} days for every product.")

    if stock is None and "current_stock" in sales.columns:  # last known stock in the sales file
        s = sales.sort_values("date") if "date" in sales.columns else sales
        stock = s.dropna(subset=["current_stock"]).drop_duplicates("product_id", keep="last")[["product_id", "current_stock"]]
    if stock is not None and "current_stock" not in stock.columns:
        raise ValueError(f"Stock file needs a stock column. Found: {list(stock.columns)}")
    if stock is None:
        warnings.append("No current-stock data: stock is ASSUMED to be 14 days of demand. "
                        "Provide real stock levels for meaningful reorder advice.")
    return {"sales_history": sales, "current_stock": stock, "products": products, "warnings": warnings}
