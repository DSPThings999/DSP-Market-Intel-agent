"""
Calls an AI model using the market-intelligence system prompt to turn a
normalized news item + ticker relationship context into the structured
JSON verdict.

Supports three providers, switched via CLASSIFIER_PROVIDER in .env:
  - "gemini" (ACTIVE by default — genuinely free forever, no card required,
    no expiration, via Google AI Studio. Uses native JSON-schema enforcement,
    so output is more reliably valid JSON than prompt-only approaches.)
  - "grok"   (kept — promo-credit based, NOT permanently free, see below)
  - "claude" (commented out below — swap back in once ready)

NOTE on Grok: xAI's free credits are promotional ($25 one-time, or $150/month
only if you opt into data sharing) — not a permanent free tier like Gemini's.
NOTE on Gemini: free-tier inputs/outputs may be used by Google to improve
their models. Fine for public financial news headlines; worth knowing if you
ever feed it anything sensitive.
"""
import json
import requests
from config import Config

with open(Config.SYSTEM_PROMPT_PATH, "r") as f:
    SYSTEM_PROMPT = f.read()


def _build_user_payload(news_item: dict, ticker_context: dict, price_context: dict | None = None) -> str:
    payload = {
        "news": {
            "headline": news_item.get("headline", ""),
            "source": news_item.get("source", ""),
            "timestamp": news_item.get("timestamp", ""),
            "summary": news_item.get("summary", ""),
            "url": news_item.get("url", ""),
        },
        "direct_tickers": ticker_context.get("direct", []),
        "indirect_tickers_from_graph": ticker_context.get("indirect", {}),
        "price_volume_context": price_context or {},
        "note": (
            "direct_tickers were explicitly mentioned in the news. "
            "indirect_tickers_from_graph are graph-confirmed relationships "
            "(e.g. supplier/competitor) — treat these as high-confidence "
            "candidates for ripple-effect classification, not guesses. "
            "price_volume_context reflects the primary direct ticker only "
            "(free-tier data via yfinance) and includes current_price; leave "
            "chart-related fields empty only if no chart image was attached. "
            "market_cap may be null if unavailable this cycle — treat that as "
            "missing data, not as a signal itself."
        ),
    }
    return json.dumps(payload, indent=2)


def _extract_json(raw_text: str) -> dict | None:
    raw_text = raw_text.strip()
    if raw_text.startswith("```"):
        raw_text = raw_text.strip("`")
        if raw_text.startswith("json"):
            raw_text = raw_text[4:]
    try:
        return json.loads(raw_text)
    except json.JSONDecodeError as e:
        print(f"[classifier] Failed to parse JSON response: {e}")
        return None


# ---------------------------------------------------------------------------
# ACTIVE PROVIDER: Gemini (Google AI Studio) — free forever, no card, no
# expiration. Uses native responseMimeType: "application/json" so Gemini
# enforces valid JSON output rather than just being asked nicely for it.
# ---------------------------------------------------------------------------
def _classify_with_gemini(system_prompt: str, user_payload: str, image_b64: str | None = None) -> dict | None:
    url = (
        f"https://generativelanguage.googleapis.com/v1beta/models/"
        f"{Config.GEMINI_MODEL}:generateContent?key={Config.GEMINI_API_KEY}"
    )
    parts = [{"text": user_payload}]
    if image_b64:
        parts.append({"inline_data": {"mime_type": "image/png", "data": image_b64}})
    body = {
        "system_instruction": {"parts": [{"text": system_prompt}]},
        "contents": [{"role": "user", "parts": parts}],
        "generationConfig": {"responseMimeType": "application/json"},
    }
    try:
        resp = requests.post(url, json=body, timeout=30)
        resp.raise_for_status()
        raw_text = resp.json()["candidates"][0]["content"]["parts"][0]["text"]
        return _extract_json(raw_text)
    except (requests.RequestException, KeyError, IndexError) as e:
        print(f"[classifier] Gemini request failed: {e}")
        return None


# ---------------------------------------------------------------------------
# KEPT, NOT DEFAULT: Grok (xAI), OpenAI-compatible chat completions endpoint.
# Free credits are promotional, not permanent — see note at top of file.
# ---------------------------------------------------------------------------
def _classify_with_grok(system_prompt: str, user_payload: str) -> dict | None:
    url = "https://api.x.ai/v1/chat/completions"
    headers = {
        "Authorization": f"Bearer {Config.GROK_API_KEY}",
        "Content-Type": "application/json",
    }
    body = {
        "model": Config.GROK_MODEL,
        "messages": [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_payload},
        ],
    }
    try:
        resp = requests.post(url, headers=headers, json=body, timeout=30)
        resp.raise_for_status()
        raw_text = resp.json()["choices"][0]["message"]["content"]
        return _extract_json(raw_text)
    except (requests.RequestException, KeyError, IndexError) as e:
        print(f"[classifier] Grok request failed: {e}")
        return None


# ---------------------------------------------------------------------------
# COMMENTED OUT FOR NOW: Claude (Anthropic). Swap CLASSIFIER_PROVIDER to
# "claude" in .env and uncomment this block (+ the import + client below)
# once you're ready to move off the free-tier providers.
# ---------------------------------------------------------------------------
# import anthropic
# _anthropic_client = anthropic.Anthropic(api_key=Config.ANTHROPIC_API_KEY)
#
# def _classify_with_claude(system_prompt: str, user_payload: str) -> dict | None:
#     try:
#         response = _anthropic_client.messages.create(
#             model=Config.CLASSIFIER_MODEL,
#             max_tokens=1500,
#             system=system_prompt,
#             messages=[{"role": "user", "content": user_payload}],
#         )
#         raw_text = "".join(
#             block.text for block in response.content if block.type == "text"
#         )
#         return _extract_json(raw_text)
#     except anthropic.APIError as e:
#         print(f"[classifier] Claude request failed: {e}")
#         return None


