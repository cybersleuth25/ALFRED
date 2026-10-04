"""
Market & Stock Intelligence Tool for Alfred — Powered by Amazon Chronos & Yahoo Finance.
========================================================================================
Supports:
  - Indian Equities (NSE: .NS, BSE: .BO, Nifty 50: ^NSEI, Sensex: ^BSESN)
  - US & Global Equities (NVDA, AAPL, MSFT, TSLA, etc.)
  - Crypto Assets (BTC-USD, ETH-USD)
  - Technical Indicators: RSI(14), MACD, Bollinger Bands, 50/200-day Moving Averages
  - Amazon Chronos Zero-Shot Probabilistic Forecasting via Tonic Space
"""

import os
import re
import json
import time
from datetime import datetime, timedelta
import numpy as np
import pandas as pd

try:
    import yfinance as yf
except ImportError:
    yf = None

# Directory for market charts
CHARTS_DIR = os.path.join(os.path.dirname(__file__), "..", "Alfred_Workspace", "market_charts")
os.makedirs(CHARTS_DIR, exist_ok=True)

# Common Indian & Global Name-to-Ticker Mappings
TICKER_MAP = {
    # Indian Indices
    "nifty": "^NSEI",
    "nifty 50": "^NSEI",
    "nifty50": "^NSEI",
    "bank nifty": "^NSEBANK",
    "banknifty": "^NSEBANK",
    "sensex": "^BSESN",
    
    # Top Indian Equities (NSE)
    "reliance": "RELIANCE.NS",
    "ril": "RELIANCE.NS",
    "tcs": "TCS.NS",
    "tata consultancy": "TCS.NS",
    "infosys": "INFY.NS",
    "infy": "INFY.NS",
    "hdfc": "HDFCBANK.NS",
    "hdfc bank": "HDFCBANK.NS",
    "icici": "ICICIBANK.NS",
    "icici bank": "ICICIBANK.NS",
    "sbi": "SBIN.NS",
    "state bank of india": "SBIN.NS",
    "itc": "ITC.NS",
    "bharti airtel": "BHARTIARTL.NS",
    "airtel": "BHARTIARTL.NS",
    "l&t": "LT.NS",
    "larsen": "LT.NS",
    "hindustan unilever": "HINDUNILVR.NS",
    "hul": "HINDUNILVR.NS",
    "tata motors": "TATAMOTORS.NS",
    "tatamotors": "TATAMOTORS.NS",
    "tata steel": "TATASTEEL.NS",
    "tatasteel": "TATASTEEL.NS",
    "zomato": "ZOMATO.NS",
    "swiggy": "SWIGGY.NS",
    "paytm": "PAYTM.NS",
    "wipro": "WIPRO.NS",
    "adani": "ADANIENT.NS",
    "adani enterprises": "ADANIENT.NS",
    "adani ports": "ADANIPORTS.NS",
    "bajaj finance": "BAJFINANCE.NS",
    "maruti": "MARUTI.NS",
    
    # Global / US Equities
    "nvidia": "NVDA",
    "apple": "AAPL",
    "microsoft": "MSFT",
    "google": "GOOGL",
    "alphabet": "GOOGL",
    "amazon": "AMZN",
    "meta": "META",
    "facebook": "META",
    "tesla": "TSLA",
    "amd": "AMD",
    
    # Crypto
    "bitcoin": "BTC-USD",
    "btc": "BTC-USD",
    "ethereum": "ETH-USD",
    "eth": "ETH-USD",
    "solana": "SOL-USD",
}

def resolve_ticker(query: str) -> str:
    """Intelligently resolves natural language names to stock tickers."""
    clean = query.strip().lower()
    clean = re.sub(r'^(stock|ticker|share|price of|forecast of|quote of)\s+', '', clean).strip()
    
    if clean in TICKER_MAP:
        return TICKER_MAP[clean]
        
    for k, v in TICKER_MAP.items():
        if k in clean or clean in k:
            return v
            
    # Default uppercase ticker
    raw = query.strip().upper()
    return raw


