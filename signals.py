"""
Entry and exit signal logic using multi-timeframe MACD.
"""

import pandas as pd
import numpy as np
import config
from indicators import (
    compute_sma,
    histogram_turning_up,
    histogram_was_negative,
    histogram_negative_streak,
    compute_relative_strength
)


def check_regime(benchmark_df, date=None):
    """
    Check if the market regime is favorable for trading.
    QQQ must be above its 50 SMA, and 50 SMA above 200 SMA.
    Returns True if regime is bullish.
    """
    if not config.REGIME_FILTER:
        return True

    if benchmark_df is None:
        return True

    bench = benchmark_df.loc[:date] if date else benchmark_df

    if len(bench) < config.REGIME_SMA_LONG:
        return True  # Not enough data, don't block

    close = bench['Close'].squeeze()
    if isinstance(close, pd.DataFrame):
        close = close.iloc[:, 0]

    sma_short = close.rolling(config.REGIME_SMA_PERIOD).mean()
    sma_long = close.rolling(config.REGIME_SMA_LONG).mean()

    # QQQ price above 50 SMA AND 50 SMA above 200 SMA
    price_above_50 = close.iloc[-1] > sma_short.iloc[-1]
    golden_cross = sma_short.iloc[-1] > sma_long.iloc[-1]

    return price_above_50 and golden_cross


def check_entry_signal(daily_df, weekly_df, benchmark_df=None, date=None):
    """
    Check if a stock has a valid entry signal on a given date.

    Entry requires ALL of:
    0. Market regime is bullish (QQQ above 50 SMA, 50 > 200)
    1. Weekly MACD histogram turning up (2+ consecutive increasing bars)
    2. Daily MACD histogram was negative for 3+ bars, now turning up
    3. Price above 200-day SMA
    4. (Optional) Relative strength vs QQQ > 1.0
    5. (Optional) Volume above average on trigger day

    Args:
        daily_df: Daily OHLCV + indicators
        weekly_df: Weekly OHLCV + indicators
        benchmark_df: QQQ daily data for relative strength
        date: Date to check (None = latest)

    Returns:
        dict with signal info or None if no signal
    """
    # === Layer 0: Market Regime Filter ===
    if not check_regime(benchmark_df, date):
        return None

    if date is not None:
        # Slice data up to the given date
        daily_slice = daily_df.loc[:date]
        # Find the latest weekly bar on or before this date
        weekly_slice = weekly_df.loc[:date]
    else:
        daily_slice = daily_df
        weekly_slice = weekly_df

    if len(daily_slice) < config.TREND_SMA_PERIOD or len(weekly_slice) < config.MACD_SLOW + config.MACD_SIGNAL:
        return None

    # === Layer 3: Trend Filter (check first, cheapest) ===
    if 'Above_Trend' not in daily_slice.columns:
        return None
    if not daily_slice['Above_Trend'].iloc[-1]:
        return None

    # === Layer 1: Weekly MACD histogram turning up ===
    weekly_hist = weekly_slice['MACD_Hist']
    if not histogram_turning_up(weekly_hist, config.WEEKLY_HIST_TURN_BARS):
        # Also accept: weekly MACD line above signal line (established uptrend)
        if weekly_slice['MACD'].iloc[-1] <= weekly_slice['MACD_Signal'].iloc[-1]:
            return None

    # === Layer 2: Daily pullback + histogram turn ===
    daily_hist = daily_slice['MACD_Hist']

    # Histogram must have been negative (pullback occurred)
    if not histogram_was_negative(daily_hist, config.DAILY_PULLBACK_MIN_BARS):
        return None

    # Histogram now turning up
    if not histogram_turning_up(daily_hist, config.DAILY_HIST_TURN_BARS):
        return None

    # === Layer 4: RSI Mean Reversion Confirmation ===
    if config.RSI_ENABLED and 'RSI' in daily_slice.columns:
        rsi = daily_slice['RSI']
        if len(rsi) < 10:
            return None
        # RSI must have been oversold recently (last 5 bars)
        recent_rsi = rsi.iloc[-7:]
        was_oversold = any(recent_rsi < config.RSI_OVERSOLD)
        now_recovering = rsi.iloc[-1] > config.RSI_RECOVERY
        if not (was_oversold and now_recovering):
            return None

    # === Build signal info ===
    signal = {
        'date': daily_slice.index[-1],
        'close': daily_slice['Close'].iloc[-1],
        'atr': daily_slice['ATR'].iloc[-1],
        'daily_macd_hist': daily_hist.iloc[-1],
        'weekly_macd_hist': weekly_hist.iloc[-1],
        'sma_200': daily_slice['SMA_200'].iloc[-1],
        'volume_surge': daily_slice['Vol_Surge'].iloc[-1] if 'Vol_Surge' in daily_slice.columns else 1.0,
    }

    # === Optional: Relative Strength ===
    if benchmark_df is not None:
        rs = compute_relative_strength(daily_slice, benchmark_df, config.RS_LOOKBACK_DAYS)
        if rs is not None and len(rs.dropna()) > 0:
            latest_rs = rs.dropna().iloc[-1]
            signal['relative_strength'] = latest_rs
            if latest_rs < config.RS_MIN_RATIO:
                return None  # Underperforming the index
        else:
            signal['relative_strength'] = None

    # === Optional: Volume confirmation ===
    if config.VOLUME_SURGE_RATIO > 1.0:
        if signal['volume_surge'] < config.VOLUME_SURGE_RATIO:
            return None

    return signal


