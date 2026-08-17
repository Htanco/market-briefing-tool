from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent
DATA_DIR = PROJECT_ROOT / "data"
BRIEFINGS_DIR = PROJECT_ROOT / "briefings"

COMMODITIES = {
    "oil": {
        "display_name": "Oil (WTI Crude)",
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
        "eia_price_route": "natural-gas/pri/fut",
        "eia_price_series": "RNGWHHD",    # Henry Hub Natural Gas Spot Price, $/MMBtu
        "price_unit": "$/MMBtu",
        "eia_stocks_route": "natural-gas/stor/wkly",
        "eia_stocks_series": "NW2_EPG0_SWO_R48_BCF",  # Lower 48 working underground storage, Bcf
        "stocks_unit": "Bcf",
        "news_keywords": "natural gas OR Henry Hub OR LNG OR gas storage",
    },
}

ACTIVE_COMMODITY = "oil"


def get_commodity_config(commodity=None):
    return COMMODITIES[commodity or ACTIVE_COMMODITY]


def commodity_data_dir(commodity):
    return DATA_DIR / commodity


def commodity_briefings_dir(commodity):
    return BRIEFINGS_DIR / commodity
