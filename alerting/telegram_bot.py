"""
Telegram alert delivery with priority-based formatting.
urgent -> sent immediately (called directly from pipeline)
watch/low -> batching is handled by the caller (pipeline.py); this module just sends.
"""
import requests
from config import Config

PRIORITY_EMOJI = {
    "urgent": "🔴",
    "watch": "🟡",
    "low": "⚪",
}

IMPACT_EMOJI = {
    "Bullish": "📈",
    "Bearish": "📉",
    "Uncertain": "❓",
}


def format_alert(news_item: dict, ticker: str, impact: dict) -> str:
    priority_icon = PRIORITY_EMOJI.get(impact.get("priority", "low"), "⚪")
    impact_icon = IMPACT_EMOJI.get(impact.get("classification", "Uncertain"), "❓")

    return (
        f"{priority_icon} {impact_icon} *{ticker}* — {impact.get('classification', 'Uncertain')}\n"
        f"_{news_item.get('headline', '')}_\n\n"
        f"{impact.get('reasoning', '')}\n\n"
        f"Source: {news_item.get('source', '')}\n"
        f"Confidence: {impact.get('confidence', 0.0)}"
    )


def send_telegram_message(text: str):
    if not Config.TELEGRAM_BOT_TOKEN or not Config.TELEGRAM_CHAT_ID:
        print("[telegram_bot] Missing bot token or chat id — skipping send.")
        print(text)
        return

    url = f"https://api.telegram.org/bot{Config.TELEGRAM_BOT_TOKEN}/sendMessage"
    payload = {
        "chat_id": Config.TELEGRAM_CHAT_ID,
        "text": text,
        "parse_mode": "Markdown",
    }
    try:
        resp = requests.post(url, json=payload, timeout=10)
        resp.raise_for_status()
    except requests.RequestException as e:
        print(f"[telegram_bot] Failed to send alert: {e}")
