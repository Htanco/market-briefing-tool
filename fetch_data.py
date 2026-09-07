import json
import os
from datetime import datetime, timedelta, timezone

from dotenv import load_dotenv

from config import ACTIVE_COMMODITY, commodity_data_dir, get_commodity_config
from http_retry import get_with_retry

load_dotenv()

EIA_BASE_URL = "https://api.eia.gov/v2"
WEEKS_OF_HISTORY = 12

MARS_BASE_URL = "https://marsapi.ams.usda.gov/services/v1.2"
FAS_ESR_BASE_URL = "https://api.fas.usda.gov/api/esr"
WHEAT_PRICE_LOOKBACK_DAYS = 120     # ~17 ISO weeks of daily bids to collapse
WHEAT_WEEKS_OF_HISTORY = 12         # trailing weeks kept per series (mirrors WEEKS_OF_HISTORY)


class EIAFetchError(Exception):
    pass


class USDAFetchError(Exception):
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
    commodity_cfg = get_commodity_config(commodity)
    source = commodity_cfg["data_source"]
    if source == "eia":
        return _fetch_eia_commodity_data(commodity, commodity_cfg)
    if source == "usda":
        return fetch_wheat_data()
    raise ValueError(f"Unknown data_source {source!r} for commodity {commodity!r}")


def _fetch_eia_commodity_data(commodity, commodity_cfg):
    api_key = os.environ.get("EIA_API_KEY")
    if not api_key:
        raise EIAFetchError("EIA_API_KEY not found in environment (check your .env file)")

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


def _iso_week_key(d):
    year, week, _ = d.isocalendar()
    return (year, week)


def _wheat_marketing_year(today):
    """USDA wheat marketing year runs Jun 1 - May 31, labelled by the calendar
    year it ENDS in. So June 2026 onward is MY 2027."""
    return today.year + 1 if today.month >= 6 else today.year


def _fetch_mars_wheat_price(cfg):
    """USDA AMS Market News report AMS_3223, "Kansas City Board of Trade Daily
    Wheat Bids" -- a regional, Hard-Red-Winter-only cash bid.

    Pulls the last WHEAT_PRICE_LOOKBACK_DAYS of the report's "Report Detail"
    section (the default response is just header metadata), keeps the one row
    per trading day whose protein tier == cfg["mars_protein_tier"] ("Ordinary",
    the base-protein HRW quote), and reads its `avg_price` (already in $/bu;
    note this API mixes snake_case and space-separated keys). Daily bids are
    collapsed to weekly by keeping the LAST trading day's bid in each ISO week.
    ISO weeks with no trading day in the report are omitted -- never nulled,
    never carried forward.
    """
    api_key = os.environ.get("USDA_MARS_API_KEY")
    if not api_key:
        raise USDAFetchError("USDA_MARS_API_KEY not found in environment (check your .env file)")

    slug = cfg["mars_report_slug"]
    protein = cfg["mars_protein_tier"]
    today = datetime.now(timezone.utc).date()
    start = today - timedelta(days=WHEAT_PRICE_LOOKBACK_DAYS)

    url = f"{MARS_BASE_URL}/reports/{slug}/Report Detail"
    params = {"q": f"report_date={start:%m/%d/%Y}:{today:%m/%d/%Y}"}
    resp = get_with_retry(
        url, params, USDAFetchError, f"MARS fetch for report AMS_{slug}",
        timeout=30, auth=(api_key, ""),
    )
    if resp.status_code != 200:
        raise USDAFetchError(
            f"MARS API returned HTTP {resp.status_code} for AMS_{slug}: {resp.text[:300]}"
        )
    try:
        rows = resp.json()["results"]
    except (ValueError, KeyError) as exc:
        raise USDAFetchError(
            f"Unexpected MARS response shape for AMS_{slug}: {resp.text[:300]}"
        ) from exc

    daily = {}
    for row in rows:
        if row.get("protein") != protein:
            continue
        price = row.get("avg_price")
        report_date = row.get("report_date")
        if price is None or not report_date:
            continue                                  # malformed / header-only row -> skip
        try:
            day = datetime.strptime(report_date, "%m/%d/%Y").date()
        except ValueError:
            continue                                  # unparseable date -> skip
        daily[day] = float(price)

    if not daily:
        raise USDAFetchError(
            f"MARS AMS_{slug} returned no priced '{protein}' rows for "
            f"{start:%Y-%m-%d}..{today:%Y-%m-%d}"
        )

    weekly = {}
    for day in sorted(daily):                          # ascending -> last day of week wins
        weekly[_iso_week_key(day)] = {"period": day.isoformat(), "value": round(daily[day], 4)}

    points = [weekly[k] for k in sorted(weekly)][-WHEAT_WEEKS_OF_HISTORY:]
    return {
        "series_id": f"AMS_{slug} HRW {protein} cash bid ($/bu)",
        "unit": cfg["price_unit"],
        "data": points,
    }


