"""
Live scanner: runs daily to find new entry signals and manage paper positions.
Designed to be called by a scheduled task.
"""

import pandas as pd
import numpy as np
import json
import os
from datetime import datetime, timedelta
import config
from data import get_universe, fetch_daily_data, daily_to_weekly, fetch_benchmark
from indicators import add_all_indicators
from signals import (
    check_entry_signal,
    check_exit_signal,
    compute_trailing_stop,
    compute_position_size
)

PORTFOLIO_FILE = os.path.join(os.path.dirname(__file__), 'portfolio.json')
TRADE_LOG_FILE = os.path.join(os.path.dirname(__file__), 'trades.csv')
SCAN_LOG_FILE = os.path.join(os.path.dirname(__file__), 'scan_log.csv')


def load_portfolio():
    """Load paper portfolio from disk."""
    if os.path.exists(PORTFOLIO_FILE):
        with open(PORTFOLIO_FILE, 'r') as f:
            return json.load(f)
    return {
        'cash': config.INITIAL_CAPITAL,
        'positions': {},
        'created': datetime.now().isoformat(),
        'last_scan': None,
    }


def save_portfolio(portfolio):
    """Save paper portfolio to disk."""
    portfolio['last_scan'] = datetime.now().isoformat()
    with open(PORTFOLIO_FILE, 'w') as f:
        json.dump(portfolio, f, indent=2, default=str)


def log_trade(trade_dict):
    """Append a trade to the CSV log."""
    df = pd.DataFrame([trade_dict])
    if os.path.exists(TRADE_LOG_FILE):
        df.to_csv(TRADE_LOG_FILE, mode='a', header=False, index=False)
    else:
        df.to_csv(TRADE_LOG_FILE, index=False)


def log_scan(scan_dict):
    """Append scan results to the CSV log."""
    df = pd.DataFrame([scan_dict])
    if os.path.exists(SCAN_LOG_FILE):
        df.to_csv(SCAN_LOG_FILE, mode='a', header=False, index=False)
    else:
        df.to_csv(SCAN_LOG_FILE, index=False)


