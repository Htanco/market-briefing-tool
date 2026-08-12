import argparse
import sys

from analyze import AnalysisError, analyze_commodity_data, save_analysis
from fetch_data import EIAFetchError, fetch_commodity_data, save_commodity_data
from generate_briefing import BriefingGenerationError, generate_briefing, save_briefing
from news import NewsFetchError, fetch_headlines, save_headlines


def main(skip_llm=False):
    print("[1/4] Fetching EIA price & inventory data...")
    try:
        raw_data = fetch_commodity_data()
        dated_path, latest_path = save_commodity_data(raw_data)
    except EIAFetchError as exc:
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
    print(f"      week ending {analysis['week_ending']}: "
          f"price {analysis['price']['change_pct']}%, "
          f"inventory surprise {analysis['inventory']['surprise_vs_recent_avg']} "
          f"{analysis['inventory']['unit']}")

    print("[3/4] Fetching oil/energy headlines...")
    try:
        news = fetch_headlines()
        save_headlines(news)
    except NewsFetchError as exc:
        print(f"News fetch failed: {exc}")
        return 1
    print(f"      {len(news['headlines'])} relevant headlines found")

    print(f"[4/4] Generating briefing{' (--skip-llm)' if skip_llm else ''}...")
    try:
        briefing_text = generate_briefing(skip_llm=skip_llm)
        dated_path, latest_path = save_briefing(briefing_text)
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
    args = parser.parse_args()
    sys.exit(main(skip_llm=args.skip_llm))