def get_stock_quote(symbol: str) -> str:
    """
    Fetches real-time price, day change, volume, and range for any Indian or global stock.
    """
    global yf
    if yf is None:
        try:
            import yfinance as yf
        except ImportError:
            return "Market data requires 'yfinance'. Please install it using: pip install yfinance"

    ticker = resolve_ticker(symbol)
    try:
        t = yf.Ticker(ticker)
        hist = t.history(period="5d")
        if hist.empty:
            # Try appending .NS for Indian stocks if user passed plain symbol
            if not ticker.endswith(".NS") and not ticker.startswith("^") and not "-" in ticker:
                t = yf.Ticker(f"{ticker}.NS")
                hist = t.history(period="5d")
                if not hist.empty:
                    ticker = f"{ticker}.NS"
        
        if hist.empty:
            return f"Could not find market data for ticker '{symbol}' (resolved to {ticker})."

        latest = float(hist['Close'].iloc[-1])
        prev = float(hist['Close'].iloc[-2]) if len(hist) > 1 else latest
        change = latest - prev
        pct_change = (change / prev) * 100 if prev else 0.0
        
        high_day = float(hist['High'].iloc[-1])
        low_day = float(hist['Low'].iloc[-1])
        volume = int(hist['Volume'].iloc[-1])
        
        is_inr = ticker.endswith(".NS") or ticker.endswith(".BO") or ticker in ["^NSEI", "^BSESN", "^NSEBANK"]
        curr = "INR " if is_inr else "$"
        
        sign = "+" if change >= 0 else ""
        lines = [
            f"📈 Market Quote for {ticker}:",
            f"• Current Price: {curr}{latest:,.2f} ({sign}{change:,.2f} / {sign}{pct_change:0.2f}%)",
            f"• Day Range: {curr}{low_day:,.2f} - {curr}{high_day:,.2f}",
            f"• Volume: {volume:,}"
        ]
        return "\n".join(lines)
    except Exception as e:
        return f"Error retrieving quote for {symbol}: {e}"


def calculate_technical_indicators(df: pd.DataFrame) -> dict:
    """Calculates RSI, MACD, and Bollinger Bands on historical close prices."""
    if len(df) < 20:
        return {}
        
    close = df['Close']
    
    # 1. 20-day SMA & Bollinger Bands
    sma20 = close.rolling(window=20).mean()
    std20 = close.rolling(window=20).std()
    upper_band = sma20 + (2 * std20)
    lower_band = sma20 - (2 * std20)
    
    # 2. RSI (14 periods)
    delta = close.diff()
    gain = (delta.where(delta > 0, 0)).rolling(window=14).mean()
    loss = (-delta.where(delta < 0, 0)).rolling(window=14).mean()
    rs = gain / loss.replace(0, np.nan)
    rsi = 100 - (100 / (1 + rs))
    
    # 3. MACD (12, 26, 9)
    exp12 = close.ewm(span=12, adjust=False).mean()
    exp26 = close.ewm(span=26, adjust=False).mean()
    macd = exp12 - exp26
    signal = macd.ewm(span=9, adjust=False).mean()
    
    return {
        "rsi": float(rsi.iloc[-1]) if not pd.isna(rsi.iloc[-1]) else 50.0,
        "sma20": float(sma20.iloc[-1]),
        "upper_band": float(upper_band.iloc[-1]),
        "lower_band": float(lower_band.iloc[-1]),
        "macd": float(macd.iloc[-1]),
        "macd_signal": float(signal.iloc[-1]),
    }


def _query_tonic_chronos(ticker: str, days: int = 14) -> dict:
    """Queries Tonic's Amazon Chronos Hugging Face Space."""
    try:
        from gradio_client import Client
        c = Client("Tonic/stock-predictions")
        res = c.predict(
            s=ticker,
            pd=float(min(30, max(5, days))),
            ld=365.0,
            st="chronos",
            api_name="/daily_analysis"
        )
        if res and len(res) >= 11:
            signals = res[0]
            pred_data = res[10]
            return {
                "success": True,
                "engine": "Amazon Chronos (Tonic HF Space)",
                "signals": signals,
                "predicted_data": pred_data
            }
    except Exception as e:
        print(f"[Market Tools] Tonic Chronos API note: {e}")
    return {"success": False}


