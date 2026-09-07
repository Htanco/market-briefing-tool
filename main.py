import argparse
import sys

from analyze import AnalysisError, analyze_commodity_data, save_analysis
from config import ACTIVE_COMMODITY, COMMODITIES, get_commodity_config
from fetch_data import EIAFetchError, USDAFetchError, fetch_commodity_data, save_commodity_data
from generate_briefing import BriefingGenerationError, generate_briefing, save_briefing
from news import NewsFetchError, fetch_headlines, save_headlines


SOURCE_LABELS = {
    "eia": ("EIA", "inventory"),
    "usda": ("USDA", "export-sales"),
}


def main(skip_llm=False, commodity=None):
    commodity = commodity or ACTIVE_COMMODITY
    commodity_cfg = get_commodity_config(commodity)
    display_name = commodity_cfg["display_name"]
    source_label, supply_label = SOURCE_LABELS[commodity_cfg["data_source"]]

    print(f"[1/4] Fetching {source_label} price & {supply_label} data ({display_name})...")
    try:
        raw_data = fetch_commodity_data(commodity)
        dated_path, latest_path = save_commodity_data(raw_data)
    except (EIAFetchError, USDAFetchError) as exc:
        print(f"Data fetch failed: {exc}")
        return 1
    print(f"      -> {dated_path}")

    print("[2/4] Analyzing this week's signals...")
    try:
        analysis = analyze_commodity_data(raw_data)
        save_analysis(analysis)
    except AnalysisError as exc:
        print(f"Analysis failed: {exc}")
        return 1
    if "export_sales" in analysis:
        es = analysis["export_sales"]
        supply_summary = (
            f"export-sales pace {es['surprise_vs_recent_avg']:+,} {es['unit']} "
            f"vs 8-wk avg (sales week {es['sales_week_ending']})"
        )
    else:
        inv = analysis["inventory"]
        supply_summary = f"inventory surprise {inv['surprise_vs_recent_avg']} {inv['unit']}"
    print(f"      week ending {analysis['week_ending']}: "
          f"price {analysis['price']['change_pct']}%, {supply_summary}")

    print(f"[3/4] Fetching {display_name} headlines...")
    try:
        news = fetch_headlines(commodity)
        save_headlines(news)
    except NewsFetchError as exc:
        print(f"News fetch failed: {exc}")
        return 1
    print(f"      {len(news['headlines'])} relevant headlines found")

    print(f"[4/4] Generating briefing{' (--skip-llm)' if skip_llm else ''}...")
    try:
        briefing_text = generate_briefing(skip_llm=skip_llm, commodity=commodity)
        dated_path, latest_path = save_briefing(
            briefing_text,
            commodity=commodity,
            meta={
                "price_change_pct": analysis["price"]["change_pct"],
                "week_ending": analysis["week_ending"],
            },
        )
    except BriefingGenerationError as exc:
        print(f"Briefing generation failed: {exc}")
        return 1
    print(f"      -> {dated_path}")

    print("\nDone.")
    return 0


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--skip-llm",
        action="store_true",
        help="Skip the Anthropic API call and write a placeholder briefing instead",
    )
    parser.add_argument(
        "--commodity",
        choices=list(COMMODITIES.keys()),
        default=ACTIVE_COMMODITY,
        help="Which commodity to run the pipeline for",
    )
    args = parser.parse_args()
    sys.exit(main(skip_llm=args.skip_llm, commodity=args.commodity))