def _dispatch(system_prompt: str, user_payload: str, image_b64: str | None = None) -> dict | None:
    if Config.CLASSIFIER_PROVIDER == "gemini":
        return _classify_with_gemini(system_prompt, user_payload, image_b64)
    elif Config.CLASSIFIER_PROVIDER == "grok":
        return _classify_with_grok(system_prompt, user_payload)  # image support not wired for Grok yet
    elif Config.CLASSIFIER_PROVIDER == "claude":
        raise NotImplementedError(
            "CLASSIFIER_PROVIDER is set to 'claude' but the Claude code path is "
            "commented out in classifier.py. Uncomment the _classify_with_claude "
            "block and the anthropic import/client above, then remove this guard."
        )
    else:
        raise ValueError(f"Unknown CLASSIFIER_PROVIDER: {Config.CLASSIFIER_PROVIDER}")


def classify_news_item(
    news_item: dict,
    ticker_context: dict,
    price_context: dict | None = None,
    chart_image_b64: str | None = None,
) -> dict | None:
    """Returns a parsed JSON dict matching the agent's output schema, or None on failure."""
    user_payload = _build_user_payload(news_item, ticker_context, price_context)
    return _dispatch(SYSTEM_PROMPT, user_payload, chart_image_b64)


# ---------------------------------------------------------------------------
# VERIFICATION STEP (the "agentic" check): the model decides for itself
# whether its own classification is trustworthy, or should be escalated for
# deeper research (Phase 5) before anyone acts on it.
# ---------------------------------------------------------------------------
with open(Config.VERIFICATION_PROMPT_PATH, "r") as f:
    VERIFICATION_PROMPT = f.read()


def _build_verification_payload(news_item: dict, ticker_context: dict, price_context: dict, verdict: dict) -> str:
    payload = {
        "news": {
            "headline": news_item.get("headline", ""),
            "summary": news_item.get("summary", ""),
        },
        "ticker_context": ticker_context,
        "price_volume_context": price_context or {},
        "verdict_to_check": verdict,
    }
    return json.dumps(payload, indent=2)


def verify_classification(news_item: dict, ticker_context: dict, price_context: dict, verdict: dict) -> dict | None:
    """
    Runs the verification check. Returns a dict like:
        {"confirmed": bool, "needs_escalation": bool, "escalation_reason": str}
    or None on failure (caller should treat None as "pass through unverified"
    rather than blocking the alert — verification is a safety net, not a gate).
    """
    user_payload = _build_verification_payload(news_item, ticker_context, price_context, verdict)
    return _dispatch(VERIFICATION_PROMPT, user_payload)


# ---------------------------------------------------------------------------
# PER-TICKER DIGEST REPORT: one-liner status, directional lean (NOT trading
# advice), volume note, latest news, last-hour effect, chart read, and a
# clearly-labeled speculative next-day outlook. Supports an optional chart
# image (base64 PNG from ingestion/chart_generator.py) via Gemini's vision
# input — only implemented for the Gemini path, since that's the active
# default; Grok/Claude image support can be added the same way later if you
# switch providers.
# ---------------------------------------------------------------------------
with open(Config.DAILY_REPORT_PROMPT_PATH, "r") as f:
    DAILY_REPORT_PROMPT = f.read()


def _build_report_payload(ticker: str, state: dict, price_context: dict, hourly_context: dict) -> str:
    payload = {
        "ticker": ticker,
        "last_known_state": state or {},
        "price_volume_context": price_context or {},
        "last_hour_context": hourly_context or {},
        "note": (
            "last_known_state reflects the most recent classified news for "
            "this ticker (may be several hours/days old if nothing new has "
            "happened). Missing/null fields mean no data was available this "
            "cycle — treat as missing, not as a signal."
        ),
    }
    return json.dumps(payload, indent=2)


def generate_ticker_report(
    ticker: str,
    state: dict,
    price_context: dict,
    hourly_context: dict,
    chart_image_b64: str | None = None,
) -> dict | None:
    """Returns a parsed JSON dict matching the daily report schema, or None on failure."""
    user_payload = _build_report_payload(ticker, state, price_context, hourly_context)

    if Config.CLASSIFIER_PROVIDER == "gemini":
        url = (
            f"https://generativelanguage.googleapis.com/v1beta/models/"
            f"{Config.GEMINI_MODEL}:generateContent?key={Config.GEMINI_API_KEY}"
        )
        parts = [{"text": user_payload}]
        if chart_image_b64:
            parts.append({
                "inline_data": {
                    "mime_type": "image/png",
                    "data": chart_image_b64,
                }
            })
        body = {
            "system_instruction": {"parts": [{"text": DAILY_REPORT_PROMPT}]},
            "contents": [{"role": "user", "parts": parts}],
            "generationConfig": {"responseMimeType": "application/json"},
        }
        try:
            resp = requests.post(url, json=body, timeout=30)
            resp.raise_for_status()
            raw_text = resp.json()["candidates"][0]["content"]["parts"][0]["text"]
            return _extract_json(raw_text)
        except (requests.RequestException, KeyError, IndexError) as e:
            print(f"[classifier] Gemini report request failed: {e}")
            return None
    else:
        # Chart image support is Gemini-only for now. Non-image providers
        # still get a text-only report (chart_read will just be empty).
        return _dispatch(DAILY_REPORT_PROMPT, user_payload)
