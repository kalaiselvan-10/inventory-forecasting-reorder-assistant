"""Steps 4-5: safety stock, reorder points, prioritized reorder list, slow-moving / stockout flags."""
from statistics import NormalDist
import numpy as np
import pandas as pd
from .forecasting import forecast_daily

STATUS_RANK = {"CRITICAL": 0, "REORDER NOW": 1, "REORDER SOON": 2, "OK": 3}


def build_reorder_table(daily, products, stock, best, window=7, alpha=0.3,
                        service_level=0.95, lookback=90, review_days=14, slow_threshold=0.5,
                        stockout_risk_threshold=0.20):
    """
    avg_daily_forecast d = forecast of daily demand (best method per product)
    safety_stock         = z * sigma_d * sqrt(L)       (z from service level, L = lead time in days)
    reorder_point        = d * L + safety_stock
    days_of_cover        = current_stock / d
    stockout_risk        = P(demand during lead time > current stock), normal approximation
    suggested_order_qty  = reorder_point + d * review_days - current_stock   (if stock <= ROP)
    """
    z = NormalDist().inv_cdf(service_level)
    base = products.merge(stock, on="product_id", how="left")
    base["current_stock"] = base["current_stock"].fillna(0)
    rows = []
    for _, p in base.iterrows():
        pid = p["product_id"]
        if pid not in daily.columns:
            continue
        s = daily[pid]
        method = best.get(pid, "moving_average")
        d = forecast_daily(s, method, window, alpha)
        sigma = float(s.tail(lookback).std(ddof=1))
        mean_recent = float(s.tail(lookback).mean())
        cv = sigma / mean_recent if mean_recent > 0 else 0.0
        L = float(p["lead_time_days"])
        ss = z * sigma * np.sqrt(L)
        rop = d * L + ss
        stk = float(p["current_stock"])
        cover = stk / d if d > 0 else np.inf

        if stk <= 0 or cover < L:
            status = "CRITICAL"
        elif stk <= rop:
            status = "REORDER NOW"
        elif stk <= 1.25 * rop:
            status = "REORDER SOON"
        else:
            status = "OK"

        qty = int(np.ceil(max(0.0, rop + d * review_days - stk))) if stk <= 1.25 * rop and d > 0 else 0
        flags = []
        if d < slow_threshold or (np.isfinite(cover) and cover > 90) or d == 0:
            flags.append("SLOW-MOVING")
        sd_L = sigma * np.sqrt(L)
        if sd_L > 0:
            risk = 1 - NormalDist().cdf((stk - d * L) / sd_L)
        else:
            risk = 1.0 if stk < d * L else 0.0
        if risk >= stockout_risk_threshold:
            flags.append("STOCKOUT-PRONE")

        rows.append({
            "product_id": pid, "product_name": p["product_name"], "category": p["category"],
            "supplier": p["supplier"], "lead_time_days": L, "current_stock": stk,
            "forecast_method": method, "avg_daily_forecast": round(d, 2),
            "demand_std": round(sigma, 2), "safety_stock": int(np.ceil(ss)),
            "reorder_point": int(np.ceil(rop)),
            "days_of_cover": round(cover, 1) if np.isfinite(cover) else np.inf,
            "stockout_risk_pct": round(100 * risk, 1), "status": status, "suggested_order_qty": qty, "flags": ", ".join(flags),
        })
    out = pd.DataFrame(rows)
    out["_rank"] = out["status"].map(STATUS_RANK)
    out = out.sort_values(["_rank", "days_of_cover"]).drop(columns="_rank").reset_index(drop=True)
    out.insert(0, "priority", range(1, len(out) + 1))
    return out