def _fetch_esr_wheat_flow(cfg):
    """USDA FAS Export Sales (ESR), commodity 107 "All Wheat".

    Sums `currentMYNetSales` across every destination country per
    `weekEndingDate` to get the national weekly export NET SALES figure
    (metric tons). This is a weekly sales FLOW -- new sales net of
    cancellations -- NOT a physical stock level, and it is a national all-class
    aggregate, unlike the regional HRW price series. The current marketing year
    and the prior one are always both fetched and concatenated, so the series
    is continuous across the June 1 marketing-year rollover.
    """
    api_key = os.environ.get("USDA_FAS_API_KEY")
    if not api_key:
        raise USDAFetchError("USDA_FAS_API_KEY not found in environment (check your .env file)")

    code = cfg["esr_commodity_code"]
    this_my = _wheat_marketing_year(datetime.now(timezone.utc).date())

    weekly_tons = {}
    for market_year in (this_my - 1, this_my):
        url = f"{FAS_ESR_BASE_URL}/exports/commodityCode/{code}/allCountries/marketYear/{market_year}"
        resp = get_with_retry(
            url, {"api_key": api_key}, USDAFetchError,
            f"FAS ESR fetch for commodity {code} MY{market_year}", timeout=30,
        )
        if resp.status_code != 200:
            raise USDAFetchError(
                f"FAS ESR API returned HTTP {resp.status_code} for commodity {code} "
                f"MY{market_year}: {resp.text[:300]}"
            )
        try:
            country_rows = resp.json()
        except ValueError as exc:
            raise USDAFetchError(
                f"Unexpected FAS ESR response for commodity {code} MY{market_year}: {resp.text[:300]}"
            ) from exc

        for row in country_rows:
            week_ending = row.get("weekEndingDate")
            if not week_ending:
                continue                              # malformed row -> skip
            week = week_ending[:10]                    # 'YYYY-MM-DD'
            weekly_tons[week] = weekly_tons.get(week, 0.0) + float(row.get("currentMYNetSales") or 0.0)

    if not weekly_tons:
        raise USDAFetchError(
            f"FAS ESR returned zero rows for commodity {code} (MY{this_my - 1}+{this_my})"
        )

    points = [{"period": wk, "value": round(weekly_tons[wk], 1)} for wk in sorted(weekly_tons)]
    points = points[-WHEAT_WEEKS_OF_HISTORY:]
    return {
        "series_id": f"ESR commodity {code} (All Wheat) weekly net sales, all destinations",
        "unit": cfg["flow_unit"],
        "data": points,
    }


def fetch_wheat_data():
    cfg = get_commodity_config("wheat")
    return {
        "commodity": "wheat",
        "fetched_at": datetime.now(timezone.utc).isoformat(),
        "price_series": _fetch_mars_wheat_price(cfg),
        "flow_series": _fetch_esr_wheat_flow(cfg),
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
    supply_key = "stocks_series" if "stocks_series" in data else "flow_series"
    print(f"Saved {len(data['price_series']['data'])} weeks of price data")
    print(f"Saved {len(data[supply_key]['data'])} weeks of supply-side data")
    print(f"-> {dated_path}")
    print(f"-> {latest_path}")
