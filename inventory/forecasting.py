"""Step 3 + validation: moving-average and exponential-smoothing forecasts, MAE / MAPE backtests."""
import numpy as np
import pandas as pd


def moving_average(series, window=7, alpha=0.3):
    """Forecast of average daily demand = mean of the last `window` days."""
    return float(series.tail(window).mean())


def exp_smoothing(series, window=7, alpha=0.3):
    """Simple exponential smoothing: last smoothed level is the daily-demand forecast."""
    return float(series.ewm(alpha=alpha, adjust=False).mean().iloc[-1])


METHODS = {"moving_average": moving_average, "exp_smoothing": exp_smoothing}


def mae(actual, forecast):
    return float(np.mean(np.abs(np.asarray(actual) - np.asarray(forecast))))


def mape(actual, forecast):
    """Mean Absolute Percentage Error (%), ignoring periods with zero actual demand."""
    a, f = np.asarray(actual, dtype=float), np.asarray(forecast, dtype=float)
    mask = a > 0
    if not mask.any():
        return float("nan")
    return float(np.mean(np.abs((a[mask] - f[mask]) / a[mask])) * 100)


def wape(actual, forecast):
    """Weighted absolute percentage error (%): total absolute error / total actual demand.
    More stable than MAPE for lumpy demand."""
    a, f = np.asarray(actual, dtype=float), np.asarray(forecast, dtype=float)
    return float(np.abs(a - f).sum() / a.sum() * 100) if a.sum() > 0 else float("nan")


def backtest(series, method, holdout_weeks=8, window=7, alpha=0.3):
    """Rolling-origin test: for each of the last `holdout_weeks` weeks, forecast the
    week's demand (7 x daily forecast) using only earlier data, then compare to actual."""
    fn, n, rows = METHODS[method], len(series), []
    for k in range(holdout_weeks, 0, -1):
        end = n - 7 * k
        rows.append((series.iloc[end:end + 7].sum(), 7 * fn(series.iloc[:end], window, alpha)))
    return pd.DataFrame(rows, columns=["actual", "forecast"])


def evaluate(daily, window=7, alpha=0.3, holdout_weeks=8):
    """MAE / MAPE for every product and method."""
    if len(daily) < 7 * holdout_weeks + 14:
        raise ValueError("Not enough history for the chosen holdout; reduce holdout_weeks.")
    rows = []
    for pid in daily.columns:
        for m in METHODS:
            bt = backtest(daily[pid], m, holdout_weeks, window, alpha)
            rows.append({"product_id": pid, "method": m,
                         "mae": mae(bt.actual, bt.forecast), "mape": mape(bt.actual, bt.forecast),
                         "wape": wape(bt.actual, bt.forecast)})
    return pd.DataFrame(rows)


def best_methods(accuracy):
    """Pick the lowest-MAE method per product."""
    idx = accuracy.groupby("product_id")["mae"].idxmin()
    return accuracy.loc[idx].set_index("product_id")["method"]


def forecast_daily(series, method, window=7, alpha=0.3):
    return max(METHODS[method](series, window, alpha), 0.0)
