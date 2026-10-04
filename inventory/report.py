"""Step 6: write the report files (CSV + text summary + charts)."""
from pathlib import Path
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt


def make_charts(res, out):
    r = res["reorder"]
    counts = r["status"].value_counts().reindex(["CRITICAL", "REORDER NOW", "REORDER SOON", "OK"]).fillna(0)
    fig, ax = plt.subplots(figsize=(6, 4))
    ax.bar(counts.index, counts.values, color=["#c0392b", "#e67e22", "#f1c40f", "#27ae60"])
    ax.set_title("Products by reorder status"); ax.set_ylabel("Products")
    fig.tight_layout(); fig.savefig(out / "status_chart.png", dpi=130); plt.close(fig)

    top = r.head(10)
    fig, ax = plt.subplots(figsize=(9, 4.5))
    x = range(len(top))
    ax.bar([i - 0.2 for i in x], top["current_stock"], 0.4, label="Current stock")
    ax.bar([i + 0.2 for i in x], top["reorder_point"], 0.4, label="Reorder point")
    ax.set_xticks(list(x)); ax.set_xticklabels(top["product_id"], rotation=45)
    ax.set_title("Top 10 priority items: stock vs reorder point"); ax.legend()
    fig.tight_layout(); fig.savefig(out / "priority_chart.png", dpi=130); plt.close(fig)


def write_report(res, out_dir="outputs"):
    out = Path(out_dir); out.mkdir(exist_ok=True)
    r, o, c = res["reorder"], res["overall"], res["clean_report"]
    r.to_csv(out / "reorder_list.csv", index=False)
    res["accuracy"].round(2).to_csv(out / "forecast_accuracy.csv", index=False)
    res["weekly"].to_csv(out / "weekly_demand.csv")
    make_charts(res, out)
    lines = [
        "INVENTORY FORECASTING & REORDER REPORT", "=" * 40,
        f"Data cleaning: {c}", "",
        "Forecast error (mean over products, weekly demand, 8-week rolling backtest):",
        o["by_method"].to_string(),
        f"Selected best-method-per-product -> MAE {o['selected_mae']} units/week | MAPE {o['selected_mape']}% (median across products {o['selected_mape_median']}%) | WAPE {o['selected_wape']}%", "",
        "Status counts:", r["status"].value_counts().to_string(), "",
        "Top 10 priority items:",
        r.head(10)[["priority", "product_id", "product_name", "current_stock", "reorder_point",
                    "days_of_cover", "status", "suggested_order_qty"]].to_string(index=False), "",
        "Slow-moving: " + (", ".join(r[r["flags"].str.contains("SLOW")]["product_id"]) or "none"),
        "Stockout-prone: " + (", ".join(r[r["flags"].str.contains("STOCKOUT")]["product_id"]) or "none"),
    ]
    (out / "summary.txt").write_text("\n".join(lines))
    return "\n".join(lines)
