"""End-to-end pipeline used by both the CLI (main.py) and the Streamlit dashboard."""
import pandas as pd
from .data_loader import load_all
from .cleaning import clean_products, clean_stock, clean_sales, aggregate_demand, cap_outliers
from .forecasting import evaluate, best_methods
from .reorder import build_reorder_table


def run_pipeline(data_dir="data", sources=None, window=7, alpha=0.3, holdout_weeks=8,
                 service_level=0.95, review_days=14, slow_threshold=0.5,
                 column_map=None, default_lead_time=7, cap_bulk_orders=True, stockout_risk_threshold=0.20):
    raw = load_all(data_dir, sources, column_map, default_lead_time)
    products = clean_products(raw["products"])
    ids = set(products["product_id"])
    sales, report = clean_sales(raw["sales_history"], ids)

    if sales.empty:
        raise ValueError("No usable sales rows after cleaning (check dates, quantities and that product IDs "
                         "match the product master). Cleaning report: " + str(report))
    daily = aggregate_demand(sales, "D")
    if cap_bulk_orders:
        daily, report["outlier_days_capped"] = cap_outliers(daily)
    weekly = daily.resample("W").sum()
    if raw["current_stock"] is None:   # assumption flagged in warnings
        stock = pd.DataFrame({"product_id": daily.columns,
                              "current_stock": (daily.tail(90).mean() * 14).round().values})
    else:
        stock = clean_stock(raw["current_stock"], ids)

    accuracy = evaluate(daily, window, alpha, holdout_weeks)
    best = best_methods(accuracy)
    reorder = build_reorder_table(daily, products, stock, best, window, alpha,
                                  service_level, review_days=review_days,
                                  slow_threshold=slow_threshold,
                                  stockout_risk_threshold=stockout_risk_threshold)

    chosen = accuracy.merge(best.rename("best").reset_index(), on="product_id")
    chosen = chosen[chosen["method"] == chosen["best"]]
    overall = {
        "by_method": accuracy.groupby("method")[["mae", "mape", "wape"]].mean().round(2),
        "selected_mae": round(float(chosen["mae"].mean()), 2),
        "selected_mape": round(float(chosen["mape"].mean()), 2),
        "selected_mape_median": round(float(chosen["mape"].median()), 2),
        "selected_wape": round(float(chosen["wape"].mean()), 2),
    }
    return {"clean_report": report, "daily": daily, "weekly": weekly, "accuracy": accuracy,
            "reorder": reorder, "overall": overall, "products": products,
            "warnings": raw["warnings"]}
