# Market Intelligence Agent — Phase 1 Skeleton ($0/month stack)

Free-tier, GitHub-Actions-scheduled skeleton for the real-time market intelligence agent.
This replaces the originally-discussed Polygon.io ($29+/mo) + Railway/Render (always-on
hosting) combo with a stack that costs nothing to run at watchlist-scale:

| Layer            | Original plan          | This build                          | Cost   |
|------------------|-------------------------|--------------------------------------|--------|
| News             | Polygon.io Starter       | Finnhub free tier (company + general news) | $0 |
| Price/volume     | Polygon.io               | yfinance (unofficial, no key)         | $0     |
| Hosting/scheduler| Railway/Render always-on | GitHub Actions cron (`workflow_dispatch` + schedule) | $0 (public repo) |
| State/dedup      | Redis + Supabase         | JSON files, committed back to repo by the Action | $0 |
| Classification   | Claude Haiku (active)    | **Gemini Flash-Lite (active, free forever)** — Grok also wired up (promo credits only), Claude kept commented out | Gemini: genuinely $0, no card, no expiration |
| Alerting         | Telegram Bot API         | Telegram Bot API                      | $0     |

Supabase/Redis aren't gone forever — they're a clean upgrade path once git-committed
JSON state stops being enough (e.g. watchlist grows past ~20-30 tickers, or you want
multi-writer safety). The `state_store.py` interface is written so that swap doesn't
touch `pipeline.py`.

## Roadmap context

- **Phase 1 (this)** — free-tier API setup, GitHub Actions scheduling, JSON output
- **Phase 2** — Supabase/Redis if/when git-committed JSON becomes a bottleneck
- **Phase 3** — bigger relationship graph, big-news rule engine tuning
- **Phase 4** — true 30-min watch batching + daily digest for `low` priority
- **Phase 5** — deep research: Claude Sonnet, Claude Vision chart reading, TradingView dashboard
- **Phase 6** — backtesting and tuning

## What's included

```
market-intel-agent/
├── .github/workflows/market_intel.yml   # scheduled runner (replaces Railway/Render)
├── main.py                    # LOCAL TESTING ONLY - loop for manual dev runs
├── pipeline.py                 # one full fetch→classify→alert cycle
├── config.py                    # env-driven config
├── ticker_mapper.py              # direct + graph-based indirect ticker resolution
├── state_store.py                # local JSON state, committed by the Action
├── ingestion/
│   ├── finnhub_client.py           # free-tier news + earnings + recommendations
│   └── yfinance_client.py            # free price/volume/volatility context
├── optional_upgrades/
│   └── polygon_client.py              # kept for later — not used by default
├── classifier.py                # Claude Haiku call using the system prompt
├── alerting/
│   └── telegram_bot.py                 # priority-based Telegram formatting + send
├── prompts/
│   └── market_intelligence_system_prompt.md
└── data/
    ├── watchlist.json             # tickers to monitor
    ├── relationships.json          # ticker relationship graph (edit to expand)
    ├── state.json                  # generated + committed by the Action
    └── seen_news.json              # generated + committed by the Action (dedup log)
```

## AI classifier: Gemini active (free forever), Grok and Claude ready to swap in

`classifier.py` supports three providers behind `CLASSIFIER_PROVIDER` in `.env`:

- **`gemini` (active default)** — Google AI Studio's Gemini API. Genuinely free
  forever: no card, no expiration, unlike promo-credit-based free tiers. Uses
  Gemini's native JSON-schema enforcement (`responseMimeType: application/json`),
  so output is more reliably valid JSON than "please just return JSON" prompting.
  Caveat: Google may use free-tier inputs/outputs to improve their products —
  fine for public financial news, worth knowing regardless.
- **`grok`** — fully wired up, kept as an option. xAI's free credits are
  promotional ($25 one-time, or $150/month only with data-sharing opted in) —
  not a permanent free tier like Gemini's.
