"""
Generates a simple price + volume chart image from yfinance data — no
third-party charting API needed (no TradingView/Finviz scraping, which is
both legally murky and fragile). The chart is built entirely from data
you're already pulling, then handed to Gemini's vision capability for
pattern reading.
"""
import base64
import io
import matplotlib
matplotlib.use("Agg")  # headless backend, no display needed (works in GitHub Actions)
import matplotlib.pyplot as plt
import yfinance as yf


def generate_chart_image(ticker: str, period: str = "3mo") -> str | None:
    """
    Returns a base64-encoded PNG image (no data: prefix) of the ticker's
    recent price + volume, or None if data couldn't be fetched.
    """
    try:
        hist = yf.Ticker(ticker).history(period=period)
    except Exception as e:
        print(f"[chart_generator] Error fetching history for {ticker}: {e}")
        return None

    if hist.empty or len(hist) < 10:
        return None

    fig, (price_ax, volume_ax) = plt.subplots(
        2, 1, figsize=(8, 5), sharex=True,
        gridspec_kw={"height_ratios": [3, 1]},
    )

    price_ax.plot(hist.index, hist["Close"], color="#1f77b4", linewidth=1.5, label="Close")
    # simple moving averages, common reference lines for trend reading
    if len(hist) >= 20:
        price_ax.plot(hist.index, hist["Close"].rolling(20).mean(), color="orange", linewidth=1, label="20-day MA")
    if len(hist) >= 50:
        price_ax.plot(hist.index, hist["Close"].rolling(50).mean(), color="green", linewidth=1, label="50-day MA")
    price_ax.set_title(f"{ticker} — {period} price & volume")
    price_ax.legend(loc="upper left", fontsize=8)
    price_ax.grid(alpha=0.3)

    volume_ax.bar(hist.index, hist["Volume"], color="#888888", width=1.0)
    volume_ax.set_ylabel("Volume", fontsize=8)
    volume_ax.grid(alpha=0.3)

    fig.tight_layout()

    buf = io.BytesIO()
    fig.savefig(buf, format="png", dpi=100)
    plt.close(fig)
    buf.seek(0)

    return base64.b64encode(buf.read()).decode("utf-8")
