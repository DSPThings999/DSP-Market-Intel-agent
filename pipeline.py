"""
Orchestrates one run of the market intelligence pipeline ($0/month stack):
  1. Fetch company news per watchlist ticker (Finnhub, free)
  2. Normalize
  3. Skip already-seen items
  4. Resolve direct + graph-based indirect tickers
  5. Pull price/volume/volatility context (yfinance, free)
  6. Classify via Grok (or Claude, once switched)
  7. VERIFY the classification (the "agentic" check — the model decides for
     itself whether its own verdict is trustworthy or needs escalation)
  8. Update per-ticker internal state
  9. Route alerts by priority (urgent = immediate; watch/low = batched);
     escalated items also get logged for future deep-research follow-up (Phase 5)

Designed to run as a single GitHub Actions job (see .github/workflows/market_intel.yml)
rather than a long-running always-on service.
"""
import json
from config import Config
from ingestion.finnhub_client import fetch_company_news, normalize_finnhub_item
from ingestion.yfinance_client import get_price_context
from ticker_mapper import resolve_tickers
from classifier import classify_news_item, verify_classification
from state_store import StateStore
from alerting.telegram_bot import format_alert, send_telegram_message


def load_watchlist() -> list[str]:
    with open(Config.WATCHLIST_PATH, "r") as f:
        return json.load(f)["tickers"]


def _log_escalation(news_item: dict, ticker: str, verdict_impact: dict, reason: str):
    """
    Appends a flagged item to data/escalation_queue.json. No deep-research
    agent consumes this yet (that's Phase 5) — for now this just makes the
    hard cases visible instead of silently trusting every verdict.
    """
    try:
        with open(Config.ESCALATION_QUEUE_PATH, "r") as f:
            queue = json.load(f)
    except (FileNotFoundError, json.JSONDecodeError):
        queue = []

    queue.append({
        "ticker": ticker,
        "headline": news_item.get("headline", ""),
        "url": news_item.get("url", ""),
        "classification": verdict_impact.get("classification"),
        "confidence": verdict_impact.get("confidence"),
        "priority": verdict_impact.get("priority"),
        "escalation_reason": reason,
    })
    queue = queue[-500:]  # bound file size

    with open(Config.ESCALATION_QUEUE_PATH, "w") as f:
        json.dump(queue, f, indent=2)


def run_cycle():
    store = StateStore()
    watchlist = load_watchlist()

    watch_batch = []
    low_batch = []
    processed = 0
    escalated = 0

    for ticker in watchlist:
        raw_items = fetch_company_news(ticker)
        print(f"[pipeline] {ticker}: fetched {len(raw_items)} raw news items.")

        price_context = get_price_context(ticker)

        for raw in raw_items:
            news_item = normalize_finnhub_item(raw, direct_ticker=ticker)
            news_id = news_item["id"]

            if not news_id or store.has_seen(news_id):
                continue

            ticker_context = resolve_tickers(news_item["direct_tickers"])
            result = classify_news_item(news_item, ticker_context, price_context)
            store.mark_seen(news_id)

            if not result:
                continue

            processed += 1

            for affected_ticker, impact in result.get("impact", {}).items():
                # --- the agentic check: let the model judge its own verdict ---
                verification = verify_classification(news_item, ticker_context, price_context, impact)

                if verification and verification.get("needs_escalation"):
                    escalated += 1
                    reason = verification.get("escalation_reason", "")
                    _log_escalation(news_item, affected_ticker, impact, reason)
                    print(f"[pipeline] {affected_ticker}: flagged for escalation — {reason}")
                    # Escalated items still get stored + alerted below, just
                    # tagged, since there's no deep-research follow-up yet to
                    # replace the verdict with. This makes the gap visible
                    # instead of silently dropping or silently trusting it.

                store.update_state(affected_ticker, {
                    "last_headline": news_item["headline"],
                    "last_classification": impact.get("classification"),
                    "last_reasoning": impact.get("reasoning"),
                    "last_confidence": impact.get("confidence"),
                    "last_escalated": bool(verification and verification.get("needs_escalation")),
                })

                priority = impact.get("priority", "low")
                alert_text = format_alert(news_item, affected_ticker, impact)
                if verification and verification.get("needs_escalation"):
                    alert_text = "⚠️ *Flagged for review — verdict may need deeper research*\n" + alert_text

                if priority == "urgent":
                    send_telegram_message(alert_text)
                elif priority == "watch":
                    watch_batch.append(alert_text)
                else:
                    low_batch.append(alert_text)

    if watch_batch:
        send_telegram_message("🟡 *Watch batch:*\n\n" + "\n\n---\n\n".join(watch_batch))
    if low_batch:
        print(f"[pipeline] {len(low_batch)} low-priority items queued for daily digest (not yet implemented).")

    print(f"[pipeline] Cycle complete. {processed} new items classified, {escalated} flagged for escalation.")


if __name__ == "__main__":
    run_cycle()
