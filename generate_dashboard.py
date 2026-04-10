"""
Generates a self-contained HTML dashboard from portfolio.json, trades.csv, and scan_log.csv.
Run after each scan to keep the dashboard current.
"""

import json
import os
import csv
from datetime import datetime

DIR = os.path.dirname(os.path.abspath(__file__))
PORTFOLIO_FILE = os.path.join(DIR, 'portfolio.json')
TRADE_LOG_FILE = os.path.join(DIR, 'trades.csv')
SCAN_LOG_FILE = os.path.join(DIR, 'scan_log.csv')
DASHBOARD_FILE = os.path.join(DIR, 'dashboard.html')
INITIAL_CAPITAL = 100_000


def load_portfolio():
    if os.path.exists(PORTFOLIO_FILE):
        with open(PORTFOLIO_FILE, 'r') as f:
            return json.load(f)
    return {'cash': INITIAL_CAPITAL, 'positions': {}, 'last_scan': 'Never'}


def load_trades():
    trades = []
    if os.path.exists(TRADE_LOG_FILE):
        with open(TRADE_LOG_FILE, 'r') as f:
            reader = csv.DictReader(f)
            for row in reader:
                trades.append(row)
    return trades


def load_scan_log():
    log = []
    if os.path.exists(SCAN_LOG_FILE):
        with open(SCAN_LOG_FILE, 'r') as f:
            reader = csv.DictReader(f)
            for row in reader:
                log.append(row)
    return log


def compute_stats(trades):
    sells = [t for t in trades if t.get('action') == 'SELL' and t.get('pnl')]
    if not sells:
        return {
            'total_trades': 0, 'winners': 0, 'losers': 0, 'win_rate': 0,
            'total_pnl': 0, 'avg_winner': 0, 'avg_loser': 0, 'profit_factor': 0,
            'best_trade': None, 'worst_trade': None,
        }

    pnls = [float(t['pnl']) for t in sells]
    winners = [p for p in pnls if p > 0]
    losers = [p for p in pnls if p <= 0]

    return {
        'total_trades': len(sells),
        'winners': len(winners),
        'losers': len(losers),
        'win_rate': len(winners) / len(sells) if sells else 0,
        'total_pnl': sum(pnls),
        'avg_winner': sum(winners) / len(winners) if winners else 0,
        'avg_loser': sum(losers) / len(losers) if losers else 0,
        'profit_factor': (sum(winners) / abs(sum(losers))) if losers and sum(losers) != 0 else float('inf'),
        'best_trade': max(sells, key=lambda t: float(t['pnl'])) if sells else None,
        'worst_trade': min(sells, key=lambda t: float(t['pnl'])) if sells else None,
    }


