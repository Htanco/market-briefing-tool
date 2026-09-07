from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent
DATA_DIR = PROJECT_ROOT / "data"
BRIEFINGS_DIR = PROJECT_ROOT / "briefings"

COMMODITIES = {
    "oil": {
        "display_name": "Oil (WTI Crude)",
        "data_source": "eia",
        "eia_price_route": "petroleum/pri/spt",
        "eia_price_series": "RWTC",       # Cushing, OK WTI Spot Price FOB, $/BBL
        "price_unit": "$/BBL",
        "eia_stocks_route": "petroleum/stoc/wstk",
        "eia_stocks_series": "WCESTUS1",  # US ending stocks excl. SPR, thousand barrels
        "stocks_unit": "thousand barrels",
        "news_keywords": "oil OR crude OR OPEC OR WTI OR Brent",
    },
    "natural_gas": {
        "display_name": "Natural Gas (Henry Hub)",
        "data_source": "eia",
        "eia_price_route": "natural-gas/pri/fut",
        "eia_price_series": "RNGWHHD",    # Henry Hub Natural Gas Spot Price, $/MMBtu
        "price_unit": "$/MMBtu",
        "eia_stocks_route": "natural-gas/stor/wkly",
        "eia_stocks_series": "NW2_EPG0_SWO_R48_BCF",  # Lower 48 working underground storage, Bcf
        "stocks_unit": "Bcf",
        "news_keywords": "natural gas OR Henry Hub OR LNG OR gas storage",
    },
    "wheat": {
        "display_name": "Wheat (Kansas City HRW)",
        "data_source": "usda",
        # --- price: USDA AMS Market News (MARS), report AMS_3223 ---
        # "Kansas City Board of Trade Daily Wheat Bids" -- a REGIONAL, Hard Red
        # Winter-only cash bid. Daily bids resampled to weekly (last bid of the
        # week). "Ordinary" is the base-protein HRW quote trade press cites.
        "mars_report_slug": "3223",
        "mars_protein_tier": "Ordinary",
        "price_unit": "$/bushel",
        # --- supply: USDA FAS Export Sales (ESR), commodity 107 "All Wheat" ---
        # A weekly export SALES FLOW (new sales net of cancellations), NOT a
        # physical stock level. Also a NATIONAL, ALL-CLASS aggregate -- it does
        # not describe the same wheat as the HRW regional price above. This
        # class/geography mismatch is called out in the README and the briefing
        # system prompt so the generated note never conflates the two.
        "esr_commodity_code": 107,
        "flow_unit": "metric tons",
        "flow_label": "weekly export net sales",
        "news_keywords": (
            "wheat OR Black Sea grain OR wheat export ban OR Russia wheat export "
            "OR grain corridor"
        ),
    },
}

ACTIVE_COMMODITY = "oil"


def get_commodity_config(commodity=None):
    return COMMODITIES[commodity or ACTIVE_COMMODITY]


def commodity_data_dir(commodity):
    return DATA_DIR / commodity


def commodity_briefings_dir(commodity):
    return BRIEFINGS_DIR / commodity