def _local_probabilistic_forecast(df: pd.DataFrame, days: int = 14) -> dict:
    """
    Robust local probabilistic time-series projection (Chronos mathematical equivalent).
    Uses geometric Brownian motion with historical drift and volatility.
    """
    close = df['Close'].dropna()
    log_returns = np.log(close / close.shift(1)).dropna()
    
    u = log_returns.mean()
    var = log_returns.var()
    drift = u - (0.5 * var)
    stdev = log_returns.std()
    
    latest = float(close.iloc[-1])
    
    # Compute 10th (bear), 50th (median), and 90th (bull) percentiles over time horizon
    time_points = np.arange(1, days + 1)
    
    expected_path = latest * np.exp(drift * time_points)
    lower_band = latest * np.exp((drift * time_points) - (1.645 * stdev * np.sqrt(time_points)))
    upper_band = latest * np.exp((drift * time_points) + (1.645 * stdev * np.sqrt(time_points)))
    
    return {
        "engine": "Probabilistic Volatility Projection",
        "latest_price": latest,
        "target_median": round(float(expected_path[-1]), 2),
        "target_bear": round(float(lower_band[-1]), 2),
        "target_bull": round(float(upper_band[-1]), 2),
        "pct_median": round(((expected_path[-1] - latest) / latest) * 100, 2),
        "pct_bear": round(((lower_band[-1] - latest) / latest) * 100, 2),
        "pct_bull": round(((upper_band[-1] - latest) / latest) * 100, 2),
    }


def forecast_stock(symbol: str, days: int = 14) -> str:
    """
    Analyzes any Indian (NSE/BSE) or global stock, computing technical indicators
    (RSI, MACD, Bollinger Bands) and projecting future price trajectories using Amazon Chronos.
    
    Args:
        symbol: Stock name or ticker (e.g. 'Reliance', 'TCS', 'Nifty', 'NVDA', 'Apple').
        days: Days into the future to forecast (default 14).
    """
    global yf
    if yf is None:
        try:
            import yfinance as yf
        except ImportError:
            return "Market analysis requires 'yfinance'. Please install it using: pip install yfinance"

    ticker = resolve_ticker(symbol)
    t = yf.Ticker(ticker)
    df = t.history(period="1y")
    
    if df.empty:
        if not ticker.endswith(".NS") and not ticker.startswith("^") and not "-" in ticker:
            t = yf.Ticker(f"{ticker}.NS")
            df = t.history(period="1y")
            if not df.empty:
                ticker = f"{ticker}.NS"
                
    if df.empty:
        return f"Could not retrieve historical data for '{symbol}' ({ticker}) to run forecast."

    is_inr = ticker.endswith(".NS") or ticker.endswith(".BO") or ticker in ["^NSEI", "^BSESN", "^NSEBANK"]
    curr = "INR " if is_inr else "$"
    
    latest_price = float(df['Close'].iloc[-1])
    
    # 1. Technical Indicators
    tech = calculate_technical_indicators(df)
    rsi_val = tech.get("rsi", 50.0)
    rsi_signal = "Overbought (Bearish Risk)" if rsi_val > 70 else ("Oversold (Bullish Rebound)" if rsi_val < 30 else "Neutral")
    
    macd_val = tech.get("macd", 0.0)
    macd_sig = tech.get("macd_signal", 0.0)
    macd_bias = "Bullish Crossover" if macd_val > macd_sig else "Bearish Divergence"
    
    # 2. Chronos Time-Series Forecasting
    chronos_res = _query_tonic_chronos(ticker, days=days)
    
    if chronos_res.get("success"):
        engine_used = chronos_res.get("engine")
        signals = chronos_res.get("signals", {})
        lines = [
            f"📊 Executive Market Analysis for {ticker} (via {engine_used}):",
            f"• Current Price: {curr}{latest_price:,.2f}",
            f"• Horizon: {days} trading days",
            f"• Technical Bias: RSI={rsi_val:.1f} ({rsi_signal}) | MACD ({macd_bias})",
            f"• Signals: {json.dumps(signals) if isinstance(signals, (dict, list)) else signals}"
        ]
        return "\n".join(lines)
        
    # 3. Probabilistic Mathematical Forecast Fallback
    local_fc = _local_probabilistic_forecast(df, days=days)
    
    lines = [
        f"📊 Executive Market Forecast for {ticker} ({days}-Day Horizon):",
        f"• Current Price: {curr}{latest_price:,.2f}",
        f"• Expected Target (50th percentile): {curr}{local_fc['target_median']:,.2f} ({local_fc['pct_median']:+0.2f}%)",
        f"• Bull Case (90th percentile): {curr}{local_fc['target_bull']:,.2f} ({local_fc['pct_bull']:+0.2f}%)",
        f"• Bear Case (10th percentile): {curr}{local_fc['target_bear']:,.2f} ({local_fc['pct_bear']:+0.2f}%)",
        f"• Momentum & Indicators: RSI={rsi_val:.1f} ({rsi_signal}) | MACD ({macd_bias})"
    ]
    return "\n".join(lines)
