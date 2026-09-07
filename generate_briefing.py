import argparse
import json
from datetime import datetime, timezone

import anthropic
from dotenv import load_dotenv

from config import ACTIVE_COMMODITY, commodity_briefings_dir, commodity_data_dir, get_commodity_config

load_dotenv()

MODEL = "claude-sonnet-5"
MAX_TOKENS = 2048


def _system_prompt(display_name, data_source):
    # EIA commodities report a physical stock LEVEL ("inventory"); wheat reports
    # weekly export NET SALES, which is a sales flow, not a stock level. Only the
    # data-description nouns and the wheat-specific caveats change below -- the
    # anti-hallucination rules are the same for every commodity.
    if data_source == "usda":
        supply_phrase = (
            "weekly export-sales data (new export sales for the week, net of "
            "cancellations — a sales flow, not a stockpile level)"
        )
        supply_noun = "export-sales"
        extra_rules = (
            "\n- The export-sales figure is a weekly FLOW of new sales, not an inventory "
            "level. Do not describe it as a stock build or draw, or as tonnes sitting in "
            "storage. Frame it as the pace of new sales running above or below its recent "
            "weekly average.\n"
            "- The price series is a regional Kansas City Hard Red Winter cash bid; the "
            "export-sales series is national and spans all wheat classes. Do not write as "
            "though the price and the sales figure describe the same wheat."
        )
    else:
        supply_phrase = "inventory data"
        supply_noun = "inventory"
        extra_rules = ""

    return f"""You are a junior commodities analyst writing a short internal note on \
the week's {display_name} market for your team. Write in that register: plain, precise, no hype, like \
a quick note passed along before a meeting, not a polished public research report.

You will be given a structured JSON summary of this week's price move, {supply_phrase}, and \
a rough volatility measure, plus a short list of recent {display_name}-related headlines (which may be \
empty).

Rules:
- Only draw a connection between a headline and a price or {supply_noun} move if it's a \
reasonable, defensible inference. Otherwise, report the move plainly without inventing a \
cause.
- If no headlines are provided, write the briefing from the price and {supply_noun} data alone \
- do not invent news context.{extra_rules}
- End with exactly one forward-looking watch item.
- Target 150-200 words. Do not pad or use filler.
- Plain prose paragraphs. No headers, bullet points, or markdown."""


class BriefingGenerationError(Exception):
    pass


def _load_json(path, error_label):
    if not path.exists():
        raise BriefingGenerationError(f"No {error_label} file at {path}")
    with open(path) as f:
        return json.load(f)


def _build_user_message(analysis, news):
    headlines = news.get("headlines", [])
    if headlines:
        headlines_text = "\n".join(f"- {h['title']}" for h in headlines)
    else:
        headlines_text = "No headlines available this week."

    return (
        f"Structured summary (JSON):\n{json.dumps(analysis, indent=2)}\n\n"
        f"Headlines:\n{headlines_text}"
    )


def generate_briefing(skip_llm=False, commodity=None):
    commodity = commodity or ACTIVE_COMMODITY
    data_dir = commodity_data_dir(commodity)
    analysis = _load_json(data_dir / "analysis_latest.json", "analysis")
    news = _load_json(data_dir / "news_latest.json", "news")

    if skip_llm:
        return (
            "[SKIP-LLM PLACEHOLDER - no Anthropic API call made]\n\n"
            f"Analysis that would have been sent:\n{json.dumps(analysis, indent=2)}\n\n"
            f"Headlines that would have been sent:\n"
            f"{json.dumps(news.get('headlines', []), indent=2)}"
        )

    cfg = get_commodity_config(commodity)
    display_name = cfg["display_name"]
    client = anthropic.Anthropic()
    user_message = _build_user_message(analysis, news)

    response = client.messages.create(
        model=MODEL,
        max_tokens=MAX_TOKENS,
        system=_system_prompt(display_name, cfg["data_source"]),
        messages=[{"role": "user", "content": user_message}],
    )

    if response.stop_reason == "refusal":
        raise BriefingGenerationError("Claude declined to generate the briefing (refusal)")

    text = "".join(block.text for block in response.content if block.type == "text")
    if not text.strip():
        raise BriefingGenerationError("Claude returned an empty briefing")

    return text.strip()


def save_briefing(text, commodity=None, meta=None):
    commodity = commodity or ACTIVE_COMMODITY
    briefings_dir = commodity_briefings_dir(commodity)
    briefings_dir.mkdir(parents=True, exist_ok=True)
    date_str = datetime.now(timezone.utc).strftime("%Y-%m-%d")

    dated_path = briefings_dir / f"{date_str}.md"
    latest_path = briefings_dir / "latest.md"

    with open(dated_path, "w") as f:
        f.write(text)
    with open(latest_path, "w") as f:
        f.write(text)

    if meta is not None:
        with open(briefings_dir / f"{date_str}.meta.json", "w") as f:
            json.dump(meta, f, indent=2)

    return dated_path, latest_path


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--skip-llm",
        action="store_true",
        help="Skip the Anthropic API call and write a placeholder briefing instead",
    )
    args = parser.parse_args()

    briefing_text = generate_briefing(skip_llm=args.skip_llm)
    dated_path, latest_path = save_briefing(briefing_text)
    print(briefing_text)
    print(f"\n-> {dated_path}")
    print(f"-> {latest_path}")
