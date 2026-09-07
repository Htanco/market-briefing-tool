# Weekly Commodity Market Briefing Tool

An automated pipeline that pulls a commodity's weekly price and supply data, computes the kind of signals a junior commodities analyst would check before writing a note, and uses Claude to generate a short, analyst-style market briefing. Think of it as a trading desk's weekly note, generated on demand instead of by hand.

The pipeline is commodity-agnostic. Each commodity is one entry in `config.py`, and new ones get added over time without touching the pipeline code. Three are live today: oil (WTI crude), natural gas (Henry Hub), and wheat (Kansas City HRW). Each one runs on its own weekly schedule, pulls from its own data sources, and gets its briefings archived next to the others on the same GitHub Pages page. See the Design Notes for how that works.

## Why weekly, and when each commodity runs

A weekly cadence means every briefing has something real to say: an actual price move and a supply surprise to talk about, rather than daily noise. Each commodity is timed to whichever public data release the market watches most closely.

Oil and natural gas are built around the EIA's weekly reports, and both run on Wednesday afternoon US Eastern time. Wheat is built around the USDA's FAS Export Sales report, which comes out Thursday at 8:30 a.m. Eastern, so the wheat run happens Thursday afternoon.

## What it does

1. **`fetch_data.py`** — pulls about 12 weeks of weekly price and supply data for whichever commodity you're running. Oil and gas come from the EIA API (spot price plus storage level). Wheat's price comes from USDA AMS Market News, specifically report AMS_3223, "Kansas City Board of Trade Daily Wheat Bids", with the daily cash bids resampled to weekly. Wheat's supply figure comes from USDA FAS Export Sales, commodity 107 ("All Wheat"), which is weekly export net sales.
2. **`analyze.py`** — computes the week-over-week price move, a supply "surprise", and short-run volatility. The surprise is the latest value against the trailing 8-week average. For oil and gas that's an inventory build or draw. For wheat it's the export sales pace for the week.
3. **`news.py`** — pulls commodity-relevant headlines from the Currents API, filtered for keyword relevance, so the briefing has some real-world context.
4. **`generate_briefing.py`** — sends the structured price, supply, and headline data to Claude (Sonnet). The system prompt is written to sound like an analyst's internal note, and it tells the model not to invent causal links between headlines and price moves that the data doesn't support.
5. **`main.py`** — runs all four steps end to end.
6. **`http_retry.py`** — shared retry/backoff logic (3 retries, 2s/4s/8s exponential backoff) for the EIA, USDA, and Currents API calls, so a transient network hiccup or server error doesn't fail an entire scheduled run. Client errors (bad API key, bad request) fail immediately instead of retrying, since retrying can't fix those.

## Setup

```bash
pip install -r requirements.txt
```

Create a `.env` file (not committed — see `.gitignore`) with:

