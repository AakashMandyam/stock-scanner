"""
Configuration for the Multi-Timeframe MACD Stock Scanner
Target: Nasdaq 100 universe, daily/weekly timeframes
"""

# === Universe ===
# Nasdaq 100 constituents (QQQ holdings)
# We fetch these dynamically, but here's a fallback list
BENCHMARK = "QQQ"

# === MACD Parameters ===
MACD_FAST = 12
MACD_SLOW = 26
MACD_SIGNAL = 9

# === Trend Filter ===
TREND_SMA_PERIOD = 200  # Must be above this to consider long entries

# === Market Regime Filter ===
# Only trade when QQQ itself is in an uptrend — kills signals during bear markets
REGIME_FILTER = True
REGIME_SMA_PERIOD = 50     # QQQ must be above its 50-day SMA
REGIME_SMA_LONG = 200      # AND QQQ 50 SMA must be above 200 SMA (golden cross)

# === MACD Histogram Divergence Filter ===
# Require bullish divergence (price lower low + histogram higher low) for higher quality signals
REQUIRE_DIVERGENCE = False  # If True, only enter on divergence (much fewer trades, higher quality)

# === Consecutive Loss Cooldown ===
# After N consecutive stop-loss exits, pause new entries for M days
COOLDOWN_AFTER_LOSSES = 3   # Pause after this many consecutive stops
COOLDOWN_DAYS = 10          # Number of trading days to pause

# === RSI Mean Reversion Entry Enhancement ===
RSI_ENABLED = False          # Disabled — didn't improve Sharpe
RSI_PERIOD = 5
RSI_OVERSOLD = 30
RSI_RECOVERY = 50

# === Entry Signal Parameters ===
# Weekly: histogram must be turning up (2 consecutive increasing bars)
WEEKLY_HIST_TURN_BARS = 2
# Daily: histogram must have been negative for at least N bars before turning
DAILY_PULLBACK_MIN_BARS = 3    # Pullback depth
# Daily: need N consecutive increasing histogram bars to trigger
DAILY_HIST_TURN_BARS = 2

# === Relative Strength ===
RS_LOOKBACK_DAYS = 63  # ~3 months of trading days
RS_MIN_RATIO = 1.0     # At parity with index is fine — RS used for ranking not filtering

# === Volume Confirmation ===
VOLUME_AVG_PERIOD = 20
VOLUME_SURGE_RATIO = 1.0  # No volume filter — use it for ranking instead

# === Risk Management ===
INITIAL_CAPITAL = 100_000
RISK_PER_TRADE_PCT = 0.012   # 1.2% risk per trade
ATR_PERIOD = 14
ATR_STOP_MULTIPLIER = 2.5    # 2.5x ATR
MAX_POSITIONS = 8

# === Volatility Scaling ===
VOL_SCALE_ENABLED = False
VOL_SCALE_DRAWDOWN_THRESHOLD = -0.05
VOL_SCALE_MIN = 0.3

# === Exit Rules ===
WEEKLY_EMA_EXIT_PERIOD = 15   # 15-week EMA — between v1 (10) and v2 (20)
WEEKLY_HIST_EXIT_BARS = 2     # Back to 2 — this exit doesn't trigger much anyway

# === Backtest Settings ===
BACKTEST_START = "2015-01-01"
BACKTEST_END = "2026-04-08"
COMMISSION_PCT = 0.001  # 0.1% round trip (conservative for modern brokers)

# === Data Settings ===
DATA_LOOKBACK_DAYS = 600  # Days of daily data to fetch for live scanning
