"""
Backtesting engine for the multi-timeframe MACD strategy.
Walks forward through time, checking for entry/exit signals day by day.
"""

import pandas as pd
import numpy as np
from datetime import timedelta
import config
from indicators import add_all_indicators, compute_relative_strength
from signals import (
    check_entry_signal,
    check_exit_signal,
    compute_trailing_stop,
    compute_position_size
)


class Position:
    def __init__(self, ticker, entry_date, entry_price, shares, atr_at_entry):
        self.ticker = ticker
        self.entry_date = entry_date
        self.entry_price = entry_price
        self.shares = shares
        self.atr_at_entry = atr_at_entry
        self.highest_since_entry = entry_price
        self.current_stop = entry_price - (config.ATR_STOP_MULTIPLIER * atr_at_entry)
        self.cost_basis = entry_price * shares

    def update(self, current_price):
        """Update trailing stop based on current price."""
        if current_price > self.highest_since_entry:
            self.highest_since_entry = current_price
        self.current_stop = compute_trailing_stop(
            self.entry_price, self.highest_since_entry, self.atr_at_entry
        )

    def pnl(self, exit_price):
        """Realized P&L."""
        return (exit_price - self.entry_price) * self.shares

    def pnl_pct(self, exit_price):
        """Realized P&L as percentage."""
        return (exit_price - self.entry_price) / self.entry_price


