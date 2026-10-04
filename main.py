"""CLI: python main.py  ->  runs the full pipeline and writes reports to outputs/"""
import argparse
from inventory.pipeline import run_pipeline
from inventory.report import write_report

if __name__ == "__main__":
    ap = argparse.ArgumentParser(description="Inventory Forecasting & Reorder Assistant")
    ap.add_argument("--data-dir", default="data", help="folder with sales_history/current_stock/products (.csv or .xlsx)")
    ap.add_argument("--sales", help="path to a sales file (csv/xlsx), overrides the data folder")
    ap.add_argument("--stock", help="path to a stock file (csv/xlsx)")
    ap.add_argument("--products", help="path to a product master file (csv/xlsx)")
    ap.add_argument("--map", default="", help="column map, e.g. \"date=Order Date,product_id=SKU,quantity=Qty\"")
    ap.add_argument("--default-lead-time", type=int, default=7, help="used when no lead-time data exists")
    ap.add_argument("--window", type=int, default=7, help="moving-average window (days)")
    ap.add_argument("--alpha", type=float, default=0.3, help="exponential smoothing factor")
    ap.add_argument("--holdout-weeks", type=int, default=8)
    ap.add_argument("--service-level", type=float, default=0.95)
    ap.add_argument("--review-days", type=int, default=14)
    a = ap.parse_args()
    src = {k: v for k, v in {"sales_history": a.sales, "current_stock": a.stock, "products": a.products}.items() if v}
    cmap = dict(kv.split("=", 1) for kv in a.map.split(",") if "=" in kv)
    res = run_pipeline(a.data_dir, src, a.window, a.alpha, a.holdout_weeks, a.service_level,
                       a.review_days, column_map=cmap, default_lead_time=a.default_lead_time)
    for w in res["warnings"]:
        print("WARNING:", w)
    print(write_report(res))
    print("\nFiles saved in outputs/")
