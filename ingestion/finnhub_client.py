"""
Finnhub ingestion (free tier, no cost): company/general news, earnings calendar,
and analyst recommendation trends. This replaces Polygon.io (paid, $29/mo+) as
the primary news source for the $0/month stack.
Docs: https://finnhub.io/docs/api
"""
import requests
from datetime import date, timedelta
from config import Config

BASE_URL = "https://finnhub.io/api/v1"


def fetch_company_news(ticker: str, days_back: int = 2) -> list[dict]:
    """Fetch recent company-specific news for a single ticker (free tier)."""
    today = date.today()
    from_date = today - timedelta(days=days_back)
    params = {
        "symbol": ticker,
        "from": from_date.isoformat(),
        "to": today.isoformat(),
        "token": Config.FINNHUB_API_KEY,
    }
    try:
        resp = requests.get(f"{BASE_URL}/company-news", params=params, timeout=15)
        resp.raise_for_status()
        return resp.json() or []
    except requests.RequestException as e:
        print(f"[finnhub_client] Error fetching company news for {ticker}: {e}")
        return []


def fetch_general_news(category: str = "general") -> list[dict]:
    """Fetch general market news (macro, not ticker-specific). Free tier."""
    params = {"category": category, "token": Config.FINNHUB_API_KEY}
    try:
        resp = requests.get(f"{BASE_URL}/news", params=params, timeout=15)
        resp.raise_for_status()
        return resp.json() or []
    except requests.RequestException as e:
        print(f"[finnhub_client] Error fetching general news: {e}")
        return []


def normalize_finnhub_item(item: dict, direct_ticker: str | None = None) -> dict:
    """Normalize a raw Finnhub news item into the pipeline's common news schema."""
    return {
        "id": str(item.get("id", "")),
        "headline": item.get("headline", ""),
        "source": item.get("source", "Finnhub"),
        "timestamp": item.get("datetime", ""),  # unix epoch seconds
        "summary": item.get("summary", "") or "",
        "url": item.get("url", ""),
        "direct_tickers": [direct_ticker] if direct_ticker else (
            item.get("related", "").split(",") if item.get("related") else []
        ),
        "keywords": [],
    }


def fetch_earnings_calendar(tickers: list[str], days_ahead: int = 7) -> list[dict]:
    """Fetch upcoming earnings dates for the watchlist, filtered to relevant tickers."""
    today = date.today()
    to_date = today + timedelta(days=days_ahead)
    params = {
        "from": today.isoformat(),
        "to": to_date.isoformat(),
        "token": Config.FINNHUB_API_KEY,
    }
    try:
        resp = requests.get(f"{BASE_URL}/calendar/earnings", params=params, timeout=15)
        resp.raise_for_status()
        results = resp.json().get("earningsCalendar", [])
    except requests.RequestException as e:
        print(f"[finnhub_client] Error fetching earnings calendar: {e}")
        return []

    watchlist_set = set(tickers)
    return [r for r in results if r.get("symbol") in watchlist_set]


def fetch_recommendation_trend(ticker: str) -> dict | None:
    """Fetch the latest analyst recommendation trend (buy/hold/sell counts) for a ticker."""
    params = {"symbol": ticker, "token": Config.FINNHUB_API_KEY}
    try:
        resp = requests.get(f"{BASE_URL}/stock/recommendation", params=params, timeout=15)
        resp.raise_for_status()
        results = resp.json()
    except requests.RequestException as e:
        print(f"[finnhub_client] Error fetching recommendation trend for {ticker}: {e}")
        return None

    return results[0] if results else None
