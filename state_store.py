"""
Local file-based state store for Phase 1.

Interface is intentionally minimal so swapping in Supabase (persistent state)
and Redis (hot cache / dedup) later is a drop-in replacement:
    - get_state(ticker) -> dict
    - update_state(ticker, patch: dict)
    - has_seen(news_id) -> bool
    - mark_seen(news_id)
"""
import json
import os
from datetime import datetime, timezone
from config import Config


def _load(path, default):
    if not os.path.exists(path):
        return default
    with open(path, "r") as f:
        try:
            return json.load(f)
        except json.JSONDecodeError:
            return default


def _save(path, data):
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "w") as f:
        json.dump(data, f, indent=2)


class StateStore:
    def __init__(self):
        self.state_path = Config.STATE_PATH
        self.seen_path = Config.SEEN_NEWS_PATH

    def get_state(self, ticker: str) -> dict:
        state = _load(self.state_path, {})
        return state.get(ticker, {})

    def update_state(self, ticker: str, patch: dict):
        state = _load(self.state_path, {})
        existing = state.get(ticker, {})
        existing.update(patch)
        existing["last_updated"] = datetime.now(timezone.utc).isoformat()
        state[ticker] = existing
        _save(self.state_path, state)

    def has_seen(self, news_id: str) -> bool:
        seen = _load(self.seen_path, [])
        return news_id in seen

    def mark_seen(self, news_id: str):
        seen = _load(self.seen_path, [])
        seen.append(news_id)
        # keep last 2000 ids to bound file size
        seen = seen[-2000:]
        _save(self.seen_path, seen)
