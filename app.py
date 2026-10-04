"""Streamlit dashboard:  streamlit run app.py"""
import streamlit as st
import pandas as pd
from inventory.pipeline import run_pipeline

st.set_page_config(page_title="Inventory Reorder Assistant", layout="wide")
st.title("📦 Inventory Forecasting & Reorder Assistant")

with st.sidebar:
    st.header("Data (optional upload)")
    up = {k: st.file_uploader(f"{k} (csv/xlsx)", type=["csv", "xlsx", "xls"], key=k)
          for k in ["sales_history", "current_stock", "products"]}
    st.caption("Only the sales file is required; stock and product files are optional. "
               "Leave all empty to use the sample data in data/.")
    cmap_txt = st.text_input("Column map (optional)", placeholder="date=Order Date, product_id=SKU, quantity=Qty")
    default_lt = st.number_input("Default lead time (days) if missing", 1, 90, 7)
    st.header("Parameters")
    window = st.slider("Moving-average window (days)", 3, 30, 7)
    alpha = st.slider("Exp. smoothing alpha", 0.05, 0.9, 0.3, 0.05)
    holdout = st.slider("Backtest weeks", 4, 12, 8)
    sl = st.select_slider("Service level", [0.90, 0.95, 0.975, 0.99], 0.95)
    review = st.slider("Review period (days)", 7, 30, 14)
    slow = st.number_input("Slow-moving below (units/day)", 0.0, 5.0, 0.5, 0.1)
    risk_thr = st.slider("Stockout-prone if risk >= (%)", 5, 80, 20, 5) / 100

sources = {k: v for k, v in up.items() if v is not None}
try:
    cmap = dict((x.strip() for x in kv.split("=", 1)) for kv in cmap_txt.split(",") if "=" in kv)
    res = run_pipeline("data", sources, window, alpha, holdout, sl, review, slow, cmap, default_lt, True, risk_thr)
except Exception as e:
    st.error(f"Could not run pipeline: {e}")
    st.stop()

for w in res["warnings"]:
    st.warning(w)
r, o = res["reorder"], res["overall"]
c1, c2, c3, c4, c5 = st.columns(5)
c1.metric("Products", len(r))
c2.metric("Need action", int(r.status.isin(["CRITICAL", "REORDER NOW"]).sum()))
c3.metric("MAE (units/week)", o["selected_mae"])
c4.metric("MAPE (median)", f"{o['selected_mape_median']}%", help=f"Mean MAPE: {o['selected_mape']}% (inflated by products with near-zero sales weeks)")
c5.metric("WAPE", f"{o['selected_wape']}%")

t1, t2, t3, t4 = st.tabs(["Reorder list", "Demand & forecast", "Forecast accuracy", "Data cleaning"])
with t1:
    sel = st.multiselect("Filter status", r.status.unique().tolist(), r.status.unique().tolist())
    st.dataframe(r[r.status.isin(sel)], width="stretch", hide_index=True)
    st.download_button("Download reorder_list.csv", r.to_csv(index=False), "reorder_list.csv")
    st.bar_chart(r.status.value_counts())
with t2:
    pid = st.selectbox("Product", r.product_id)
    st.line_chart(res["weekly"][pid])
    row = r[r.product_id == pid].iloc[0]
    st.write(f"**{row.product_name}** — forecast {row.avg_daily_forecast}/day using *{row.forecast_method}*, "
             f"reorder point {row.reorder_point}, safety stock {row.safety_stock}, stock {row.current_stock:.0f}.")
with t3:
    st.write("Average error by method (weekly demand):")
    st.dataframe(o["by_method"])
    st.dataframe(res["accuracy"].round(2), width="stretch", hide_index=True)
with t4:
    st.json(res["clean_report"])
