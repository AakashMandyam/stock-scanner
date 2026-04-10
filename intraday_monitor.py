"""
Intraday monitor: runs multiple times per day during market hours.
- Checks stops on open positions using live intraday prices
- Flags forming entry signals (but doesn't confirm until close)
- Executes stop-loss exits immediately when triggered

This is the real-time component. The daily scan (scanner.py) remains
the authority for confirming new entries at market close.
"""

import sys
import os
import json
import yfinance as yf
import pandas as pd
import numpy as np
from datetime import datetime, timedelta

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import config
from data import get_universe, daily_to_weekly, fetch_benchmark
from indicators import add_all_indicators, compute_macd, compute_atr, compute_trend_filter, compute_volume_avg, compute_rsi
from signals import check_entry_signal, compute_trailing_stop, compute_position_size, check_regime

PORTFOLIO_FILE = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'portfolio.json')
TRADE_LOG_FILE = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'trades.csv')
ALERT_LOG_FILE = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'alerts.csv')


def load_portfolio():
    if os.path.exists(PORTFOLIO_FILE):
        with open(PORTFOLIO_FILE, 'r') as f:
            return json.load(f)
    return {'cash': config.INITIAL_CAPITAL, 'positions': {}, 'last_scan': None}


def save_portfolio(portfolio):
    portfolio['last_intraday_check'] = datetime.now().isoformat()
    with open(PORTFOLIO_FILE, 'w') as f:
        json.dump(portfolio, f, indent=2, default=str)


def log_trade(trade_dict):
    df = pd.DataFrame([trade_dict])
    if os.path.exists(TRADE_LOG_FILE):
        df.to_csv(TRADE_LOG_FILE, mode='a', header=False, index=False)
    else:
        df.to_csv(TRADE_LOG_FILE, index=False)


def log_alert(alert_dict):
    df = pd.DataFrame([alert_dict])
    if os.path.exists(ALERT_LOG_FILE):
        df.to_csv(ALERT_LOG_FILE, mode='a', header=False, index=False)
    else:
        df.to_csv(ALERT_LOG_FILE, index=False)


def get_live_prices(tickers):
    """Fetch current intraday prices for a list of tickers."""
    prices = {}
    try:
        data = yf.download(tickers, period='1d', interval='1m', progress=False)
        if data.empty:
            return prices
        for ticker in tickers:
            try:
                if len(tickers) == 1:
                    close = data['Close'].iloc[-1]
                else:
                    close = data[('Close', ticker)].iloc[-1]
                if not pd.isna(close):
                    prices[ticker] = float(close)
            except:
                pass
    except:
        # Fallback: fetch individually
        for ticker in tickers:
            try:
                t = yf.Ticker(ticker)
                price = t.info.get('regularMarketPrice') or t.info.get('currentPrice')
                if price:
                    prices[ticker] = float(price)
            except:
                pass
    return prices


def check_intraday_stops(portfolio, live_prices):
    """
    Check if any open positions have hit their stop loss at current prices.
    Returns list of positions to exit.
    """
    exits = []
    for ticker, pos in portfolio.get('positions', {}).items():
        if ticker not in live_prices:
            continue

        current_price = live_prices[ticker]

        # Update highest price
        if current_price > pos.get('highest', pos['entry_price']):
            pos['highest'] = current_price

        # Recompute trailing stop
        current_stop = compute_trailing_stop(
            pos['entry_price'],
            pos.get('highest', pos['entry_price']),
            pos['atr']
        )
        pos['current_stop'] = current_stop

        if current_price <= current_stop:
            pnl = (current_price - pos['entry_price']) * pos['shares']
            pnl_pct = (current_price - pos['entry_price']) / pos['entry_price']
            exits.append({
                'ticker': ticker,
                'current_price': current_price,
                'stop': current_stop,
                'entry_price': pos['entry_price'],
                'shares': pos['shares'],
                'pnl': round(pnl, 2),
                'pnl_pct': round(pnl_pct * 100, 2),
                'reason': 'intraday_stop_loss',
            })

    return exits