class BacktestEngine:
    def __init__(self, daily_dict, weekly_dict, benchmark_df):
        self.daily_dict = daily_dict
        self.weekly_dict = weekly_dict
        self.benchmark_df = benchmark_df
        self.positions = {}  # ticker -> Position
        self.closed_trades = []
        self.equity_curve = []
        self.cash = config.INITIAL_CAPITAL
        self.trade_log = []
        self.peak_equity = config.INITIAL_CAPITAL
        self.consecutive_stops = 0
        self.cooldown_until = None

    def run(self, start_date=None, end_date=None):
        """Run the backtest over the specified date range."""
        start_date = pd.Timestamp(start_date or config.BACKTEST_START)
        end_date = pd.Timestamp(end_date or config.BACKTEST_END)

        # Pre-compute all indicators
        print("Computing indicators for all tickers...")
        for ticker in list(self.daily_dict.keys()):
            try:
                self.daily_dict[ticker], self.weekly_dict[ticker] = add_all_indicators(
                    self.daily_dict[ticker],
                    self.weekly_dict[ticker],
                    self.benchmark_df
                )
            except Exception as e:
                print(f"  Error computing indicators for {ticker}: {e}")
                del self.daily_dict[ticker]
                if ticker in self.weekly_dict:
                    del self.weekly_dict[ticker]

        # Get all trading dates from benchmark
        trading_dates = self.benchmark_df.loc[start_date:end_date].index

        print(f"Running backtest from {start_date.date()} to {end_date.date()} ({len(trading_dates)} trading days)...")

        for i, date in enumerate(trading_dates):
            if i % 250 == 0 and i > 0:
                pv = self._portfolio_value(date)
                print(f"  Day {i}/{len(trading_dates)} | Date: {date.date()} | Portfolio: ${pv:,.0f} | Positions: {len(self.positions)}")

            self._process_day(date)

        # Close any remaining positions at last date
        last_date = trading_dates[-1]
        for ticker in list(self.positions.keys()):
            self._close_position(ticker, last_date, "backtest_end")

        return self._generate_report()

    def _process_day(self, date):
        """Process a single trading day: check exits, then entries."""
        # === Check exits first ===
        for ticker in list(self.positions.keys()):
            if ticker not in self.daily_dict:
                continue

            daily = self.daily_dict[ticker]
            weekly = self.weekly_dict[ticker]
            pos = self.positions[ticker]

            # Get data up to this date
            daily_to_date = daily.loc[:date]
            weekly_to_date = weekly.loc[:date]

            if len(daily_to_date) == 0:
                continue

            # Update position with current price
            current_price = daily_to_date['Close'].iloc[-1]
            pos.update(current_price)

            # Check exit signals
            exit_signal = check_exit_signal(
                daily_to_date, weekly_to_date,
                pos.entry_price, pos.entry_date, pos.current_stop
            )

            if exit_signal:
                self._close_position(ticker, date, exit_signal['reason'])

        # === Check entries ===
        if len(self.positions) >= config.MAX_POSITIONS:
            return  # Full, no new entries

        # Cooldown check
        if self.cooldown_until and date <= self.cooldown_until:
            return

        signals = []
        for ticker in self.daily_dict:
            if ticker in self.positions:
                continue  # Already holding

            daily = self.daily_dict[ticker]
            weekly = self.weekly_dict[ticker]

            daily_to_date = daily.loc[:date]
            weekly_to_date = weekly.loc[:date]

            signal = check_entry_signal(
                daily_to_date, weekly_to_date,
                self.benchmark_df, date
            )

            if signal:
                signal['ticker'] = ticker
                # Add relative strength for ranking
                rs = signal.get('relative_strength', 1.0)
                signal['rank_score'] = rs if rs else 1.0
                signals.append(signal)

        # Rank by relative strength, take top N to fill positions
        signals.sort(key=lambda x: x['rank_score'], reverse=True)
        slots_available = config.MAX_POSITIONS - len(self.positions)

        for signal in signals[:slots_available]:
            self._open_position(signal)

        # Record equity
        pv = self._portfolio_value(date)
        self.equity_curve.append({'date': date, 'equity': pv})

    def _open_position(self, signal):
        """Open a new paper position."""
        ticker = signal['ticker']
        entry_price = signal['close']
        atr = signal['atr']

        if pd.isna(atr) or atr <= 0:
            return

        stop_price = entry_price - (config.ATR_STOP_MULTIPLIER * atr)
        portfolio_value = self._portfolio_value(signal['date'])

        # Volatility scaling — reduce size when in drawdown
        vol_scale = 1.0
        if config.VOL_SCALE_ENABLED:
            if portfolio_value > self.peak_equity:
                self.peak_equity = portfolio_value
            dd = (portfolio_value - self.peak_equity) / self.peak_equity
            if dd < config.VOL_SCALE_DRAWDOWN_THRESHOLD:
                # Linear scale from 1.0 at threshold to VOL_SCALE_MIN at -30%
                scale_range = -0.30 - config.VOL_SCALE_DRAWDOWN_THRESHOLD
                dd_beyond = dd - config.VOL_SCALE_DRAWDOWN_THRESHOLD
                vol_scale = max(config.VOL_SCALE_MIN, 1.0 + (1.0 - config.VOL_SCALE_MIN) * (dd_beyond / scale_range))

        shares = compute_position_size(portfolio_value, entry_price, stop_price)
        shares = max(1, int(shares * vol_scale))

        if shares <= 0:
            return

        cost = shares * entry_price * (1 + config.COMMISSION_PCT)
        if cost > self.cash:
            shares = int(self.cash / (entry_price * (1 + config.COMMISSION_PCT)))
            if shares <= 0:
                return
            cost = shares * entry_price * (1 + config.COMMISSION_PCT)

        self.cash -= cost
        pos = Position(ticker, signal['date'], entry_price, shares, atr)
        self.positions[ticker] = pos

        self.trade_log.append({
            'ticker': ticker,
            'action': 'BUY',
            'date': signal['date'],
            'price': entry_price,
            'shares': shares,
            'value': shares * entry_price,
            'atr': atr,
            'stop': stop_price,
            'rs': signal.get('relative_strength', None),
            'weekly_hist': signal['weekly_macd_hist'],
            'daily_hist': signal['daily_macd_hist'],
        })

    def _close_position(self, ticker, date, reason):
        """Close an existing position."""
        if ticker not in self.positions:
            return

        pos = self.positions[ticker]

        # Get exit price
        daily = self.daily_dict.get(ticker)
        if daily is not None:
            daily_to_date = daily.loc[:date]
            if len(daily_to_date) > 0:
                exit_price = daily_to_date['Close'].iloc[-1]
            else:
                exit_price = pos.entry_price
        else:
            exit_price = pos.entry_price

        proceeds = pos.shares * exit_price * (1 - config.COMMISSION_PCT)
        self.cash += proceeds

        pnl = pos.pnl(exit_price)
        pnl_pct = pos.pnl_pct(exit_price)
        days_held = (date - pos.entry_date).days

        trade = {
            'ticker': ticker,
            'action': 'SELL',
            'date': date,
            'entry_date': pos.entry_date,
            'entry_price': pos.entry_price,
            'exit_price': exit_price,
            'shares': pos.shares,
            'pnl': pnl,
            'pnl_pct': pnl_pct,
            'days_held': days_held,
            'reason': reason,
        }

        self.closed_trades.append(trade)
        self.trade_log.append({
            'ticker': ticker,
            'action': 'SELL',
            'date': date,
            'price': exit_price,
            'shares': pos.shares,
            'value': pos.shares * exit_price,
            'pnl': pnl,
            'reason': reason,
        })

        # Track consecutive stop losses for cooldown
        if reason == 'stop_loss':
            self.consecutive_stops += 1
            if self.consecutive_stops >= config.COOLDOWN_AFTER_LOSSES:
                self.cooldown_until = date + pd.Timedelta(days=config.COOLDOWN_DAYS)
                self.consecutive_stops = 0
        else:
            self.consecutive_stops = 0

        del self.positions[ticker]

    def _portfolio_value(self, date):
        """Total portfolio value: cash + open positions."""
        total = self.cash
        for ticker, pos in self.positions.items():
            daily = self.daily_dict.get(ticker)
            if daily is not None:
                daily_to_date = daily.loc[:date]
                if len(daily_to_date) > 0:
                    current_price = daily_to_date['Close'].iloc[-1]
                    total += pos.shares * current_price
        return total

    def _generate_report(self):
        """Generate backtest performance report."""
        if not self.closed_trades:
            return {"error": "No trades executed"}

        trades_df = pd.DataFrame(self.closed_trades)
        equity_df = pd.DataFrame(self.equity_curve)

        # Basic stats
        total_trades = len(trades_df)
        winners = trades_df[trades_df['pnl'] > 0]
        losers = trades_df[trades_df['pnl'] <= 0]
        win_rate = len(winners) / total_trades if total_trades > 0 else 0

        avg_winner = winners['pnl_pct'].mean() if len(winners) > 0 else 0
        avg_loser = losers['pnl_pct'].mean() if len(losers) > 0 else 0
        profit_factor = (winners['pnl'].sum() / abs(losers['pnl'].sum())) if len(losers) > 0 and losers['pnl'].sum() != 0 else float('inf')

        avg_days_held = trades_df['days_held'].mean()
        avg_winner_days = winners['days_held'].mean() if len(winners) > 0 else 0
        avg_loser_days = losers['days_held'].mean() if len(losers) > 0 else 0

        # Equity curve stats
        if len(equity_df) > 0:
            final_equity = equity_df['equity'].iloc[-1]
            total_return = (final_equity - config.INITIAL_CAPITAL) / config.INITIAL_CAPITAL

            # Max drawdown
            equity_df['peak'] = equity_df['equity'].cummax()
            equity_df['drawdown'] = (equity_df['equity'] - equity_df['peak']) / equity_df['peak']
            max_drawdown = equity_df['drawdown'].min()

            # Annualized return
            days = (equity_df['date'].iloc[-1] - equity_df['date'].iloc[0]).days
            years = days / 365.25
            annual_return = (1 + total_return) ** (1 / years) - 1 if years > 0 else 0

            # Sharpe ratio (approximate)
            if len(equity_df) > 1:
                daily_returns = equity_df['equity'].pct_change().dropna()
                sharpe = (daily_returns.mean() / daily_returns.std()) * np.sqrt(252) if daily_returns.std() > 0 else 0
            else:
                sharpe = 0
        else:
            final_equity = config.INITIAL_CAPITAL
            total_return = 0
            max_drawdown = 0
            annual_return = 0
            sharpe = 0

        # Exit reason breakdown
        exit_reasons = trades_df['reason'].value_counts().to_dict()

        # Biggest winners and losers
        best_trades = trades_df.nlargest(5, 'pnl_pct')[['ticker', 'entry_date', 'exit_price', 'pnl_pct', 'days_held']].to_dict('records')
        worst_trades = trades_df.nsmallest(5, 'pnl_pct')[['ticker', 'entry_date', 'exit_price', 'pnl_pct', 'days_held']].to_dict('records')

        report = {
            'total_trades': total_trades,
            'winners': len(winners),
            'losers': len(losers),
            'win_rate': win_rate,
            'avg_winner_pct': avg_winner,
            'avg_loser_pct': avg_loser,
            'profit_factor': profit_factor,
            'total_pnl': trades_df['pnl'].sum(),
            'initial_capital': config.INITIAL_CAPITAL,
            'final_equity': final_equity,
            'total_return': total_return,
            'annual_return': annual_return,
            'max_drawdown': max_drawdown,
            'sharpe_ratio': sharpe,
            'avg_days_held': avg_days_held,
            'avg_winner_days': avg_winner_days,
            'avg_loser_days': avg_loser_days,
            'exit_reasons': exit_reasons,
            'best_trades': best_trades,
            'worst_trades': worst_trades,
            'trades_df': trades_df,
            'equity_df': equity_df,
        }

        return report


