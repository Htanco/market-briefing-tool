import json
import os
from datetime import datetime, timezone

from dotenv import load_dotenv

from config import ACTIVE_COMMODITY, commodity_data_dir, get_commodity_config
from http_retry import get_with_retry

load_dotenv()

CURRENTS_SEARCH_URL = "https://api.currentsapi.services/v1/search"
MAX_HEADLINES = 6


class NewsFetchError(Exception):
    pass


def _relevant(article, keyword_terms):
    title = (article.get("title") or "").lower()
    return any(term.lower() in title for term in keyword_terms)


def fetch_headlines(commodity=None):
    commodity = commodity or ACTIVE_COMMODITY
    api_key = os.environ.get("CURRENTS_API_KEY")
    if not api_key:
        raise NewsFetchError("CURRENTS_API_KEY not found in environment (check your .env file)")

    commodity_cfg = get_commodity_config(commodity)
    keywords = commodity_cfg["news_keywords"]
    keyword_terms = [term.strip() for term in keywords.split(" OR ")]

    params = {
        "keywords": keywords,
        "language": "en",
        "apiKey": api_key,
    }

    resp = get_with_retry(CURRENTS_SEARCH_URL, params, NewsFetchError, "Currents news fetch")

    if resp.status_code != 200:
        raise NewsFetchError(f"Currents API returned HTTP {resp.status_code}: {resp.text[:300]}")

    try:
        payload = resp.json()
        articles = payload["news"]
    except (ValueError, KeyError) as exc:
        raise NewsFetchError(f"Unexpected Currents response shape: {resp.text[:300]}") from exc

    relevant = [a for a in articles if _relevant(a, keyword_terms)]

    headlines = [
        {
            "title": a.get("title"),
            "url": a.get("url"),
            "published": a.get("published"),
        }
        for a in relevant[:MAX_HEADLINES]
    ]

    return {
        "commodity": commodity,
        "fetched_at": datetime.now(timezone.utc).isoformat(),
        "headlines": headlines,
    }


def save_headlines(payload):
    commodity = payload["commodity"]
    data_dir = commodity_data_dir(commodity)
    data_dir.mkdir(parents=True, exist_ok=True)
    fetch_date = datetime.now(timezone.utc).strftime("%Y-%m-%d")

    dated_path = data_dir / f"news_{fetch_date}.json"
    latest_path = data_dir / "news_latest.json"

    with open(dated_path, "w") as f:
        json.dump(payload, f, indent=2)
    with open(latest_path, "w") as f:
        json.dump(payload, f, indent=2)

    return dated_path, latest_path


if __name__ == "__main__":
    data = fetch_headlines()
    dated_path, latest_path = save_headlines(data)
    print(f"Found {len(data['headlines'])} relevant headlines:")
    for h in data["headlines"]:
        print(f"- {h['title']} ({h['published']})")
    print(f"\n-> {dated_path}")
    print(f"-> {latest_path}")
