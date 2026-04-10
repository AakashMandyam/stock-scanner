#!/bin/bash
# Setup script for the MACD Stock Scanner
# Run this once: bash ~/Documents/stock_scanner/setup.sh

set -e

echo "=== MACD Stock Scanner Setup ==="
echo ""

# 1. Install Python dependencies
echo "[1/4] Installing Python dependencies..."
pip3 install --user yfinance pandas numpy tabulate 2>/dev/null || pip3 install yfinance pandas numpy tabulate
echo "  Done."

# 2. Create logs directory
echo "[2/4] Creating logs directory..."
mkdir -p ~/Documents/stock_scanner/logs
echo "  Done."

# 3. Test the scanner works
echo "[3/4] Testing scanner..."
cd ~/Documents/stock_scanner
python3 -c "import yfinance, pandas, numpy; print('  All dependencies OK.')"

# 4. Install launchd job (runs daily at 5 PM weekdays)
echo "[4/4] Installing daily schedule (launchd)..."
cp ~/Documents/stock_scanner/com.stockscanner.daily.plist ~/Library/LaunchAgents/
launchctl unload ~/Library/LaunchAgents/com.stockscanner.daily.plist 2>/dev/null || true
launchctl load ~/Library/LaunchAgents/com.stockscanner.daily.plist
echo "  Scheduled: daily at 5:00 PM"

echo ""
echo "=== Setup Complete ==="
echo ""
echo "The scanner will run automatically at 5 PM every day."
echo "It does NOT require the Claude app to be open."
echo ""
echo "Useful commands:"
echo "  Run manually:    cd ~/Documents/stock_scanner && python3 main.py scan"
echo "  Run backtest:    cd ~/Documents/stock_scanner && python3 main.py backtest"
echo "  Check status:    cd ~/Documents/stock_scanner && python3 main.py status"
echo "  View dashboard:  open ~/Documents/stock_scanner/dashboard.html"
echo "  View logs:       cat ~/Documents/stock_scanner/logs/scan_stdout.log"
echo ""
echo "To stop the daily schedule:"
echo "  launchctl unload ~/Library/LaunchAgents/com.stockscanner.daily.plist"
echo ""
echo "To restart it:"
echo "  launchctl load ~/Library/LaunchAgents/com.stockscanner.daily.plist"