def run_scan():
    """
    Run the daily scan:
    1. Fetch latest data
    2. Check exits on open positions
    3. Scan for new entries
    4. Update portfolio
    5. Generate summary
    """
    portfolio = load_portfolio()
    summary = {
        'date': datetime.now().strftime('%Y-%m-%d %H:%M'),
        'signals': [],
        'exits': [],
        'new_entries': [],
        'open_positions': [],
        'portfolio_value': 0,
    }

    # Fetch data
    tickers = get_universe()
    end_date = datetime.now().strftime('%Y-%m-%d')
    start_date = (datetime.now() - timedelta(days=config.DATA_LOOKBACK_DAYS)).strftime('%Y-%m-%d')

    daily_dict = fetch_daily_data(tickers, start_date, end_date)
    benchmark_df = fetch_benchmark(start_date, end_date)

    # Compute weekly and indicators
    weekly_dict = {}
    for ticker in list(daily_dict.keys()):
        try:
            weekly_dict[ticker] = daily_to_weekly(daily_dict[ticker])
            daily_dict[ticker], weekly_dict[ticker] = add_all_indicators(
                daily_dict[ticker], weekly_dict[ticker], benchmark_df
            )
        except Exception as e:
            del daily_dict[ticker]

    # === Check exits ===
    for ticker, pos_data in list(portfolio['positions'].items()):
        if ticker not in daily_dict:
            continue

        daily = daily_dict[ticker]
        weekly = weekly_dict[ticker]
        current_price = daily['Close'].iloc[-1]

        # Update trailing stop
        if current_price > pos_data['highest']:
            pos_data['highest'] = float(current_price)
        pos_data['current_stop'] = float(compute_trailing_stop(
            pos_data['entry_price'], pos_data['highest'], pos_data['atr']
        ))

        exit_signal = check_exit_signal(
            daily, weekly,
            pos_data['entry_price'],
            pd.Timestamp(pos_data['entry_date']),
            pos_data['current_stop']
        )

        if exit_signal:
            exit_price = float(current_price)
            shares = pos_data['shares']
            pnl = (exit_price - pos_data['entry_price']) * shares
            pnl_pct = (exit_price - pos_data['entry_price']) / pos_data['entry_price']

            portfolio['cash'] += shares * exit_price * (1 - config.COMMISSION_PCT)

            exit_info = {
                'ticker': ticker,
                'exit_price': exit_price,
                'entry_price': pos_data['entry_price'],
                'shares': shares,
                'pnl': round(pnl, 2),
                'pnl_pct': round(pnl_pct * 100, 2),
                'reason': exit_signal['reason'],
                'days_held': (datetime.now() - datetime.fromisoformat(pos_data['entry_date'])).days,
            }

            summary['exits'].append(exit_info)
            log_trade({
                'date': end_date, 'ticker': ticker, 'action': 'SELL',
                'price': exit_price, 'shares': shares, 'pnl': pnl,
                'reason': exit_signal['reason']
            })

            del portfolio['positions'][ticker]

    # === Scan for entries ===
    entry_signals = []
    for ticker in daily_dict:
        if ticker in portfolio['positions']:
            continue

        signal = check_entry_signal(
            daily_dict[ticker], weekly_dict[ticker], benchmark_df
        )

        if signal:
            signal['ticker'] = ticker
            rs = signal.get('relative_strength', 1.0)
            signal['rank_score'] = rs if rs else 1.0
            entry_signals.append(signal)

    # Rank and take entries
    entry_signals.sort(key=lambda x: x['rank_score'], reverse=True)
    slots = config.MAX_POSITIONS - len(portfolio['positions'])

    for signal in entry_signals:
        summary['signals'].append({
            'ticker': signal['ticker'],
            'price': round(float(signal['close']), 2),
            'rs': round(float(signal.get('relative_strength', 0)), 3),
            'weekly_hist': round(float(signal['weekly_macd_hist']), 4),
            'daily_hist': round(float(signal['daily_macd_hist']), 4),
        })

    for signal in entry_signals[:slots]:
        ticker = signal['ticker']
        entry_price = float(signal['close'])
        atr = float(signal['atr'])
        stop_price = entry_price - (config.ATR_STOP_MULTIPLIER * atr)

        portfolio_value = portfolio['cash']
        for t, p in portfolio['positions'].items():
            if t in daily_dict:
                portfolio_value += p['shares'] * float(daily_dict[t]['Close'].iloc[-1])

        shares = compute_position_size(portfolio_value, entry_price, stop_price)
        if shares <= 0:
            continue

        cost = shares * entry_price * (1 + config.COMMISSION_PCT)
        if cost > portfolio['cash']:
            continue

        portfolio['cash'] -= cost
        portfolio['positions'][ticker] = {
            'entry_date': end_date,
            'entry_price': entry_price,
            'shares': shares,
            'atr': atr,
            'stop': round(stop_price, 2),
            'current_stop': round(stop_price, 2),
            'highest': entry_price,
        }

        summary['new_entries'].append({
            'ticker': ticker,
            'price': entry_price,
            'shares': shares,
            'stop': round(stop_price, 2),
        })

        log_trade({
            'date': end_date, 'ticker': ticker, 'action': 'BUY',
            'price': entry_price, 'shares': shares, 'pnl': 0,
            'reason': 'entry_signal'
        })

    # === Update open position summaries ===
    total_value = portfolio['cash']
    for ticker, pos_data in portfolio['positions'].items():
        if ticker in daily_dict:
            current_price = float(daily_dict[ticker]['Close'].iloc[-1])
            pos_value = pos_data['shares'] * current_price
            total_value += pos_value
            unrealized_pnl = (current_price - pos_data['entry_price']) * pos_data['shares']
            unrealized_pct = (current_price - pos_data['entry_price']) / pos_data['entry_price']

            summary['open_positions'].append({
                'ticker': ticker,
                'entry_price': pos_data['entry_price'],
                'current_price': round(current_price, 2),
                'shares': pos_data['shares'],
                'unrealized_pnl': round(unrealized_pnl, 2),
                'unrealized_pct': round(unrealized_pct * 100, 2),
                'stop': round(pos_data['current_stop'], 2),
                'days_held': (datetime.now() - datetime.fromisoformat(pos_data['entry_date'])).days,
            })

    summary['portfolio_value'] = round(total_value, 2)
    summary['cash'] = round(portfolio['cash'], 2)
    summary['total_return_pct'] = round((total_value - config.INITIAL_CAPITAL) / config.INITIAL_CAPITAL * 100, 2)

    save_portfolio(portfolio)
    log_scan({
        'date': end_date,
        'portfolio_value': summary['portfolio_value'],
        'num_positions': len(portfolio['positions']),
        'num_signals': len(summary['signals']),
        'num_entries': len(summary['new_entries']),
        'num_exits': len(summary['exits']),
    })

    return summary