def generate_html():
    portfolio = load_portfolio()
    trades = load_trades()
    scan_log = load_scan_log()
    stats = compute_stats(trades)

    # Estimate portfolio value (cash + positions at entry price as fallback)
    positions = portfolio.get('positions', {})
    est_value = portfolio.get('cash', INITIAL_CAPITAL)
    for ticker, pos in positions.items():
        est_value += pos.get('shares', 0) * pos.get('entry_price', 0)

    total_return = (est_value - INITIAL_CAPITAL) / INITIAL_CAPITAL * 100

    # Equity history from scan log
    equity_points = []
    for entry in scan_log:
        equity_points.append({
            'date': entry.get('date', ''),
            'value': float(entry.get('portfolio_value', INITIAL_CAPITAL)),
        })

    # Recent trades (last 20)
    recent_sells = [t for t in trades if t.get('action') == 'SELL'][-20:]
    recent_sells.reverse()

    # Build positions table rows
    pos_rows = ""
    for ticker, pos in positions.items():
        entry_price = pos.get('entry_price', 0)
        stop = pos.get('current_stop', pos.get('stop', 0))
        shares = pos.get('shares', 0)
        entry_date = pos.get('entry_date', '')
        days_held = ''
        if entry_date:
            try:
                days_held = (datetime.now() - datetime.fromisoformat(entry_date)).days
            except:
                days_held = '?'
        risk_pct = ((entry_price - stop) / entry_price * 100) if entry_price > 0 else 0
        pos_rows += f"""
        <tr>
            <td><span class="ticker">{ticker}</span></td>
            <td>${entry_price:.2f}</td>
            <td>${stop:.2f}</td>
            <td>{shares}</td>
            <td>${shares * entry_price:,.0f}</td>
            <td>{days_held}d</td>
            <td class="neg">-{risk_pct:.1f}%</td>
        </tr>"""

    if not pos_rows:
        pos_rows = '<tr><td colspan="7" style="text-align:center;color:#555577;padding:24px;">No open positions</td></tr>'

    # Build recent trades rows
    trade_rows = ""
    for t in recent_sells:
        pnl = float(t.get('pnl', 0))
        cls = "pos" if pnl > 0 else "neg"
        reason = t.get('reason', '').replace('_', ' ')
        trade_rows += f"""
        <tr>
            <td><span class="ticker">{t.get('ticker', '')}</span></td>
            <td>{t.get('date', '')}</td>
            <td>${float(t.get('price', 0)):.2f}</td>
            <td>{t.get('shares', '')}</td>
            <td class="{cls}">${pnl:+,.0f}</td>
            <td><span class="reason-badge">{reason}</span></td>
        </tr>"""

    if not trade_rows:
        trade_rows = '<tr><td colspan="6" style="text-align:center;color:#555577;padding:24px;">No trades yet</td></tr>'

    # Equity chart data
    equity_js = json.dumps(equity_points)

    html = f"""<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>MACD Scanner Dashboard</title>
<style>
* {{ margin: 0; padding: 0; box-sizing: border-box; }}
body {{
    background: #0a0a14;
    color: #c8c8e0;
    font-family: -apple-system, BlinkMacSystemFont, 'SF Pro Display', 'Segoe UI', sans-serif;
    padding: 0;
    min-height: 100vh;
}}
.header {{
    background: linear-gradient(135deg, #12122a 0%, #1a1a3a 100%);
    padding: 28px 36px;
    border-bottom: 1px solid #2a2a4a;
    display: flex;
    justify-content: space-between;
    align-items: center;
}}
.header h1 {{ font-size: 22px; font-weight: 700; color: #e0e0ff; }}
.header .sub {{ color: #5555aa; font-size: 13px; margin-top: 4px; }}
.header .return-badge {{
    font-size: 36px;
    font-weight: 800;
    font-family: 'SF Mono', 'Menlo', monospace;
    color: {'#22c55e' if total_return >= 0 else '#ef4444'};
}}
.header .return-label {{ font-size: 11px; color: #6666aa; text-transform: uppercase; letter-spacing: 1px; text-align: right; }}

.stats-grid {{
    display: grid;
    grid-template-columns: repeat(auto-fit, minmax(170px, 1fr));
    gap: 12px;
    padding: 20px 36px;
}}
.stat-card {{
    background: #12122a;
    border: 1px solid #2a2a4a;
    border-radius: 10px;
    padding: 16px 20px;
}}
.stat-card .label {{ font-size: 11px; color: #5555aa; text-transform: uppercase; letter-spacing: 0.8px; }}
.stat-card .value {{ font-size: 24px; font-weight: 700; margin-top: 4px; font-family: 'SF Mono', 'Menlo', monospace; }}
.stat-card .detail {{ font-size: 11px; color: #444466; margin-top: 2px; }}

.section {{
    padding: 20px 36px;
}}
.section h2 {{
    font-size: 16px;
    font-weight: 600;
    color: #8888bb;
    margin-bottom: 14px;
    display: flex;
    align-items: center;
    gap: 8px;
}}
.section h2 .dot {{
    width: 8px; height: 8px; border-radius: 50%;
    display: inline-block;
}}
.dot.green {{ background: #22c55e; box-shadow: 0 0 6px #22c55e88; }}
.dot.blue {{ background: #3b82f6; box-shadow: 0 0 6px #3b82f688; }}
.dot.amber {{ background: #f59e0b; box-shadow: 0 0 6px #f59e0b88; }}

table {{
    width: 100%;
    border-collapse: collapse;
    background: #12122a;
    border-radius: 10px;
    overflow: hidden;
    border: 1px solid #2a2a4a;
}}
thead th {{
    text-align: left;
    padding: 12px 16px;
    font-size: 11px;
    text-transform: uppercase;
    letter-spacing: 0.8px;
    color: #5555aa;
    background: #0f0f22;
    border-bottom: 1px solid #2a2a4a;
}}
tbody td {{
    padding: 10px 16px;
    font-size: 13px;
    border-bottom: 1px solid #1a1a30;
    font-family: 'SF Mono', 'Menlo', monospace;
}}
tbody tr:hover {{ background: #1a1a35; }}
.ticker {{
    background: #2a2a5a;
    color: #a0a0ff;
    padding: 3px 8px;
    border-radius: 4px;
    font-weight: 600;
    font-size: 12px;
}}
.pos {{ color: #22c55e; font-weight: 600; }}
.neg {{ color: #ef4444; font-weight: 600; }}
.reason-badge {{
    background: #1a1a35;
    color: #6666aa;
    padding: 3px 8px;
    border-radius: 4px;
    font-size: 11px;
}}

.chart-container {{
    background: #12122a;
    border: 1px solid #2a2a4a;
    border-radius: 10px;
    padding: 20px;
    height: 300px;
    position: relative;
}}
canvas {{ width: 100% !important; height: 260px !important; }}

.status-bar {{
    display: flex;
    justify-content: space-between;
    align-items: center;
    padding: 12px 36px;
    background: #0f0f20;
    border-top: 1px solid #2a2a4a;
    font-size: 12px;
    color: #444466;
    position: fixed;
    bottom: 0;
    left: 0;
    right: 0;
}}
.status-bar .live {{ color: #22c55e; }}

.two-col {{ display: grid; grid-template-columns: 1fr 1fr; gap: 20px; }}
@media (max-width: 900px) {{ .two-col {{ grid-template-columns: 1fr; }} }}
</style>
</head>
<body>

<div class="header">
    <div>
        <h1>MACD Multi-Timeframe Scanner</h1>
        <div class="sub">Nasdaq 100 &middot; Paper Trading &middot; Daily/Weekly MACD + 200 SMA + Relative Strength</div>
    </div>
    <div>
        <div class="return-label">Total Return</div>
        <div class="return-badge">{'+' if total_return >= 0 else ''}{total_return:.1f}%</div>
    </div>
</div>

<div class="stats-grid">
    <div class="stat-card">
        <div class="label">Portfolio Value</div>
        <div class="value" style="color:#e0e0ff">${est_value:,.0f}</div>
        <div class="detail">started at $100,000</div>
    </div>
    <div class="stat-card">
        <div class="label">Cash Available</div>
        <div class="value" style="color:#3b82f6">${portfolio.get('cash', 0):,.0f}</div>
        <div class="detail">{len(positions)} open positions</div>
    </div>
    <div class="stat-card">
        <div class="label">Total Trades</div>
        <div class="value" style="color:#8b5cf6">{stats['total_trades']}</div>
        <div class="detail">{stats['winners']}W / {stats['losers']}L</div>
    </div>
    <div class="stat-card">
        <div class="label">Win Rate</div>
        <div class="value" style="color:#f59e0b">{stats['win_rate']*100:.1f}%</div>
        <div class="detail">profit factor: {stats['profit_factor']:.2f}</div>
    </div>
    <div class="stat-card">
        <div class="label">Total P&L</div>
        <div class="value" style="color:{'#22c55e' if stats['total_pnl'] >= 0 else '#ef4444'}">${stats['total_pnl']:+,.0f}</div>
        <div class="detail">realized trades only</div>
    </div>
    <div class="stat-card">
        <div class="label">Avg Winner / Loser</div>
        <div class="value" style="color:#06b6d4;font-size:18px">${stats['avg_winner']:+,.0f} / ${stats['avg_loser']:,.0f}</div>
        <div class="detail">per trade</div>
    </div>
</div>

<div class="section">
    <h2><span class="dot blue"></span> Equity Curve</h2>
    <div class="chart-container">
        <canvas id="equityChart"></canvas>
    </div>
</div>

<div class="section two-col">
    <div>
        <h2><span class="dot green"></span> Open Positions</h2>
        <table>
            <thead><tr>
                <th>Ticker</th><th>Entry</th><th>Stop</th><th>Shares</th><th>Value</th><th>Held</th><th>Risk</th>
            </tr></thead>
            <tbody>{pos_rows}</tbody>
        </table>
    </div>
    <div>
        <h2><span class="dot amber"></span> Recent Trades</h2>
        <table>
            <thead><tr>
                <th>Ticker</th><th>Date</th><th>Price</th><th>Shares</th><th>P&L</th><th>Reason</th>
            </tr></thead>
            <tbody>{trade_rows}</tbody>
        </table>
    </div>
</div>

<div style="height:60px"></div>

<div class="status-bar">
    <span>Last scan: <span class="live">{portfolio.get('last_scan', 'Never')}</span></span>
    <span>Strategy: MACD(12,26,9) + 200SMA + RS | ATR Stop 2.5x | Max 8 positions | 1.2% risk/trade</span>
    <span>Auto-refreshes with each scan</span>
</div>

<script>
const equityData = {equity_js};

function drawChart() {{
    const canvas = document.getElementById('equityChart');
    if (!canvas || equityData.length === 0) return;
    if (equityData.length === 1) {{{{
        const ctx = canvas.getContext("2d");
        const rect = canvas.parentElement.getBoundingClientRect();
        canvas.width = rect.width - 40;
        canvas.height = 260;
        const w = canvas.width, h = canvas.height;
        const pad = {{{{ top: 20, right: 20, bottom: 30, left: 65 }}}};
        const midY = h / 2;
        ctx.setLineDash([4, 4]);
        ctx.strokeStyle = "#555577"; ctx.lineWidth = 1;
        ctx.beginPath(); ctx.moveTo(pad.left, midY); ctx.lineTo(w - pad.right, midY); ctx.stroke();
        ctx.setLineDash([]); ctx.fillStyle = "#555577"; ctx.textAlign = "left";
        ctx.font = "11px SF Mono, Menlo, monospace";
        ctx.fillText("$100k start", pad.left + 4, midY - 6);
        const dotX = w / 2, dotY = midY - 10;
        ctx.beginPath(); ctx.arc(dotX, dotY, 6, 0, Math.PI * 2);
        ctx.fillStyle = "#3b82f6"; ctx.fill();
        ctx.fillStyle = "#e2e8f0"; ctx.textAlign = "center";
        ctx.fillText("$" + (equityData[0].value/1000).toFixed(1) + "k", dotX, dotY - 14);
        ctx.fillStyle = "#666688";
        ctx.fillText("Chart appears after 2+ scans", w / 2, h - 8);
        return;
    }}}}
    const ctx = canvas.getContext('2d');
    const rect = canvas.parentElement.getBoundingClientRect();
    canvas.width = rect.width - 40;
    canvas.height = 260;

    const w = canvas.width;
    const h = canvas.height;
    const pad = {{ top: 20, right: 20, bottom: 30, left: 65 }};
    const plotW = w - pad.left - pad.right;
    const plotH = h - pad.top - pad.bottom;

    const values = equityData.map(d => d.value);
    const minV = Math.min(...values) * 0.95;
    const maxV = Math.max(...values) * 1.05;

    const xScale = (i) => pad.left + (i / (equityData.length - 1)) * plotW;
    const yScale = (v) => pad.top + plotH - ((v - minV) / (maxV - minV)) * plotH;

    // Grid
    ctx.strokeStyle = '#1a1a35';
    ctx.lineWidth = 1;
    for (let i = 0; i <= 5; i++) {{
        const y = pad.top + (plotH / 5) * i;
        ctx.beginPath();
        ctx.moveTo(pad.left, y);
        ctx.lineTo(w - pad.right, y);
        ctx.stroke();

        const val = maxV - (i / 5) * (maxV - minV);
        ctx.fillStyle = '#444466';
        ctx.font = '11px SF Mono, Menlo, monospace';
        ctx.textAlign = 'right';
        ctx.fillText('$' + (val/1000).toFixed(0) + 'k', pad.left - 8, y + 4);
    }}

    // Date labels
    ctx.fillStyle = '#444466';
    ctx.font = '11px SF Mono, Menlo, monospace';
    ctx.textAlign = 'center';
    const step = Math.max(1, Math.floor(equityData.length / 6));
    for (let i = 0; i < equityData.length; i += step) {{
        ctx.fillText(equityData[i].date.slice(0, 7), xScale(i), h - 5);
    }}

    // Fill gradient
    const gradient = ctx.createLinearGradient(0, pad.top, 0, h - pad.bottom);
    gradient.addColorStop(0, 'rgba(59,130,246,0.25)');
    gradient.addColorStop(1, 'rgba(59,130,246,0.02)');

    ctx.beginPath();
    ctx.moveTo(xScale(0), h - pad.bottom);
    for (let i = 0; i < equityData.length; i++) {{
        ctx.lineTo(xScale(i), yScale(equityData[i].value));
    }}
    ctx.lineTo(xScale(equityData.length - 1), h - pad.bottom);
    ctx.closePath();
    ctx.fillStyle = gradient;
    ctx.fill();

    // Line
    ctx.beginPath();
    ctx.moveTo(xScale(0), yScale(equityData[0].value));
    for (let i = 1; i < equityData.length; i++) {{
        ctx.lineTo(xScale(i), yScale(equityData[i].value));
    }}
    ctx.strokeStyle = '#3b82f6';
    ctx.lineWidth = 2;
    ctx.stroke();

    // $100k baseline
    const baseY = yScale(100000);
    if (baseY > pad.top && baseY < h - pad.bottom) {{
        ctx.setLineDash([4, 4]);
        ctx.strokeStyle = '#555577';
        ctx.lineWidth = 1;
        ctx.beginPath();
        ctx.moveTo(pad.left, baseY);
        ctx.lineTo(w - pad.right, baseY);
        ctx.stroke();
        ctx.setLineDash([]);
        ctx.fillStyle = '#555577';
        ctx.textAlign = 'left';
        ctx.fillText('$100k start', pad.left + 4, baseY - 6);
    }}

    // Current value dot
    const lastI = equityData.length - 1;
    const lastX = xScale(lastI);
    const lastY = yScale(equityData[lastI].value);
    ctx.beginPath();
    ctx.arc(lastX, lastY, 5, 0, Math.PI * 2);
    ctx.fillStyle = '#3b82f6';
    ctx.fill();
    ctx.strokeStyle = '#0a0a14';
    ctx.lineWidth = 2;
    ctx.stroke();
}}

window.addEventListener('load', drawChart);
window.addEventListener('resize', drawChart);
</script>

</body>
</html>"""

    with open(DASHBOARD_FILE, 'w') as f:
        f.write(html)

    print(f"Dashboard generated: {DASHBOARD_FILE}")


if __name__ == '__main__':
    generate_html()
