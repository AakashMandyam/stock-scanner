"""
Main entry point for the Multi-Timeframe MACD Stock Scanner.

Usage:
    python main.py backtest     — Run historical backtest
    python main.py scan         — Run live daily scan
    python main.py status       — Show current portfolio status
"""

import sys
import os

# Ensure we can import from the same directory
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import config
from data import get_universe, prepare_data, fetch_benchmark
from backtest import BacktestEngine, print_report
from scanner import run_scan, print_scan_summary, load_portfolio
import json


def run_backtest():
    """Execute the full historical backtest."""
    print("=" * 70)
    print("  Multi-Timeframe MACD Strategy — Backtest Mode")
    print(f"  Period: {config.BACKTEST_START} to {config.BACKTEST_END}")
    print(f"  Universe: Nasdaq 100 ({len(get_universe())} tickers)")
    print("=" * 70)

    tickers = get_universe()
    benchmark_df = fetch_benchmark(config.BACKTEST_START, config.BACKTEST_END)
    daily_dict, weekly_dict = prepare_data(tickers, config.BACKTEST_START, config.BACKTEST_END)

    engine = BacktestEngine(daily_dict, weekly_dict, benchmark_df)
    report = engine.run(config.BACKTEST_START, config.BACKTEST_END)
    print_report(report)

    # Save trades to CSV
    if 'trades_df' in report:
        trades_path = os.path.join(os.path.dirname(__file__), 'backtest_trades.csv')
        report['trades_df'].to_csv(trades_path, index=False)
        print(f"\n  Trade log saved to: {trades_path}")

    # Save equity curve
    if 'equity_df' in report:
        equity_path = os.path.join(os.path.dirname(__file__), 'backtest_equity.csv')
        report['equity_df'].to_csv(equity_path, index=False)
        print(f"  Equity curve saved to: {equity_path}")

    return report


def run_live_scan():
    """Execute the daily live scan."""
    summary = run_scan()
    print_scan_summary(summary)
    return summary


def show_status():
    """Show current portfolio status."""
    portfolio = load_portfolio()
    print("\n" + "=" * 70)
    print("  PORTFOLIO STATUS")
    print("=" * 70)
    print(f"\n  Cash: ${portfolio['cash']:,.2f}")
    print(f"  Last Scan: {portfolio.get('last_scan', 'Never')}")
    print(f"  Open Positions: {len(portfolio['positions'])}")

    for ticker, pos in portfolio['positions'].items():
        print(f"\n  {ticker}:")
        print(f"    Entry: ${pos['entry_price']:.2f} on {pos['entry_date']}")
        print(f"    Shares: {pos['shares']}")
        print(f"    Stop: ${pos['current_stop']:.2f}")
        print(f"    Highest: ${pos['highest']:.2f}")

    print("\n" + "=" * 70)


if __name__ == '__main__':
    if len(sys.argv) < 2:
        print("Usage: python main.py [backtest|scan|status]")
        sys.exit(1)

    mode = sys.argv[1].lower()

    if mode == 'backtest':
        run_backtest()
    elif mode == 'scan':
        run_live_scan()
    elif mode == 'status':
        show_status()
    else:
        print(f"Unknown mode: {mode}")
        print("Usage: python main.py [backtest|scan|status]")
        sys.exit(1)