def print_report(report):
    """Pretty print backtest results."""
    if 'error' in report:
        print(f"Backtest Error: {report['error']}")
        return

    print("\n" + "=" * 70)
    print("  BACKTEST RESULTS: Multi-Timeframe MACD Strategy (Nasdaq 100)")
    print("=" * 70)

    print(f"\n  Initial Capital:     ${report['initial_capital']:>12,.0f}")
    print(f"  Final Equity:        ${report['final_equity']:>12,.0f}")
    print(f"  Total Return:        {report['total_return']:>12.1%}")
    print(f"  Annualized Return:   {report['annual_return']:>12.1%}")
    print(f"  Max Drawdown:        {report['max_drawdown']:>12.1%}")
    print(f"  Sharpe Ratio:        {report['sharpe_ratio']:>12.2f}")

    print(f"\n  --- Trade Statistics ---")
    print(f"  Total Trades:        {report['total_trades']:>8}")
    print(f"  Winners:             {report['winners']:>8}  ({report['win_rate']:.1%})")
    print(f"  Losers:              {report['losers']:>8}")
    print(f"  Profit Factor:       {report['profit_factor']:>8.2f}")
    print(f"  Avg Winner:          {report['avg_winner_pct']:>8.1%}")
    print(f"  Avg Loser:           {report['avg_loser_pct']:>8.1%}")

    print(f"\n  --- Holding Period ---")
    print(f"  Avg Days Held:       {report['avg_days_held']:>8.0f}")
    print(f"  Avg Winner Days:     {report['avg_winner_days']:>8.0f}")
    print(f"  Avg Loser Days:      {report['avg_loser_days']:>8.0f}")

    print(f"\n  --- Exit Reasons ---")
    for reason, count in report['exit_reasons'].items():
        print(f"  {reason:<25} {count:>5}")

    print(f"\n  --- Top 5 Winners ---")
    for t in report['best_trades']:
        entry_d = t['entry_date']
        if hasattr(entry_d, 'strftime'):
            entry_d = entry_d.strftime('%Y-%m-%d')
        print(f"  {t['ticker']:<6} {entry_d}  {t['pnl_pct']:>+7.1%}  ({t['days_held']} days)")

    print(f"\n  --- Top 5 Losers ---")
    for t in report['worst_trades']:
        entry_d = t['entry_date']
        if hasattr(entry_d, 'strftime'):
            entry_d = entry_d.strftime('%Y-%m-%d')
        print(f"  {t['ticker']:<6} {entry_d}  {t['pnl_pct']:>+7.1%}  ({t['days_held']} days)")

    print("\n" + "=" * 70)
