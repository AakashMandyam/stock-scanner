"""
Data pipeline: fetch and prepare daily/weekly OHLCV data for Nasdaq 100 stocks.
"""

import yfinance as yf
import pandas as pd
import numpy as np
import json
import os
from datetime import datetime, timedelta

# Nasdaq 100 tickers (as of early 2026 — update periodically)
NASDAQ_100 = [
    "AAPL", "ABNB", "ADBE", "ADI", "ADP", "ADSK", "AEP", "AMAT", "AMD", "AMGN",
    "AMZN", "ANSS", "APP", "ARM", "ASML", "AVGO", "AZN", "BIIB", "BKNG", "BKR",
    "CCEP", "CDNS", "CDW", "CEG", "CHTR", "CMCSA", "COIN", "COST", "CPRT", "CRWD",
    "CSGP", "CTAS", "CTSH", "DASH", "DDOG", "DLTR", "DXCM", "EA", "EXC", "FANG",
    "FAST", "FTNT", "GEHC", "GFS", "GILD", "GOOG", "GOOGL", "HON", "IDXX", "ILMN",
    "INTC", "INTU", "ISRG", "KDP", "KHC", "KLAC", "LIN", "LRCX", "LULU", "MAR",
    "MCHP", "MDB", "MDLZ", "MELI", "META", "MNST", "MRNA", "MRVL", "MSFT", "MU",
    "NFLX", "NVDA", "NXPI", "ODFL", "ON", "ORLY", "PANW", "PAYX", "PCAR", "PDD",
    "PEP", "PLTR", "PYPL", "QCOM", "REGN", "ROP", "ROST", "SBUX", "SNPS", "SPY",
    "TEAM", "TMUS", "TSLA", "TTD", "TTWO", "TXN", "VRSK", "VRTX", "WBD", "WDAY",
    "XEL", "ZS"
]


def get_universe():
    """Return the list of tickers to scan."""
    return NASDAQ_100


def fetch_daily_data(tickers, start, end, progress=False):
    """
    Fetch daily OHLCV data for a list of tickers.
    Returns dict of {ticker: DataFrame} with columns [Open, High, Low, Close, Volume].
    """
    print(f"Fetching daily data for {len(tickers)} tickers from {start} to {end}...")

    all_data = {}
    failed = []

    # Batch download
    try:
        raw = yf.download(
            tickers,
            start=start,
            end=end,
            auto_adjust=True,
            progress=progress,
            threads=True
        )

        if raw.empty:
            print("WARNING: No data returned from yfinance")
            return all_data

        for ticker in tickers:
            try:
                if len(tickers) == 1:
                    df = raw.copy()
                else:
                    # Multi-ticker download has multi-level columns
                    df = pd.DataFrame({
                        'Open': raw[('Open', ticker)],
                        'High': raw[('High', ticker)],
                        'Low': raw[('Low', ticker)],
                        'Close': raw[('Close', ticker)],
                        'Volume': raw[('Volume', ticker)]
                    })

                df = df.dropna(subset=['Close'])

                if len(df) > 50:  # Need enough data for indicators
                    all_data[ticker] = df
                else:
                    failed.append(ticker)
            except Exception as e:
                failed.append(ticker)

    except Exception as e:
        print(f"Batch download failed: {e}")
        print("Falling back to individual downloads...")
        for ticker in tickers:
            try:
                df = yf.download(ticker, start=start, end=end, auto_adjust=True, progress=False)
                if len(df) > 50:
                    all_data[ticker] = df
                else:
                    failed.append(ticker)
            except:
                failed.append(ticker)

    if failed:
        print(f"Failed/insufficient data for {len(failed)} tickers: {failed[:10]}...")

    print(f"Successfully loaded {len(all_data)} tickers")
    return all_data


def daily_to_weekly(daily_df):
    """
    Convert daily OHLCV to weekly OHLCV.
    Uses Friday as week end. Handles incomplete current week correctly.
    """
    weekly = daily_df.resample('W-FRI').agg({
        'Open': 'first',
        'High': 'max',
        'Low': 'min',
        'Close': 'last',
        'Volume': 'sum'
    }).dropna()

    return weekly


def prepare_data(tickers, start, end, progress=False):
    """
    Fetch daily data and compute weekly data for all tickers.
    Returns: (daily_dict, weekly_dict)
    """
    daily_dict = fetch_daily_data(tickers, start, end, progress=progress)
    weekly_dict = {}

    for ticker, daily_df in daily_dict.items():
        weekly_dict[ticker] = daily_to_weekly(daily_df)

    return daily_dict, weekly_dict


def fetch_benchmark(start, end):
    """Fetch QQQ data for relative strength calculations."""
    df = yf.download("QQQ", start=start, end=end, auto_adjust=True, progress=False)
    return df
