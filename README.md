# Inventory Forecasting & Reorder Assistant

Python application that analyses sales history, current stock, supplier lead times and product master data to
forecast demand, compute safety stock / reorder points, and produce a prioritised reorder list with a dashboard.

## Requirements covered
| # | Requirement | Where |
|---|---|---|
| 1 | Import sales history, current stock, lead time, product master | `inventory/data_loader.py`: CSV or Excel, flexible column names, upload in dashboard |
| 2 | Clean missing/duplicate records, aggregate daily/weekly | `inventory/cleaning.py` |
| 3 | Moving-average & exponential-smoothing forecasts | `inventory/forecasting.py` |
| 4 | Safety stock & reorder point from lead time and demand variability | `inventory/reorder.py` |
| 5 | Prioritised reorder list, slow-moving & stockout-prone flags | `inventory/reorder.py` |
| 6 | Dashboard/report + MAE/MAPE validation | `app.py` (Streamlit), `inventory/report.py` |

## Run
```bash
python -m venv .venv && source .venv/bin/activate     # Windows: .venv\Scripts\activate
pip install -r requirements.txt
python fetch_dataset.py            # downloads the public dataset into data/ (already included in the zip)
python main.py                     # CLI: prints report, writes outputs/
streamlit run app.py               # interactive dashboard
pytest                             # unit tests
```

## Dataset (real-world, imported from an external source)
**UCI Online Retail** - real transactions of a UK online gift retailer (1 Dec 2010 - 9 Dec 2011), Chen, Sain & Guo (2012), UCI ML Repository #352.
`fetch_dataset.py` downloads a public GitHub mirror and builds `data/sales_history.csv` (raw invoice lines of the 50 best-selling regular products,
plus non-product codes such as postage/fees, with cancellations and repeated lines left in), `data/products.csv` and `data/current_stock.csv`.
The project's own cleaning step then removes duplicates, cancellations/negative quantities and non-product codes, aggregates to daily/weekly demand
and caps one-off bulk orders (99th percentile of each product's non-zero days; switch off with `cap_bulk_orders=False`).

**Be transparent in your report:** the dataset has no supplier lead times or stock levels. `lead_time_days`, `supplier` and `current_stock` are
**simulated with a fixed seed** (see `data/DATA_NOTES.md`); sales are real. Replace them with real values if you have them.

Forecast error is high for this data because real demand is lumpy (wholesale orders, Christmas ramp-up). MAE/MAPE are reported with WAPE
(total error / total demand), which is the more reliable figure here; the median MAPE is shown because a few near-zero weeks inflate the mean.

## Using your own / real dataset
```bash
python main.py --sales my_sales.xlsx                       # only a sales file is needed
python main.py --sales s.csv --stock st.xlsx --products p.csv
python main.py --sales s.csv --map "date=Order Date,product_id=SKU,quantity=Qty" --default-lead-time 10
```
- CSV and Excel (`.xlsx/.xls`) are supported; common column names (Order Date, InvoiceDate, SKU, StockCode, Qty, Description...) are recognised automatically, otherwise use `--map` (or the dashboard's *Column map* box).
- Only the sales file is required. If there is no product master it is built from the sales file; if there is no stock or lead-time data, documented defaults are used and a **warning** is shown (stock = 14 days of demand, lead time = `--default-lead-time`). Supply real stock/lead times for meaningful reorder advice.
- When you pass your own sales file, the sample files in `data/` are ignored.
- Dates are parsed month-first; exact duplicate rows are removed, so aggregate transaction data to one row per product per day first if identical repeat sales are legitimate.

## Input files (CSV or Excel)
- `sales_history.csv`: `date, product_id, quantity` (one row per product per day with sales)
- `current_stock.csv`: `product_id, current_stock`
- `products.csv`: `product_id, product_name, category, supplier, lead_time_days` (extra columns allowed)

## Method
- **Cleaning:** exact duplicates, unparseable dates, missing quantities, negative quantities and unknown products are removed (counts reported); IDs are trimmed/upper-cased; days without sales become 0.
- **Forecast:** daily demand rate via 7-day moving average or exponential smoothing (alpha 0.3); the method with the lower backtest MAE is chosen per product.
- **Validation:** rolling-origin backtest over the last 8 weeks, forecasting each week using only earlier data. Reported as **MAE** (units/week) and **MAPE** (%, weeks with zero actual demand ignored).
- **Safety stock** = z × σ_daily × √lead_time (z from service level, default 95% → 1.645; σ over last 90 days)
- **Reorder point** = daily forecast × lead_time + safety stock
- **Status:** CRITICAL (stock 0 or days of cover < lead time) → REORDER NOW (stock ≤ ROP) → REORDER SOON (≤ 1.25×ROP) → OK
- **Suggested order qty** = ROP + forecast × review period (14 d) − current stock
- **Flags:** SLOW-MOVING (< 0.5 units/day or > 90 days of cover); STOCKOUT-PRONE (estimated probability that demand during the lead time exceeds current stock is >= 20%; `stockout_risk_pct` column, threshold adjustable)

## Outputs (`outputs/`)
`reorder_list.csv`, `forecast_accuracy.csv`, `weekly_demand.csv`, `summary.txt`, `status_chart.png`, `priority_chart.png`

## Git
```bash
git init && git add . && git commit -m "Inventory forecasting & reorder assistant"
git branch -M main && git remote add origin <your-repo-url> && git push -u origin main
```

## Data sources and limitations
| Input | Source | Real? |
|---|---|---|
| Sales history (invoice lines) | UCI Online Retail, UK online gift retailer, Dec 2010 - Dec 2011 | Real |
| Product master (code, name, unit price) | Same dataset | Real |
| Supplier lead time and supplier name | Generated with a fixed random seed (5-21 days) in `fetch_dataset.py` | Simulated |
| Current stock | Generated with a fixed random seed as multiples of lead-time demand | Simulated |

Why: no public retail dataset publishes supplier lead times or stock levels together with real sales, because these are internal company records.
The pipeline is source-agnostic: replace `data/products.csv` and `data/current_stock.csv` (or upload them in the dashboard) with a company's real
files and every result updates; no code changes are needed. Reorder recommendations are therefore **illustrative** until real lead times and stock are supplied.
Forecast accuracy (MAE / MAPE / WAPE) is based only on the real sales data and is not affected by the simulated inputs.
