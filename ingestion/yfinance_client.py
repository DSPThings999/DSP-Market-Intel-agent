"""
Price/volume/volatility context via yfinance (free, unofficial, no API key).
This fills the raw_signals fields (price_trend, volume_trend, volatility) that
Polygon would otherwise have provided, at zero cost.
"""
import yfinance as yf


def get_hourly_change(ticker: str) -> dict:
    """
    Returns the approximate price change over the last available hour of
    trading (intraday), used for the "what happened in the last hour" line
    in per-ticker reports. Returns empty values outside market hours or if
    intraday data isn't available (yfinance intraday data can be sparse).
    """
    try:
        intraday = yf.Ticker(ticker).history(period="1d", interval="1h")
    except Exception as e:
        print(f"[yfinance_client] Error fetching hourly data for {ticker}: {e}")
        return {"hourly_change_pct": None, "hourly_volume": None}

    if intraday.empty or len(intraday) < 2:
        return {"hourly_change_pct": None, "hourly_volume": None}

    last_close = intraday["Close"].iloc[-1]
    prev_close = intraday["Close"].iloc[-2]
    change_pct = ((last_close - prev_close) / prev_close) * 100 if prev_close else None

    return {
        "hourly_change_pct": round(change_pct, 2) if change_pct is not None else None,
        "hourly_volume": int(intraday["Volume"].iloc[-1]),
    }


def get_price_context(ticker: str) -> dict:
    """
    Returns a lightweight snapshot used as classification context:
      - price_trend: up/down/flat over the last 5 sessions
      - volume_trend: normal/unusual (today's volume vs 20-day average)
      - volatility: rough label based on recent daily range vs price
      - market_cap: latest market capitalization in USD, or None if unavailable

    market_cap comes from yfinance's `.info` lookup, which is flakier than the
    plain price-history call above (slower, more prone to empty/blocked
    responses). It's fetched separately so a failure here doesn't take down
    price_trend/volume_trend/volatility, which are more reliable.
    """
    try:
        hist = yf.Ticker(ticker).history(period="1mo")
    except Exception as e:
        print(f"[yfinance_client] Error fetching history for {ticker}: {e}")
        return {"price_trend": "", "volume_trend": "", "volatility": "", "market_cap": None}

    if hist.empty or len(hist) < 6:
        return {"price_trend": "", "volume_trend": "", "volatility": "", "market_cap": None}

    closes = hist["Close"]
    volumes = hist["Volume"]

    pct_change_5d = (closes.iloc[-1] - closes.iloc[-6]) / closes.iloc[-6] * 100
    if pct_change_5d > 1.5:
        price_trend = "up"
    elif pct_change_5d < -1.5:
        price_trend = "down"
    else:
        price_trend = "flat"

    avg_volume_20d = volumes.iloc[-20:].mean() if len(volumes) >= 20 else volumes.mean()
    today_volume = volumes.iloc[-1]
    volume_trend = "unusual" if today_volume > (avg_volume_20d * 1.5) else "normal"

    daily_range_pct = ((hist["High"] - hist["Low"]) / hist["Close"]).iloc[-5:].mean() * 100
    if daily_range_pct > 4:
        volatility = "high"
    elif daily_range_pct > 2:
        volatility = "moderate"
    else:
        volatility = "low"

    market_cap = None
    try:
        info = yf.Ticker(ticker).info
        market_cap = info.get("marketCap")
    except Exception as e:
        print(f"[yfinance_client] Error fetching market cap for {ticker} (non-fatal): {e}")

    current_price = round(float(closes.iloc[-1]), 2)

    return {
        "price_trend": price_trend,
        "volume_trend": volume_trend,
        "volatility": volatility,
        "market_cap": market_cap,
        "current_price": current_price,
    }
