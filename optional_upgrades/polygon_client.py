"""
Polygon.io news ingestion (Stocks Starter tier).
Docs: https://polygon.io/docs/stocks/get_v2_reference_news
"""
import requests
from config import Config

BASE_URL = "https://api.polygon.io"


def fetch_news_for_tickers(tickers: list[str], limit: int = 20) -> list[dict]:
    """
    Fetch recent news for a list of tickers. Polygon's news endpoint accepts
    a single ticker filter per call on the free/starter tier, so we loop.
    Returns a de-duplicated, normalized list of raw news dicts.
    """
    all_items = []
    seen_ids = set()

    for ticker in tickers:
        params = {
            "ticker": ticker,
            "limit": limit,
            "order": "desc",
            "sort": "published_utc",
            "apiKey": Config.POLYGON_API_KEY,
        }
        try:
            resp = requests.get(f"{BASE_URL}/v2/reference/news", params=params, timeout=15)
            resp.raise_for_status()
            results = resp.json().get("results", [])
        except requests.RequestException as e:
            print(f"[polygon_client] Error fetching news for {ticker}: {e}")
            continue

        for item in results:
            item_id = item.get("id")
            if item_id in seen_ids:
                continue
            seen_ids.add(item_id)
            all_items.append(item)

    return all_items


def normalize_polygon_item(item: dict) -> dict:
    """Normalize a raw Polygon news item into the pipeline's common news schema."""
    return {
        "id": item.get("id"),
        "headline": item.get("title", ""),
        "source": item.get("publisher", {}).get("name", "Polygon"),
        "timestamp": item.get("published_utc", ""),
        "summary": item.get("description", "") or "",
        "url": item.get("article_url", ""),
        "direct_tickers": item.get("tickers", []) or [],
        "keywords": item.get("keywords", []) or [],
    }
