"""
Maps a normalized news item to direct + indirect (related) tickers using the
static relationship graph in data/relationships.json. This is the ground-truth
graph; the classifier prompt may also propose additional inferred
relationships, but those are marked separately as model-inferred, not graph-confirmed.

Three levels of indirect impact are surfaced, all graph-confirmed (nothing
invented at runtime):
  - "company": explicit related-ticker links (e.g. TSM -> NVDA, supplier)
  - "sector":  any other watchlist ticker tagged with the same sector
  - "country": any other watchlist ticker tagged with the same country

No cap is applied to sector/country matches — if ten watchlist tickers share
a sector, all ten are listed, each with a short explanation of why.
"""
import json
from config import Config


def _load_relationships() -> dict:
    with open(Config.RELATIONSHIPS_PATH, "r") as f:
        return json.load(f)


def resolve_tickers(direct_tickers: list[str]) -> dict:
    """
    Given a list of directly-mentioned tickers, return:
        {
            "direct": [...],
            "indirect": {
                ticker: {
                    "related_to": X,
                    "level": "company" | "sector" | "country",
                    "type": ...,
                    "note": ...
                }, ...
            }
        }
    """
    relationships = _load_relationships()
    indirect = {}

    for ticker in direct_tickers:
        graph_entry = relationships.get(ticker)
        if not graph_entry:
            continue

        # --- Company-level: explicit related-ticker links ---
        for related_ticker in graph_entry.get("related", []):
            if related_ticker in direct_tickers:
                continue
            indirect.setdefault(related_ticker, {
                "related_to": ticker,
                "level": "company",
                "type": graph_entry.get("type", "related"),
                "note": graph_entry.get("note", ""),
            })

        # --- Sector-level: any other tracked ticker in the same sector ---
        sector = graph_entry.get("sector")
        if sector:
            for other_ticker, other_entry in relationships.items():
                if other_ticker == ticker or other_ticker in direct_tickers:
                    continue
                if other_entry.get("sector") == sector:
                    indirect.setdefault(other_ticker, {
                        "related_to": ticker,
                        "level": "sector",
                        "type": "sector_peer",
                        "note": f"Shares the '{sector}' sector with {ticker} — sector-wide news may affect both",
                    })

        # --- Country-level: any other tracked ticker in the same country ---
        country = graph_entry.get("country")
        if country:
            for other_ticker, other_entry in relationships.items():
                if other_ticker == ticker or other_ticker in direct_tickers:
                    continue
                if other_entry.get("country") == country:
                    indirect.setdefault(other_ticker, {
                        "related_to": ticker,
                        "level": "country",
                        "type": "country_peer",
                        "note": f"Shares '{country}' as a home/operating market with {ticker} — country-level events (regulatory, currency, geopolitical) may affect both",
                    })

    return {"direct": direct_tickers, "indirect": indirect}