def check_exit_signal(daily_df, weekly_df, entry_price, entry_date, current_atr_stop):
    """
    Check if an open position should be exited.

    Exit if ANY of:
    1. Price hits ATR stop loss
    2. Weekly close below 10-week EMA
    3. Weekly MACD histogram negative for 2 consecutive weeks

    Returns:
        dict with exit info or None if no exit signal
    """
    if len(weekly_df) < 2 or len(daily_df) < 1:
        return None

    current_price = daily_df['Close'].iloc[-1]
    current_date = daily_df.index[-1]

    # === Exit 1: ATR Stop Loss ===
    if current_price <= current_atr_stop:
        return {
            'date': current_date,
            'close': current_price,
            'reason': 'stop_loss',
            'detail': f'Price {current_price:.2f} hit stop {current_atr_stop:.2f}'
        }

    # === Exit 2: Weekly close below EMA ===
    if 'EMA_Exit' in weekly_df.columns:
        weekly_close = weekly_df['Close'].iloc[-1]
        weekly_ema = weekly_df['EMA_Exit'].iloc[-1]
        if weekly_close < weekly_ema:
            return {
                'date': current_date,
                'close': current_price,
                'reason': 'weekly_ema_break',
                'detail': f'Weekly close {weekly_close:.2f} < EMA({config.WEEKLY_EMA_EXIT_PERIOD}) {weekly_ema:.2f}'
            }

    # === Exit 3: Weekly histogram negative streak ===
    weekly_hist = weekly_df['MACD_Hist']
    # Only trigger if histogram was positive after entry and now turned negative
    post_entry_weekly = weekly_df.loc[entry_date:]
    if len(post_entry_weekly) > config.WEEKLY_HIST_EXIT_BARS:
        if post_entry_weekly['MACD_Hist'].max() > 0:  # Was positive at some point
            if histogram_negative_streak(weekly_hist, config.WEEKLY_HIST_EXIT_BARS):
                return {
                    'date': current_date,
                    'close': current_price,
                    'reason': 'weekly_hist_negative',
                    'detail': f'Weekly histogram negative for {config.WEEKLY_HIST_EXIT_BARS} bars'
                }

    return None


def compute_trailing_stop(entry_price, highest_since_entry, atr_at_entry):
    """
    Compute trailing stop based on ATR.
    Stop = max(initial_stop, highest_close - 2*ATR)
    """
    initial_stop = entry_price - (config.ATR_STOP_MULTIPLIER * atr_at_entry)
    trailing_stop = highest_since_entry - (config.ATR_STOP_MULTIPLIER * atr_at_entry)
    return max(initial_stop, trailing_stop)


def compute_position_size(portfolio_value, entry_price, stop_price):
    """
    Position size based on risk per trade.
    Risk amount = portfolio_value * risk_pct
    Shares = risk_amount / (entry_price - stop_price)
    """
    risk_amount = portfolio_value * config.RISK_PER_TRADE_PCT
    risk_per_share = entry_price - stop_price

    if risk_per_share <= 0:
        return 0

    shares = int(risk_amount / risk_per_share)
    position_value = shares * entry_price

    # Cap at 25% of portfolio per position
    max_position = portfolio_value * 0.25
    if position_value > max_position:
        shares = int(max_position / entry_price)

    return max(0, shares)
