import json
import statistics

from config import ACTIVE_COMMODITY, commodity_data_dir

TRAILING_WEEKS = 8


class AnalysisError(Exception):
    pass


def _load_latest_data(commodity=None):
    commodity = commodity or ACTIVE_COMMODITY
    latest_path = commodity_data_dir(commodity) / "latest.json"
    if not latest_path.exists():
        raise AnalysisError(f"No data file at {latest_path} — run fetch_data.py first")
    with open(latest_path) as f:
        return json.load(f)


def _values(series):
    return [point["value"] for point in series["data"]]


def _week_over_week_changes(values):
    return [values[i] - values[i - 1] for i in range(1, len(values))]


def analyze_commodity_data(raw_data):
    commodity = raw_data["commodity"]
    price_values = _values(raw_data["price_series"])
    stocks_values = _values(raw_data["stocks_series"])

    min_points = TRAILING_WEEKS + 2
    if len(price_values) < min_points or len(stocks_values) < min_points:
        raise AnalysisError(
            f"Need at least {min_points} weeks of history for trailing {TRAILING_WEEKS}-week "
            f"analysis, got {len(price_values)} price / {len(stocks_values)} stocks points"
        )

    week_ending = raw_data["price_series"]["data"][-1]["period"]

    # --- price move over the week ---
    latest_price = price_values[-1]
    prior_price = price_values[-2]
    price_change_abs = latest_price - prior_price
    price_change_pct = (price_change_abs / prior_price) * 100

    # --- inventory "surprise" vs recent average weekly change ---
    stock_changes = _week_over_week_changes(stocks_values)
    latest_stock_change = stock_changes[-1]
    recent_avg_stock_change = statistics.mean(stock_changes[-(TRAILING_WEEKS + 1):-1])
    surprise_vs_recent_avg = latest_stock_change - recent_avg_stock_change

    # --- basic volatility: stdev of weekly % price changes, trailing N weeks ---
    price_pct_changes = [
        (price_values[i] - price_values[i - 1]) / price_values[i - 1] * 100
        for i in range(1, len(price_values))
    ]
    trailing_pct_changes = price_pct_changes[-TRAILING_WEEKS:]
    volatility_stdev_pct = statistics.stdev(trailing_pct_changes)

    return {
        "commodity": commodity,
        "week_ending": week_ending,
        "price": {
            "latest": round(latest_price, 2),
            "prior_week": round(prior_price, 2),
            "change_abs": round(price_change_abs, 2),
            "change_pct": round(price_change_pct, 2),
            "unit": raw_data["price_series"]["unit"],
        },
        "inventory": {
            "latest_level": round(stocks_values[-1], 1),
            "week_change": round(latest_stock_change, 1),
            "recent_avg_change_8w": round(recent_avg_stock_change, 1),
            "surprise_vs_recent_avg": round(surprise_vs_recent_avg, 1),
            "unit": raw_data["stocks_series"]["unit"],
            "surprise_definition": (
                "This week's stock change minus the average weekly change over the "
                "trailing 8 weeks. It is a self-relative signal, not a comparison to "
                "analyst consensus/forecast."
            ),
        },
        "volatility": {
            "metric": f"stdev of weekly % price changes, trailing {TRAILING_WEEKS} weeks",
            "value_pct": round(volatility_stdev_pct, 2),
        },
    }


def save_analysis(analysis):
    commodity = analysis["commodity"]
    data_dir = commodity_data_dir(commodity)
    data_dir.mkdir(parents=True, exist_ok=True)
    latest_path = data_dir / "analysis_latest.json"
    with open(latest_path, "w") as f:
        json.dump(analysis, f, indent=2)
    return latest_path


if __name__ == "__main__":
    raw_data = _load_latest_data()
    analysis = analyze_commodity_data(raw_data)
    path = save_analysis(analysis)
    print(json.dumps(analysis, indent=2))
    print(f"\n-> {path}")