def print_scan_summary(summary):
    """Pretty print the scan results."""
    print("\n" + "=" * 70)
    print(f"  DAILY SCAN RESULTS — {summary['date']}")
    print("=" * 70)

    print(f"\n  Portfolio Value: ${summary['portfolio_value']:>12,.2f}")
    print(f"  Cash:           ${summary['cash']:>12,.2f}")
    print(f"  Total Return:   {summary['total_return_pct']:>+10.2f}%")
    print(f"  Open Positions: {len(summary['open_positions'])}")

    if summary['exits']:
        print(f"\n  --- EXITS TODAY ---")
        for e in summary['exits']:
            print(f"  SOLD {e['ticker']:<6} @ ${e['exit_price']:.2f}  P&L: ${e['pnl']:>+8.2f} ({e['pnl_pct']:>+.1f}%)  [{e['reason']}]  ({e['days_held']}d)")

    if summary['new_entries']:
        print(f"\n  --- NEW ENTRIES ---")
        for e in summary['new_entries']:
            print(f"  BUY  {e['ticker']:<6} @ ${e['price']:.2f}  Shares: {e['shares']}  Stop: ${e['stop']:.2f}")

    if summary['signals']:
        print(f"\n  --- ALL SIGNALS (ranked by RS) ---")
        for s in summary['signals']:
            in_portfolio = "HELD" if any(p['ticker'] == s['ticker'] for p in summary['open_positions']) else "    "
            entered = ">>> ENTERED" if any(e['ticker'] == s['ticker'] for e in summary['new_entries']) else ""
            print(f"  {s['ticker']:<6} ${s['price']:<8.2f} RS:{s['rs']:.3f}  WkHist:{s['weekly_hist']:>+.4f}  DyHist:{s['daily_hist']:>+.4f}  {in_portfolio} {entered}")

    if summary['open_positions']:
        print(f"\n  --- OPEN POSITIONS ---")
        for p in summary['open_positions']:
            print(f"  {p['ticker']:<6} Entry: ${p['entry_price']:.2f}  Now: ${p['current_price']:.2f}  "
                  f"P&L: ${p['unrealized_pnl']:>+8.2f} ({p['unrealized_pct']:>+.1f}%)  "
                  f"Stop: ${p['stop']:.2f}  ({p['days_held']}d)")

    print("\n" + "=" * 70)


if __name__ == '__main__':
    summary = run_scan()
    print_scan_summary(summary)

    # Auto-regenerate the HTML dashboard
    try:
        from generate_dashboard import generate_html
        generate_html()
    except Exception as e:
        print(f"Warning: could not regenerate dashboard: {e}")
