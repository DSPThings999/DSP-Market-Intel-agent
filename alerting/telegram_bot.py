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

    current_price = impact.get("current_price")
    price_line = f"Current price: ${current_price}" if current_price is not None else "Current price: n/a"

    expected_range = impact.get("expected_price_range", "")
    expected_line = f"Speculative next-session range: {expected_range}" if expected_range else ""

    chart_read = impact.get("chart_read", "")
    chart_line = f"Chart read: {chart_read}" if chart_read else ""

    lines = [
        f"{priority_icon} {impact_icon} *{ticker}* — {impact.get('classification', 'Uncertain')}",
        f"_{news_item.get('headline', '')}_",
        "",
        impact.get("reasoning", ""),
        "",
        price_line,
    ]
    if expected_line:
        lines.append(expected_line)
    if chart_line:
        lines.append(chart_line)
    lines += [
        "",
        f"Source: {news_item.get('source', '')}",
        f"Confidence: {impact.get('confidence', 0.0)}",
        "",
        "_Not financial advice — an AI's read of current data, not a guaranteed prediction._",
    ]

    return "\n".join(lines)


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
