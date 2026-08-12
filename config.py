from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent
DATA_DIR = PROJECT_ROOT / "data"
BRIEFINGS_DIR = PROJECT_ROOT / "briefings"

COMMODITIES = {
    "oil": {
        "display_name": "Oil (WTI Crude)",
        "eia_price_route": "petroleum/pri/spt",
        "eia_price_series": "RWTC",       # Cushing, OK WTI Spot Price FOB, $/BBL
        "eia_stocks_route": "petroleum/stoc/wstk",
        "eia_stocks_series": "WCESTUS1",  # US ending stocks excl. SPR, thousand barrels
        "news_keywords": "oil OR crude OR OPEC OR WTI OR Brent",
    }
}

ACTIVE_COMMODITY = "oil"


def get_commodity_config():
    return COMMODITIES[ACTIVE_COMMODITY]
