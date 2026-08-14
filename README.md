# Weekly Oil Market Briefing Tool

An automated pipeline that pulls weekly WTI crude price and US commercial inventory data, computes the kind of signals a junior commodities analyst would check before writing a note, and uses Claude to generate a short, analyst-style market briefing. Think of it as a trading desk's weekly note, generated on demand instead of by hand.

Built as an independent project to demonstrate applied commodity-market analysis and AI/automation skills, with a deliberate design choice to stay commodity-agnostic rather than oil-specific (see Design Notes below).

## Why weekly, and why Wednesday

The pipeline is timed around the EIA's weekly petroleum status report, released every Wednesday — the most closely-watched public data point in the oil market. A weekly cadence also means each briefing has something real to say: an actual price move and inventory surprise to discuss, rather than daily noise.

## What it does

1. **`fetch_data.py`** — pulls 12 weeks of weekly WTI spot price and US commercial crude inventory data (excluding the Strategic Petroleum Reserve) from the EIA's public API.
2. **`analyze.py`** — computes the week-over-week price move, an inventory "surprise" (the latest build/draw vs. the trailing 8-week average), and short-run volatility.
3. **`news.py`** — pulls relevant oil/energy headlines from the Currents API, filtered for keyword relevance, to give the briefing real-world context.
4. **`generate_briefing.py`** — sends the structured price, inventory, and headline data to Claude (Sonnet), with a system prompt written to sound like an analyst's internal note and explicit instructions not to invent causal links between headlines and price moves that the data doesn't support.
5. **`main.py`** — runs all four steps end to end.
6. **`http_retry.py`** — shared retry/backoff logic (3 retries, 2s/4s/8s exponential backoff) for the EIA and Currents API calls, so a transient network hiccup or server error doesn't fail an entire scheduled run. Client errors (bad API key, bad request) fail immediately instead of retrying, since retrying can't fix those.

## Setup

```bash
pip install -r requirements.txt
```

Create a `.env` file (not committed — see `.gitignore`) with:

```
ANTHROPIC_API_KEY=your-key-here   # or any AI provider you prefer
EIA_API_KEY=your-key-here         # or any commodity data source you prefer
CURRENTS_API_KEY=your-key-here    # or any news API you prefer
```

## Usage

Run the full pipeline:

```bash
python main.py
```

Run without spending Anthropic API credit — writes a placeholder briefing, useful for testing the rest of the pipeline:

```bash
python main.py --skip-llm
```

## Design notes / why it's built this way

- **Commodity-agnostic by design.** All commodity-specific values (EIA series IDs, news keywords) live in `config.py`. Oil is the first commodity implemented, but the pipeline itself doesn't assume oil — adding a second commodity means adding a config entry, not rewriting the pipeline.
- **Stages are separated on purpose.** Fetching, analysis, news, and LLM generation are independent scripts, not one monolith, so any single layer can be improved or swapped without touching the others.
- **The inventory "surprise" is self-relative, not vs. a market consensus forecast.** It compares the latest change to the asset's own recent trend. This is labeled explicitly in the output data so it isn't mistaken for something it isn't.
- **The LLM prompt is deliberately constrained against overreach.** It's told to report the data plainly if no headline plausibly explains a price move, rather than forcing a narrative. In testing this held up well: the model caught an internal contradiction in one headline (a "soaring" price framing that didn't match an actual price drop) and flagged it rather than smoothing it over.
- **Retry logic distinguishes transient from permanent failures.** Network errors and 5xx server responses are retried with exponential backoff; 4xx errors (bad key, bad request) fail immediately, since retrying wouldn't change the outcome. Covered by tests in `test_retry.py`.

## Possible extensions

- Publish briefings automatically via GitHub Pages, with a dated, non-overwriting archive
- Schedule weekly runs via GitHub Actions
- Extend `config.py` to a second commodity (e.g. copper) to demonstrate the cross-commodity design in practice

## Tech stack

Python, EIA API, Currents API, Anthropic API (Claude Sonnet)