- **`claude`** — written but commented out in `classifier.py`. To switch:
  uncomment the `_classify_with_claude` function and the `anthropic`
  import/client above it, set `CLASSIFIER_PROVIDER=claude` in `.env` (and in
  the GitHub Actions workflow's `env:` block), and uncomment the
  `ANTHROPIC_API_KEY` line there too.

## The verification step (a small, real, agentic check)

After classification, `pipeline.py` calls `verify_classification()` — a second AI
call where the model reviews its own verdict and decides, for itself, whether it's
trustworthy or should be flagged. This is a genuine agentic decision (the model
choosing an outcome, not your code deciding in advance), just not a full
tool-calling research loop yet — that's still Phase 5.

- Flagged items get logged to `data/escalation_queue.json` (nothing consumes
  this queue yet — it just makes the hard cases visible instead of silently
  trusting every verdict).
- Alerts for flagged items get a "⚠️ Flagged for review" prefix so you can
  tell at a glance which verdicts deserve a second look.
- This roughly doubles classifier API calls (one classify + one verify per
  news item), so double the per-item cost estimates from the cost breakdown
  above when budgeting.

## Reliability: rate-limit retries + reduced call volume

Earlier versions of the digest made a *second* full round of Gemini calls
(one per ticker, with a chart image) purely for the standing report, on top
of the classify/verify calls already happening for fresh news — this reliably
triggered Gemini's free-tier rate limit partway through a run, causing later
tickers to silently fail.

Two fixes:
- **`report_generator.py` no longer calls any AI model.** The digest is built
  entirely from `data/state.json`, which the main classification step
  (`pipeline.py` + `classifier.py`) already populates with everything needed
  (headline, classification, confidence, current price, expected range, chart
  read). This roughly halves API calls per cycle.
- **`classifier.py`'s Gemini calls now retry with backoff** on rate-limit
  (429) responses, and `pipeline.py` adds a short delay between watchlist
  tickers, so even under load the pipeline degrades gracefully instead of
  silently failing.

## The digest, grouped by sector

Each cycle's digest now groups your watchlist by sector (from
`data/relationships.json`), highlights the single biggest/most important news
item per sector, then lists every ticker in that sector with its current
price, speculative range, chart read, and which related tickers (company,
sector, or country level) might also be affected — instead of one flat,
repetitive list.

## Macro/general news scanning

`ingestion/finnhub_client.py`'s `fetch_general_news()` (written earlier but
unused) is now wired into `pipeline.py` — broad market/macro news (Fed
moves, sector-wide events) gets classified against your whole watchlist at
once, since it isn't tied to one specific ticker. This is in addition to,
not instead of, the per-ticker company news scanning.

## Setup

1. Push this to a GitHub repo (public repo = unlimited free Actions minutes;
   private repo = 2,000 free minutes/month, still plenty at 15-min polling).
2. In repo Settings → Secrets and variables → Actions, add:
   `FINNHUB_API_KEY`, `GEMINI_API_KEY`, `TELEGRAM_BOT_TOKEN`, `TELEGRAM_CHAT_ID`
   (same pattern as your existing stock-analysis repo's `EMAIL_*` secrets).
   `GROK_API_KEY` and `ANTHROPIC_API_KEY` are only needed if you switch providers.
3. Edit `data/watchlist.json` and `data/relationships.json` for your actual tickers
   and known relationships (competitors, suppliers, customers, ETFs).
4. Trigger the workflow manually once via Actions → Market Intelligence Agent →
   "Run workflow" to confirm it works before relying on the schedule.

### Local testing (optional)
```bash
pip install -r requirements.txt
cp .env.example .env   # fill in the same keys as above
python pipeline.py      # runs one cycle
python main.py          # loops locally every POLL_INTERVAL_MINUTES, for dev only
```

## Notes on what's deliberately NOT in this skeleton yet

- **Chart reading / technical indicators** — explicitly deferred to Phase 5
  (Claude Vision + a chart data source). `raw_signals` chart/technical fields
  come back empty on purpose.
- **`watch` batching on a true 30-min timer** — currently batches only within
  one Action run (one poll). True time-windowed batching is a Phase 4 tweak.
- **`low` priority daily digest** — logged, not sent yet. Needs a second,
  once-daily workflow trigger in Phase 4.
- **Finnhub free-tier rate limits** — 60 calls/min is generous, but a 15-min
  schedule × N tickers × (news + earnings) calls stays well under it even
  with a 20-30 ticker watchlist.
