"""
Builds the per-cycle digest, grouped by sector, showing:
  - the biggest/most important news per sector this cycle
  - which stocks in that sector are affected (direct + related)
  - each stock's direct news, classification, current price, and outlook

Deliberately reuses data already produced by the main classification step in
pipeline.py (which now includes current_price, expected_price_range, and
chart_read) via state_store, instead of making a second full round of API
calls per ticker. This both avoids duplicate cost and fixes the rate-limit
failures seen when the old version called Gemini once per ticker just for
the digest, on top of the classify/verify calls already happening.
"""
import json
from config import Config
from ticker_mapper import resolve_tickers
from state_store import StateStore


def load_watchlist() -> list[str]:
    with open(Config.WATCHLIST_PATH, "r") as f:
        return json.load(f)["tickers"]


def _load_relationships() -> dict:
    with open(Config.RELATIONSHIPS_PATH, "r") as f:
        return json.load(f)


def _group_by_sector(watchlist: list[str], relationships: dict) -> dict:
    groups = {}
    for ticker in watchlist:
        sector = relationships.get(ticker, {}).get("sector", "unclassified")
        groups.setdefault(sector, []).append(ticker)
    return groups


def _affected_tickers_for(ticker: str) -> str:
    context = resolve_tickers([ticker])
    if not context["indirect"]:
        return "none identified"
    return ", ".join(sorted(context["indirect"].keys()))


def build_digest():
    store = StateStore()
    watchlist = load_watchlist()
    relationships = _load_relationships()
    sector_groups = _group_by_sector(watchlist, relationships)

    sections = []

    for sector, tickers in sorted(sector_groups.items()):
        # Find the "biggest" news in this sector: highest priority, then
        # highest confidence, among tickers that have any recorded state.
        priority_rank = {"urgent": 2, "watch": 1, "low": 0}
        candidates = []
        for t in tickers:
            state = store.get_state(t)
            if state.get("last_headline"):
                candidates.append((t, state))

        biggest = None
        if candidates:
            biggest = max(
                candidates,
                key=lambda pair: (
                    priority_rank.get(pair[1].get("last_priority", "low"), 0),
                    pair[1].get("last_confidence") or 0,
                ),
            )

        lines = [f"*Sector: {sector}*"]

        if biggest:
            b_ticker, b_state = biggest
            lines.append(
                f"Biggest news: [{b_ticker}] {b_state.get('last_headline', '')} "
                f"— {b_state.get('last_classification', 'Uncertain')}"
            )
        else:
            lines.append("Biggest news: no fresh news this cycle for this sector.")

        for ticker in tickers:
            state = store.get_state(ticker)
            affected = _affected_tickers_for(ticker)

            if not state.get("last_headline"):
                lines.append(f"\n• *{ticker}* — no fresh news this cycle. Related tickers: {affected}")
                continue

            price = state.get("last_current_price")
            price_str = f"${price}" if price is not None else "n/a"
            expected_range = state.get("last_expected_price_range", "")
            chart_read = state.get("last_chart_read", "")

            lines.append(
                f"\n• *{ticker}* — {state.get('last_classification', 'Uncertain')} "
                f"(confidence {state.get('last_confidence', 'n/a')})\n"
                f"  News: {state.get('last_headline', '')}\n"
                f"  Current price: {price_str}"
                + (f" | Speculative range: {expected_range}" if expected_range else "")
                + (f"\n  Chart: {chart_read}" if chart_read else "")
                + f"\n  Related tickers that may also be affected: {affected}"
            )

        sections.append("\n".join(lines))

    digest = (
        "Watchlist Digest (by sector)\n\n"
        + "\n\n---\n\n".join(sections)
        + "\n\nNot financial advice - an AI's read of current data, not a guaranteed prediction."
    )
    return digest
