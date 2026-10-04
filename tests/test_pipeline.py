import numpy as np
import pandas as pd
from inventory.forecasting import moving_average, exp_smoothing, mae, mape
from inventory.cleaning import clean_sales, aggregate_demand
from inventory.pipeline import run_pipeline


def test_forecasts_constant_series():
    s = pd.Series([5.0] * 30)
    assert moving_average(s) == 5.0
    assert abs(exp_smoothing(s) - 5.0) < 1e-9


def test_metrics():
    assert mae([10, 20], [12, 18]) == 2
    assert abs(mape([10, 20], [12, 18]) - 15.0) < 1e-9


def test_cleaning_removes_bad_rows():
    df = pd.DataFrame({"date": ["2026-01-01"] * 2 + ["2026-01-02", "bad", "2026-01-03"],
                       "product_id": ["a", "a", "A", "A", "ZZ"],
                       "quantity": [1, 1, np.nan, 2, 3]})
    clean, rep = clean_sales(df, {"A"})
    assert len(clean) == 1 and rep["duplicates_removed"] == 1


def test_aggregate_fills_missing_days():
    df = pd.DataFrame({"date": pd.to_datetime(["2026-01-01", "2026-01-04"]),
                       "product_id": ["A", "A"], "quantity": [2, 3]})
    assert len(aggregate_demand(df, "D")) == 4


def test_full_pipeline_on_sample_data():
    res = run_pipeline("data")
    r = res["reorder"]
    assert (r.reorder_point >= 0).all() and r.priority.is_monotonic_increasing
    assert res["overall"]["selected_mae"] >= 0


def _retail_excel(path):
    rng = np.random.default_rng(0)
    d = pd.date_range("2026-01-01", periods=150)
    rows = [{"Order Date": x, "SKU": f"sku{i}", "Qty": int(rng.poisson(4 + i)), "Description": f"Item {i}"}
            for i in range(4) for x in d]
    pd.DataFrame(rows).to_excel(path, index=False)


def test_excel_import_with_different_columns_and_no_stock_file(tmp_path):
    f = tmp_path / "retail.xlsx"
    _retail_excel(f)
    res = run_pipeline(str(tmp_path), {"sales_history": str(f)})
    assert len(res["reorder"]) == 4
    assert any("ASSUMED" in w for w in res["warnings"])
    assert res["reorder"].product_name.iloc[0].startswith("Item")


def test_manual_column_map(tmp_path):
    f = tmp_path / "s.csv"
    d = pd.date_range("2026-01-01", periods=120)
    pd.DataFrame({"when": d, "code": "A1", "pieces": 3}).to_csv(f, index=False)
    res = run_pipeline(str(tmp_path), {"sales_history": str(f)},
                       column_map={"date": "when", "product_id": "code", "quantity": "pieces"})
    assert res["reorder"].product_id.tolist() == ["A1"]