def scan_forming_signals(live_prices):
    """
    Check which stocks are forming potential entry signals based on
    current intraday prices. These are ALERTS, not confirmed entries.
    Entries only confirm at market close via the daily scan.
    """
    alerts = []

    # Need historical daily data for indicators
    end_date = datetime.now().strftime('%Y-%m-%d')
    start_date = (datetime.now() - timedelta(days=config.DATA_LOOKBACK_DAYS)).strftime('%Y-%m-%d')

    # Fetch benchmark for regime check
    benchmark_df = fetch_benchmark(start_date, end_date)
    if not check_regime(benchmark_df):
        return alerts  # Market regime not bullish, no alerts

    # Only check stocks we have live prices for
    tickers = [t for t in get_universe() if t in live_prices]

    # Fetch daily data
    print(f"Checking {len(tickers)} stocks for forming signals...")
    try:
        raw = yf.download(tickers, start=start_date, end=end_date, auto_adjust=True, progress=False)
    except:
        return alerts

    for ticker in tickers:
        try:
            if len(tickers) == 1:
                daily = raw.copy()
            else:
                daily = pd.DataFrame({
                    'Open': raw[('Open', ticker)],
                    'High': raw[('High', ticker)],
                    'Low': raw[('Low', ticker)],
                    'Close': raw[('Close', ticker)],
                    'Volume': raw[('Volume', ticker)]
                })
            daily = daily.dropna(subset=['Close'])

            if len(daily) < config.TREND_SMA_PERIOD:
                continue

            # Append current intraday price as a partial "today" bar
            today = pd.DataFrame({
                'Open': [live_prices[ticker]],
                'High': [live_prices[ticker]],
                'Low': [live_prices[ticker]],
                'Close': [live_prices[ticker]],
                'Volume': [0]
            }, index=[pd.Timestamp(datetime.now().date())])

            # Only append if today isn't already in the data
            if today.index[0] not in daily.index:
                daily = pd.concat([daily, today])

            weekly = daily.resample('W-FRI').agg({
                'Open': 'first', 'High': 'max', 'Low': 'min',
                'Close': 'last', 'Volume': 'sum'
            }).dropna()

            daily, weekly = add_all_indicators(daily, weekly, benchmark_df)

            signal = check_entry_signal(daily, weekly, benchmark_df)
            if signal:
                alerts.append({
                    'ticker': ticker,
                    'current_price': live_prices[ticker],
                    'signal_strength': 'FORMING',
                    'daily_hist': round(float(signal['daily_macd_hist']), 4),
                    'weekly_hist': round(float(signal['weekly_macd_hist']), 4),
                    'rs': round(float(signal.get('relative_strength', 0)), 3),
                    'above_200sma': True,
                })
        except Exception as e:
            continue

    return alerts


def run_intraday_check():
    """Main intraday monitoring loop."""
    portfolio = load_portfolio()
    now = datetime.now()

    print(f"\n{'='*60}")
    print(f"  INTRADAY CHECK — {now.strftime('%Y-%m-%d %H:%M:%S')}")
    print(f"{'='*60}")

    # Get tickers we need prices for
    held_tickers = list(portfolio.get('positions', {}).keys())
    all_tickers = list(set(held_tickers + get_universe()))

    # Fetch live prices
    print(f"Fetching live prices for {len(held_tickers)} held + scanning universe...")
    live_prices = get_live_prices(all_tickers)
    print(f"Got prices for {len(live_prices)} tickers")

    # === CHECK STOPS ===
    exits = check_intraday_stops(portfolio, live_prices)

    if exits:
        print(f"\n  !!! STOP LOSS TRIGGERED !!!")
        for exit in exits:
            ticker = exit['ticker']
            print(f"  EXIT {ticker} @ ${exit['current_price']:.2f}  "
                  f"Stop: ${exit['stop']:.2f}  "
                  f"P&L: ${exit['pnl']:+.2f} ({exit['pnl_pct']:+.1f}%)")

            # Execute the exit
            pos = portfolio['positions'][ticker]
            portfolio['cash'] += pos['shares'] * exit['current_price'] * (1 - config.COMMISSION_PCT)

            log_trade({
                'date': now.strftime('%Y-%m-%d'),
                'ticker': ticker,
                'action': 'SELL',
                'price': exit['current_price'],
                'shares': pos['shares'],
                'pnl': exit['pnl'],
                'reason': 'intraday_stop_loss'
            })

            del portfolio['positions'][ticker]
    else:
        print(f"\n  All {len(held_tickers)} positions above their stops.")

    # === UPDATE POSITION VALUES ===
    total_value = portfolio['cash']
    for ticker, pos in portfolio['positions'].items():
        if ticker in live_prices:
            current = live_prices[ticker]
            pos_value = pos['shares'] * current
            total_value += pos_value
            unrealized = (current - pos['entry_price']) / pos['entry_price'] * 100
            print(f"  {ticker:<6} ${current:.2f}  P&L: {unrealized:+.1f}%  Stop: ${pos.get('current_stop', 0):.2f}")

    print(f"\n  Portfolio Value: ${total_value:,.2f}  (Cash: ${portfolio['cash']:,.2f})")

    # === SCAN FOR FORMING SIGNALS ===
    print(f"\n  Scanning for forming entry signals...")
    alerts = scan_forming_signals(live_prices)

    if alerts:
        print(f"\n  --- FORMING SIGNALS (not confirmed until close) ---")
        for a in alerts:
            already_held = a['ticker'] in portfolio.get('positions', {})
            status = " [HELD]" if already_held else ""
            print(f"  {a['ticker']:<6} ${a['current_price']:.2f}  RS:{a['rs']:.3f}  "
                  f"DyHist:{a['daily_hist']:+.4f}  WkHist:{a['weekly_hist']:+.4f}{status}")

            log_alert({
                'date': now.strftime('%Y-%m-%d %H:%M'),
                'ticker': a['ticker'],
                'price': a['current_price'],
                'status': 'forming',
                'rs': a['rs'],
            })
    else:
        print(f"  No forming signals detected.")

    save_portfolio(portfolio)
    print(f"\n{'='*60}\n")

    return {
        'exits': exits,
        'alerts': alerts,
        'portfolio_value': total_value,
        'positions_count': len(portfolio['positions']),
    }


if __name__ == '__main__':
    run_intraday_check()
