import os
from dotenv import load_dotenv

load_dotenv()


class Config:
    # Optional/legacy — only needed if you later upgrade off the free-tier stack
    POLYGON_API_KEY = os.getenv("POLYGON_API_KEY", "")

    FINNHUB_API_KEY = os.getenv("FINNHUB_API_KEY", "")

    # --- AI classifier provider switch ---
    # "grok" (active, free-credit tier while prototyping) or "claude" (commented out in classifier.py for now)
    CLASSIFIER_PROVIDER = os.getenv("CLASSIFIER_PROVIDER", "grok")

    GROK_API_KEY = os.getenv("GROK_API_KEY", "")
    GROK_MODEL = os.getenv("GROK_MODEL", "grok-4.3")

    ANTHROPIC_API_KEY = os.getenv("ANTHROPIC_API_KEY", "")
    CLASSIFIER_MODEL = os.getenv("CLASSIFIER_MODEL", "claude-haiku-4-5-20251001")

    TELEGRAM_BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN", "")
    TELEGRAM_CHAT_ID = os.getenv("TELEGRAM_CHAT_ID", "")

    POLL_INTERVAL_MINUTES = int(os.getenv("POLL_INTERVAL_MINUTES", "5"))

    WATCHLIST_PATH = os.path.join(os.path.dirname(__file__), "data", "watchlist.json")
    RELATIONSHIPS_PATH = os.path.join(os.path.dirname(__file__), "data", "relationships.json")
    STATE_PATH = os.path.join(os.path.dirname(__file__), "data", "state.json")
    SEEN_NEWS_PATH = os.path.join(os.path.dirname(__file__), "data", "seen_news.json")

    SYSTEM_PROMPT_PATH = os.path.join(
        os.path.dirname(__file__), "prompts", "market_intelligence_system_prompt.md"
    )
    VERIFICATION_PROMPT_PATH = os.path.join(
        os.path.dirname(__file__), "prompts", "verification_prompt.md"
    )
    ESCALATION_QUEUE_PATH = os.path.join(
        os.path.dirname(__file__), "data", "escalation_queue.json"
    )
