"""
Maps a normalized news item to direct + indirect (related) tickers using the
static relationship graph in data/relationships.json. This is the ground-truth
graph; the classifier prompt (Claude) may also propose additional inferred
relationships, but those are marked separately as model-inferred, not graph-confirmed.
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
            "indirect": {ticker: {"related_to": X, "type": ..., "note": ...}, ...}
        }
    """
    relationships = _load_relationships()
    indirect = {}

    for ticker in direct_tickers:
        graph_entry = relationships.get(ticker)
        if not graph_entry:
            continue
        for related_ticker in graph_entry.get("related", []):
            if related_ticker in direct_tickers:
                continue
            # Don't overwrite an existing mapping from an earlier direct ticker
            indirect.setdefault(related_ticker, {
                "related_to": ticker,
                "type": graph_entry.get("type", "related"),
                "note": graph_entry.get("note", ""),
            })

    return {"direct": direct_tickers, "indirect": indirect}
