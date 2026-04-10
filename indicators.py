"""
Technical indicator calculations: MACD, ATR, EMA, Relative Strength.
"""

import pandas as pd
import numpy as np
import config


def compute_ema(series, period):
    """Exponential Moving Average."""
    return series.ewm(span=period, adjust=False).mean()


def compute_sma(series, period):
    """Simple Moving Average."""
    return series.rolling(window=period).mean()


def compute_macd(df, fast=None, slow=None, signal=None):
    """
    Compute MACD line, signal line, and histogram.
    Adds columns: MACD, MACD_Signal, MACD_Hist
    """
    fast = fast or config.MACD_FAST
    slow = slow or config.MACD_SLOW
    signal = signal or config.MACD_SIGNAL

    df = df.copy()
    df['EMA_Fast'] = compute_ema(df['Close'], fast)
    df['EMA_Slow'] = compute_ema(df['Close'], slow)
    df['MACD'] = df['EMA_Fast'] - df['EMA_Slow']
    df['MACD_Signal'] = compute_ema(df['MACD'], signal)
    df['MACD_Hist'] = df['MACD'] - df['MACD_Signal']

    # Clean up intermediate columns
    df.drop(['EMA_Fast', 'EMA_Slow'], axis=1, inplace=True)

    return df


def compute_atr(df, period=None):
    """
    Average True Range.
    Adds column: ATR
    """
    period = period or config.ATR_PERIOD
    df = df.copy()

    high_low = df['High'] - df['Low']
    high_close = (df['High'] - df['Close'].shift(1)).abs()
    low_close = (df['Low'] - df['Close'].shift(1)).abs()

    true_range = pd.concat([high_low, high_close, low_close], axis=1).max(axis=1)
    df['ATR'] = true_range.rolling(window=period).mean()

    return df


def compute_trend_filter(df, period=None):
    """
    200-day SMA trend filter.
    Adds column: SMA_200, Above_Trend
    """
    period = period or config.TREND_SMA_PERIOD
    df = df.copy()
    df['SMA_200'] = compute_sma(df['Close'], period)
    df['Above_Trend'] = df['Close'] > df['SMA_200']
    return df


def compute_weekly_ema(df, period=None):
    """
    Weekly EMA for exit signal.
    Adds column: EMA_Exit
    """
    period = period or config.WEEKLY_EMA_EXIT_PERIOD
    df = df.copy()
    df['EMA_Exit'] = compute_ema(df['Close'], period)
    return df


def compute_volume_avg(df, period=None):
    """
    Volume moving average for confirmation.
    Adds columns: Vol_Avg, Vol_Surge
    """
    period = period or config.VOLUME_AVG_PERIOD
    df = df.copy()
    df['Vol_Avg'] = compute_sma(df['Volume'], period)
    df['Vol_Surge'] = df['Volume'] / df['Vol_Avg']
    return df


def compute_relative_strength(stock_df, benchmark_df, lookback=None):
    """
    Relative strength: stock's N-day return / benchmark's N-day return.
    Returns the RS ratio (>1 means outperforming).
    """
    lookback = lookback or config.RS_LOOKBACK_DAYS

    # Align dates
    common_dates = stock_df.index.intersection(benchmark_df.index)
    if len(common_dates) < lookback:
        return None

    stock_close = stock_df.loc[common_dates, 'Close'].squeeze()
    bench_close = benchmark_df.loc[common_dates, 'Close'].squeeze()

    # Ensure we have Series not DataFrames
    if isinstance(stock_close, pd.DataFrame):
        stock_close = stock_close.iloc[:, 0]
    if isinstance(bench_close, pd.DataFrame):
        bench_close = bench_close.iloc[:, 0]

    stock_ret = stock_close.pct_change(lookback)
    bench_ret = bench_close.pct_change(lookback)

    # Avoid division by zero
    rs = pd.Series(index=common_dates, dtype=float)
    mask = bench_ret.abs() > 0.001
    rs.loc[mask] = (1 + stock_ret.loc[mask]) / (1 + bench_ret.loc[mask])

    return rs


def add_all_indicators(daily_df, weekly_df, benchmark_df=None):
    """
    Compute all indicators for a single stock.
    Returns: (daily_df with indicators, weekly_df with indicators)
    """
    # Daily indicators
    daily_df = compute_macd(daily_df)
    daily_df = compute_atr(daily_df)
    daily_df = compute_trend_filter(daily_df)
    daily_df = compute_volume_avg(daily_df)
    if config.RSI_ENABLED:
        daily_df['RSI'] = compute_rsi(daily_df['Close'], config.RSI_PERIOD)

    # Weekly indicators
    weekly_df = compute_macd(weekly_df)
    weekly_df = compute_weekly_ema(weekly_df)

    return daily_df, weekly_df


def histogram_turning_up(hist_series, n_bars=2):
    """
    Check if the histogram has N consecutive increasing bars (turning up from trough).
    Returns True/False for the last bar.
    """
    if len(hist_series) < n_bars + 1:
        return False

    recent = hist_series.iloc[-(n_bars + 1):]

    # Each bar must be greater than the previous
    for i in range(1, len(recent)):
        if recent.iloc[i] <= recent.iloc[i - 1]:
            return False

    return True


def histogram_was_negative(hist_series, min_bars=3):
    """
    Check if the histogram was negative for at least min_bars before the recent turn.
    Looks back from the current position.
    """
    if len(hist_series) < min_bars + 2:
        return False

    # Look at bars before the most recent 2 (which are the turn-up bars)
    lookback = hist_series.iloc[-(min_bars + 2):-2]
    neg_count = (lookback < 0).sum()

    return neg_count >= min_bars


def compute_rsi(series, period=None):
    """Relative Strength Index."""
    period = period or config.RSI_PERIOD
    delta = series.diff()
    gain = delta.where(delta > 0, 0.0)
    loss = -delta.where(delta < 0, 0.0)
    avg_gain = gain.rolling(window=period).mean()
    avg_loss = loss.rolling(window=period).mean()
    rs = avg_gain / avg_loss
    rsi = 100 - (100 / (1 + rs))
    return rsi


def histogram_negative_streak(hist_series, n_bars=2):
    """
    Check if the last N bars of histogram are negative (for exit signal).
    """
    if len(hist_series) < n_bars:
        return False

    return all(hist_series.iloc[-n_bars:] < 0)
