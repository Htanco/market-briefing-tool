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

    # EIA commodities carry a "stocks_series" (a physical stock LEVEL); wheat
    # carries a "flow_series" (weekly export net sales, already a per-week FLOW).
    is_flow = "flow_series" in raw_data
    supply_series = raw_data["flow_series"] if is_flow else raw_data["stocks_series"]
    supply_values = _values(supply_series)

    min_points = TRAILING_WEEKS + 2
    if len(price_values) < min_points or len(supply_values) < min_points:
        raise AnalysisError(
            f"Need at least {min_points} weeks of history for trailing {TRAILING_WEEKS}-week "
            f"analysis, got {len(price_values)} price / {len(supply_values)} supply points"
        )

    week_ending = raw_data["price_series"]["data"][-1]["period"]

    # --- price move over the week ---
    latest_price = price_values[-1]
    prior_price = price_values[-2]
    price_change_abs = latest_price - prior_price
    price_change_pct = (price_change_abs / prior_price) * 100

    # --- supply-side "surprise" vs the series' own trailing-8-week average ---
    if is_flow:
        # Weekly export NET SALES is already a per-week flow, so the latest
        # week's figure is compared DIRECTLY to the mean of the 8 weeks before
        # it (computed only over this wheat flow series). It is NOT differenced
        # -- differencing a flow would be a meaningless second derivative, and
        # _week_over_week_changes() is deliberately not called on this path.
        sales_week_ending = supply_series["data"][-1]["period"]
        latest_net_sales = supply_values[-1]
        recent_avg_net_sales = statistics.mean(supply_values[-(TRAILING_WEEKS + 1):-1])
        supply_block = {
            "latest_week_net_sales": round(latest_net_sales, 1),
            "recent_avg_net_sales_8w": round(recent_avg_net_sales, 1),
            "surprise_vs_recent_avg": round(latest_net_sales - recent_avg_net_sales, 1),
            "unit": supply_series["unit"],
            "sales_week_ending": sales_week_ending,
            "surprise_definition": (
                "This week's export NET SALES minus the mean of the trailing 8 weeks' "
                "net sales. It measures sales PACE relative to itself -- not versus "
                "analyst expectations, and NOT a physical inventory build or draw. "
                "'sales_week_ending' usually lags 'week_ending' (the price week) by "
                "about a week because the ESR report is released the following Thursday."
            ),
        }
        supply_key = "export_sales"
    else:
        stock_changes = _week_over_week_changes(supply_values)
        latest_stock_change = stock_changes[-1]
        recent_avg_stock_change = statistics.mean(stock_changes[-(TRAILING_WEEKS + 1):-1])
        supply_block = {
            "latest_level": round(supply_values[-1], 1),
            "week_change": round(latest_stock_change, 1),
            "recent_avg_change_8w": round(recent_avg_stock_change, 1),
            "surprise_vs_recent_avg": round(latest_stock_change - recent_avg_stock_change, 1),
            "unit": supply_series["unit"],
            "surprise_definition": (
                "This week's stock change minus the average weekly change over the "
                "trailing 8 weeks. It is a self-relative signal, not a comparison to "
                "analyst consensus/forecast."
            ),
        }
        supply_key = "inventory"

    # --- basic volatility: stdev of weekly % price changes, trailing N weeks ---
    price_pct_changes = [
        (price_values[i] - price_values[i - 1]) / price_values[i - 1] * 100
        for i in range(1, len(price_values))
    ]
    trailing_pct_changes = price_pct_changes[-TRAILING_WEEKS:]
    volatility_stdev_pct = statistics.stdev(trailing_pct_changes)

    analysis = {
        "commodity": commodity,
        "week_ending": week_ending,
        "price": {
            "latest": round(latest_price, 2),
            "prior_week": round(prior_price, 2),
            "change_abs": round(price_change_abs, 2),
            "change_pct": round(price_change_pct, 2),
            "unit": raw_data["price_series"]["unit"],
        },
    }
    analysis[supply_key] = supply_block
    analysis["volatility"] = {
        "metric": f"stdev of weekly % price changes, trailing {TRAILING_WEEKS} weeks",
        "value_pct": round(volatility_stdev_pct, 2),
    }
    return analysis


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