```
ANTHROPIC_API_KEY=your-key-here   # or any AI provider you prefer
EIA_API_KEY=your-key-here         # oil and natural gas price + storage data
USDA_FAS_API_KEY=your-key-here    # wheat export sales, free from api.fas.usda.gov
USDA_MARS_API_KEY=your-key-here   # wheat cash price (AMS Market News), free from mymarketnews.ams.usda.gov
CURRENTS_API_KEY=your-key-here    # headlines, or any news API you prefer
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

The pipeline runs oil unless you tell it otherwise. Pick a different commodity with `--commodity`:

```bash
python main.py --commodity natural_gas
python main.py --commodity wheat
```

## Design notes / why it's built this way

- **Commodity-agnostic by design.** All the commodity-specific values (data source, series and report IDs, units, news keywords) live in `config.py`, keyed by a `data_source` field that the fetch layer dispatches on. Oil, natural gas, and wheat are implemented. Adding the next one means adding a config entry, plus one fetch function if it brings a new data provider. It does not mean rewriting the pipeline. Every commodity's briefings go into the same dated, non-overwriting archive, so the GitHub Pages page just grows a new section per commodity.
- **Stages are separated on purpose.** Fetching, analysis, news, and LLM generation are independent scripts, not one monolith, so any single layer can be improved or swapped without touching the others.
- **The supply "surprise" is self-relative, not measured against a market consensus forecast.** It compares the latest value to the series' own trailing 8-week average. For oil and gas that is an inventory build or draw. For wheat it is the week's export sales pace, which is a flow rather than a stock level, so the wheat path skips the differencing step that only makes sense for a running total. Each variant is labelled explicitly in the output data.
- **Wheat's price and supply series describe different wheat, on purpose.** The price is a regional Kansas City Hard Red Winter cash bid (report AMS_3223, "Ordinary" protein, which is the base-protein HRW quote). The export sales figure is national and covers every wheat class (FAS commodity 107). These are the best free weekly public series for each side, but they are not the same wheat, and the briefing prompt is told not to write about them as if they were.
- **Wheat price source: USDA MARS rather than Yahoo Finance.** Chicago wheat futures (`ZW=F`) via Yahoo were the obvious first choice, but that endpoint is unofficial and unversioned, which is a bad thing to depend on in an unattended weekly job. AMS_3223 is an official USDA cash series with a stable API. The tradeoff is that it is regional HRW rather than a national benchmark, which is the caveat above.
- **The LLM prompt is deliberately constrained against overreach.** It's told to report the data plainly if no headline plausibly explains a price move, rather than forcing a narrative. In testing this held up well: the model caught an internal contradiction in one headline (a "soaring" price framing that didn't match an actual price drop) and flagged it rather than smoothing it over.
- **Retry logic distinguishes transient from permanent failures.** Network errors and 5xx server responses are retried with exponential backoff; 4xx errors (bad key, bad request) fail immediately, since retrying wouldn't change the outcome. Covered by tests in `test_retry.py`.

## Adding a new commodity

A new commodity is mostly a `config.py` entry. Here is the practical version.

### 1. If it reuses a data source that already exists (say, another EIA series)

Add one entry to `COMMODITIES` in `config.py` with these fields:

- `display_name`, for example `"Copper (COMEX)"`
- `data_source: "eia"`, which is the field `fetch_data.py` dispatches on
- `eia_price_route`, `eia_price_series`, `price_unit`
- `eia_stocks_route`, `eia_stocks_series`, `stocks_unit`
- `news_keywords`, a string of `" OR "`-separated terms that get substring-matched against headline titles

That is the only code change. `main.py` picks up the new `--commodity` choice, `build_index.py` adds an archive section, and `analyze.py` and `generate_briefing.py` already handle the `eia` path. You still need to add a workflow file (step 4).

### 2. If it needs a new data provider (the way wheat needed USDA)

Add a new `data_source` value like `"usda"`, a branch for it in `fetch_commodity_data()`, and a fetch function. Use `http_retry.get_with_retry` for the HTTP calls. It takes an optional `auth=` argument (for example `(key, "")` for HTTP Basic) and an optional `headers=` argument for providers that do not take the key as a query parameter.

The fetch function has to return this exact structure, so that `analyze.py` and `save_commodity_data` keep working without changes:

```python
{
    "commodity": "<key matching the COMMODITIES dict>",  # the save_* functions read the
                                                         # commodity from here. Do not pass
                                                         # it around as a separate argument
                                                         # with its own fallback.
    "fetched_at": "<ISO 8601 UTC string>",
    "price_series": {
        "series_id": "<str>",
        "unit": "<str>",
        "data": [{"period": "YYYY-MM-DD", "value": <float>}, ...],  # oldest first, at
                                                                    # least 10 points
    },
    # exactly one of the following, with the same inner shape as price_series:
    "stocks_series": { ... },  # when the supply metric is a physical stock level
    "flow_series":   { ... },  # when it is a per-week flow (see step 3)
}
```

`analyze.py` works out `flow_series` versus `stocks_series` on its own, and `save_commodity_data` just writes whatever keys are there.

### 3. When `analyze.py` needs a new branch

Only when the new supply series is a flow (a per-week quantity, like wheat's export net sales) rather than a stock level (a running total, like oil and gas inventory).

`analyze.py` takes a stock level, differences it to get the weekly change, and compares that change to its trailing 8-week average. Differencing a flow does not mean anything, because you would be taking the change of a change. So for a flow, return it as `flow_series` and add a branch in `analyze_commodity_data()` that compares the latest weekly value straight to its own trailing 8-week mean, with no call to `_week_over_week_changes`. Give the result block its own name (wheat's is `export_sales`, not `inventory`) and use that same name wherever `main.py` and `generate_briefing.py` read it. A stock-level series needs no change to `analyze.py` at all.

### 4. GitHub Actions

Give the commodity its own workflow file, copied from one of the existing ones, with:

- its own concurrency group, `weekly-briefing-<commodity>`
- the run step `python main.py --commodity <commodity>`
- the `git pull --rebase origin main` before `git push`, since the other workflows also commit every week
- only the API-key secrets it actually uses

One thing the wheat build taught us: do not reach for the Wednesday cron just because oil and gas use it. Oil and gas run Wednesday because that is when the EIA publishes. Wheat's USDA FAS Export Sales report comes out Thursday at 8:30 a.m. Eastern, so the wheat workflow runs Thursday afternoon. Before you schedule a new commodity, look up when its data provider actually publishes, and set the cron a few hours after that, on the same day if it is a morning release. A fetch that is a day early is a silent failure. It runs fine and briefs last week's number.

## Possible extensions

- More commodities. Each one is a `config.py` entry, plus one fetch function if it brings a new data provider. Corn and soybeans, for instance, would reuse the USDA FAS and MARS plumbing that wheat already added.
- A consensus or expectations feed, so the supply "surprise" can be measured against the market's forecast instead of only the series' own recent trend.
- Tighter headline relevance filtering. The current keyword substring match is deliberately simple.

## Tech stack

Python, EIA API, USDA FAS Export Sales API, USDA AMS Market News (MARS) API, Currents API, Anthropic API (Claude Sonnet)
