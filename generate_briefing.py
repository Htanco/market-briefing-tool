import argparse
import json
from datetime import datetime, timezone

import anthropic
from dotenv import load_dotenv

from config import ACTIVE_COMMODITY, BRIEFINGS_DIR, DATA_DIR

load_dotenv()

MODEL = "claude-sonnet-5"
MAX_TOKENS = 2048

SYSTEM_PROMPT = """You are a junior commodities analyst writing a short internal note on \
the week's oil market for your team. Write in that register: plain, precise, no hype, like \
a quick note passed along before a meeting, not a polished public research report.

You will be given a structured JSON summary of this week's price move, inventory data, and \
a rough volatility measure, plus a short list of recent oil-related headlines (which may be \
empty).

Rules:
- Only draw a connection between a headline and a price or inventory move if it's a \
reasonable, defensible inference. Otherwise, report the move plainly without inventing a \
cause.
- If no headlines are provided, write the briefing from the price and inventory data alone \
- do not invent news context.
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


def generate_briefing(skip_llm=False):
    analysis = _load_json(DATA_DIR / f"{ACTIVE_COMMODITY}_analysis_latest.json", "analysis")
    news = _load_json(DATA_DIR / f"{ACTIVE_COMMODITY}_news_latest.json", "news")

    if skip_llm:
        return (
            "[SKIP-LLM PLACEHOLDER - no Anthropic API call made]\n\n"
            f"Analysis that would have been sent:\n{json.dumps(analysis, indent=2)}\n\n"
            f"Headlines that would have been sent:\n"
            f"{json.dumps(news.get('headlines', []), indent=2)}"
        )

    client = anthropic.Anthropic()
    user_message = _build_user_message(analysis, news)

    response = client.messages.create(
        model=MODEL,
        max_tokens=MAX_TOKENS,
        system=SYSTEM_PROMPT,
        messages=[{"role": "user", "content": user_message}],
    )

    if response.stop_reason == "refusal":
        raise BriefingGenerationError("Claude declined to generate the briefing (refusal)")

    text = "".join(block.text for block in response.content if block.type == "text")
    if not text.strip():
        raise BriefingGenerationError("Claude returned an empty briefing")

    return text.strip()


def save_briefing(text):
    BRIEFINGS_DIR.mkdir(parents=True, exist_ok=True)
    date_str = datetime.now(timezone.utc).strftime("%Y-%m-%d")

    dated_path = BRIEFINGS_DIR / f"{ACTIVE_COMMODITY}_briefing_{date_str}.md"
    latest_path = BRIEFINGS_DIR / f"{ACTIVE_COMMODITY}_briefing_latest.md"

    with open(dated_path, "w") as f:
        f.write(text)
    with open(latest_path, "w") as f:
        f.write(text)

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
