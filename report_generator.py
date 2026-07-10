"""
Builds the per-cycle digest: one line per watchlist ticker (status, lean,
volume, last-hour move, chart read, speculative next-day outlook), plus a
plain listing of sector/country-wide ripple effects across the watchlist.

This runs every cycle for every ticker (not just ones with fresh news), since
you asked for a standing report — not just event-driven alerts. Cost-wise,
this means one classify-style API call PER ticker per run, regardless of
whether anything happened; keep that in mind if the watchlist grows large
(see README cost notes).
"""
import json
from config import Config
from ingestion.yfinance_client import get_price_context, get_hourly_change
from ingestion.chart_generator import generate_chart_image
from ticker_mapper import resolve_tickers
from classifier import generate_ticker_report
from state_store import StateStore


def load_watchlist() -> list[str]:
    with open(Config.WATCHLIST_PATH, "r") as f:
        return json.load(f)["tickers"]


def build_relationship_section(watchlist: list[str]) -> str:
    """
    Plain-text listing of every sector/country/company-level ripple effect
    across the current watchlist — no cap on how many are listed.
    """
    lines = []
    seen_pairs = set()

    for ticker in watchlist:
        context = resolve_tickers([ticker])
        for related_ticker, info in context["indirect"].items():
            pair_key = tuple(sorted([ticker, related_ticker]))
            if pair_key in seen_pairs:
                continue
            seen_pairs.add(pair_key)
            level = info["level"]
            lines.append(f"• {ticker} <-> {related_ticker} ({level}): {info['note']}")

    if not lines:
        return "No sector/company/country relationships found for the current watchlist (check data/relationships.json)."
    return "\n".join(lines)


def build_digest():
    store = StateStore()
    watchlist = load_watchlist()
    report_lines = []

    for ticker in watchlist:
        state = store.get_state(ticker)
        price_context = get_price_context(ticker)
        hourly_context = get_hourly_change(ticker)
        chart_image = generate_chart_image(ticker)

        report = generate_ticker_report(ticker, state, price_context, hourly_context, chart_image)

        if not report:
            report_lines.append(f"WARNING {ticker}: report generation failed this cycle.")
            continue

        report_lines.append(
            f"*{report.get('ticker', ticker)}* - {report.get('directional_lean', 'Neutral/Mixed')}\n"
            f"{report.get('one_liner', '')}\n"
            f"Volume: {report.get('volume_note', 'n/a')} | Last hour: {report.get('last_hour_effect', 'n/a')}\n"
            f"News: {report.get('latest_news_summary', 'no recent data')}\n"
            f"Chart: {report.get('chart_read', 'n/a')}\n"
            f"Next-day outlook (speculative): {report.get('next_day_outlook', 'n/a')}"
        )

    relationship_section = build_relationship_section(watchlist)

    digest = (
        "Watchlist Digest\n\n"
        + "\n\n---\n\n".join(report_lines)
        + "\n\nSector / Company / Country ripple effects\n"
        + relationship_section
        + "\n\nNot financial advice - an AI's read of current data, not a guaranteed prediction."
    )
    return digest
