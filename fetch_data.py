import json
import os
from datetime import datetime, timezone

from dotenv import load_dotenv

from config import ACTIVE_COMMODITY, commodity_data_dir, get_commodity_config
from http_retry import get_with_retry

load_dotenv()

EIA_BASE_URL = "https://api.eia.gov/v2"
WEEKS_OF_HISTORY = 12


class EIAFetchError(Exception):
    pass


def _fetch_series(route, series_id, api_key):
    url = f"{EIA_BASE_URL}/{route}/data/"
    params = {
        "api_key": api_key,
        "frequency": "weekly",
        "data[0]": "value",
        "facets[series][]": series_id,
        "sort[0][column]": "period",
        "sort[0][direction]": "desc",
        "length": WEEKS_OF_HISTORY,
    }

    resp = get_with_retry(url, params, EIAFetchError, f"EIA fetch for series {series_id}")

    if resp.status_code != 200:
        raise EIAFetchError(
            f"EIA API returned HTTP {resp.status_code} for series {series_id}: {resp.text[:300]}"
        )

    try:
        payload = resp.json()
        rows = payload["response"]["data"]
    except (ValueError, KeyError) as exc:
        raise EIAFetchError(
            f"Unexpected EIA response shape for series {series_id}: {resp.text[:300]}"
        ) from exc

    if not rows:
        raise EIAFetchError(f"EIA API returned zero rows for series {series_id}")

    points = [{"period": row["period"], "value": float(row["value"])} for row in rows]
    points.sort(key=lambda p: p["period"])  # ascending, oldest first
    return points


def fetch_commodity_data(commodity=None):
    commodity = commodity or ACTIVE_COMMODITY
    api_key = os.environ.get("EIA_API_KEY")
    if not api_key:
        raise EIAFetchError("EIA_API_KEY not found in environment (check your .env file)")

    commodity_cfg = get_commodity_config(commodity)

    price_points = _fetch_series(
        commodity_cfg["eia_price_route"], commodity_cfg["eia_price_series"], api_key
    )
    stocks_points = _fetch_series(
        commodity_cfg["eia_stocks_route"], commodity_cfg["eia_stocks_series"], api_key
    )

    return {
        "commodity": commodity,
        "fetched_at": datetime.now(timezone.utc).isoformat(),
        "price_series": {
            "series_id": commodity_cfg["eia_price_series"],
            "unit": commodity_cfg["price_unit"],
            "data": price_points,
        },
        "stocks_series": {
            "series_id": commodity_cfg["eia_stocks_series"],
            "unit": commodity_cfg["stocks_unit"],
            "data": stocks_points,
        },
    }


def save_commodity_data(payload):
    commodity = payload["commodity"]
    data_dir = commodity_data_dir(commodity)
    data_dir.mkdir(parents=True, exist_ok=True)
    fetch_date = datetime.now(timezone.utc).strftime("%Y-%m-%d")

    dated_path = data_dir / f"{fetch_date}.json"
    latest_path = data_dir / "latest.json"

    with open(dated_path, "w") as f:
        json.dump(payload, f, indent=2)
    with open(latest_path, "w") as f:
        json.dump(payload, f, indent=2)

    return dated_path, latest_path


if __name__ == "__main__":
    data = fetch_commodity_data()
    dated_path, latest_path = save_commodity_data(data)
    print(f"Saved {len(data['price_series']['data'])} weeks of price data")
    print(f"Saved {len(data['stocks_series']['data'])} weeks of stocks data")
    print(f"-> {dated_path}")
    print(f"-> {latest_path}")
