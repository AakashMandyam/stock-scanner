import { useState, useMemo } from "react";
import { LineChart, Line, XAxis, YAxis, CartesianGrid, Tooltip, ResponsiveContainer, BarChart, Bar, Cell, PieChart, Pie, AreaChart, Area, Legend } from "recharts";

const EQUITY_DATA = [{"date": "2015-01-02", "equity": 100000, "drawdown": 0}, {"date": "2015-02-18", "equity": 100000, "drawdown": 0}, {"date": "2015-09-29", "equity": 100000, "drawdown": 0}, {"date": "2015-12-28", "equity": 98633, "drawdown": -4.07}, {"date": "2016-02-24", "equity": 92605, "drawdown": -9.93}, {"date": "2016-07-20", "equity": 97302, "drawdown": -5.36}, {"date": "2016-09-22", "equity": 106235, "drawdown": -0.51}, {"date": "2017-03-17", "equity": 111508, "drawdown": 0}, {"date": "2017-07-31", "equity": 123029, "drawdown": -2.25}, {"date": "2017-10-26", "equity": 130281, "drawdown": 0}, {"date": "2018-01-22", "equity": 149375, "drawdown": 0}, {"date": "2018-05-29", "equity": 148110, "drawdown": -1.53}, {"date": "2018-10-30", "equity": 154045, "drawdown": -10.01}, {"date": "2019-01-31", "equity": 154045, "drawdown": -10.01}, {"date": "2019-06-19", "equity": 154290, "drawdown": -9.87}, {"date": "2019-08-28", "equity": 146381, "drawdown": -14.49}, {"date": "2019-12-30", "equity": 147541, "drawdown": -13.81}, {"date": "2020-04-03", "equity": 150987, "drawdown": -11.8}, {"date": "2020-06-01", "equity": 148129, "drawdown": -13.47}, {"date": "2021-02-23", "equity": 179095, "drawdown": -5.34}, {"date": "2021-05-26", "equity": 171250, "drawdown": -9.49}, {"date": "2021-08-12", "equity": 205165, "drawdown": 0}, {"date": "2022-02-07", "equity": 202094, "drawdown": -7.29}, {"date": "2022-06-22", "equity": 202092, "drawdown": -7.29}, {"date": "2022-12-16", "equity": 202092, "drawdown": -7.29}, {"date": "2023-03-23", "equity": 211614, "drawdown": -2.92}, {"date": "2023-08-24", "equity": 243428, "drawdown": -7.53}, {"date": "2023-12-01", "equity": 242103, "drawdown": -8.03}, {"date": "2024-03-06", "equity": 253491, "drawdown": -5.47}, {"date": "2024-05-23", "equity": 226230, "drawdown": -15.64}, {"date": "2024-09-06", "equity": 209426, "drawdown": -21.9}, {"date": "2024-12-10", "equity": 230094, "drawdown": -14.19}, {"date": "2025-04-08", "equity": 228148, "drawdown": -14.92}, {"date": "2025-07-09", "equity": 231009, "drawdown": -13.85}, {"date": "2026-01-13", "equity": 274807, "drawdown": 0}, {"date": "2026-04-07", "equity": 260691, "drawdown": -8.93}];

const STATS = {
  totalTrades: 509, winners: 223, losers: 286, winRate: 0.438,
  avgWinnerPct: 12.3, avgLoserPct: -5.8, profitFactor: 1.48,
  initialCapital: 100000, finalEquity: 260691,
  totalReturnPct: 160.7, annualizedReturn: 8.9,
  maxDrawdown: -22.0, sharpeRatio: 0.85,
  avgDaysHeld: 32, avgWinnerDays: 50, avgLoserDays: 18,
};

const EXIT_REASONS = [
  { name: "Stop Loss", value: 422, color: "#ef4444" },
  { name: "Weekly EMA Break", value: 57, color: "#f59e0b" },
  { name: "Weekly Hist Negative", value: 30, color: "#3b82f6" },
];

const TOP_WINNERS = [
  { ticker: "APP", date: "2024-10-22", pnl: 101.1, days: 34 },
  { ticker: "AMD", date: "2018-07-09", pnl: 86.0, days: 81 },
  { ticker: "COIN", date: "2024-02-01", pnl: 81.2, days: 42 },
  { ticker: "MRNA", date: "2021-06-28", pnl: 72.8, days: 44 },
  { ticker: "PLTR", date: "2025-01-15", pnl: 64.5, days: 35 },
];

const TOP_LOSERS = [
  { ticker: "TTD", date: "2017-10-06", pnl: -20.7, days: 35 },
  { ticker: "COIN", date: "2024-12-06", pnl: -20.3, days: 13 },
  { ticker: "DDOG", date: "2020-08-04", pnl: -20.1, days: 3 },
  { ticker: "NVDA", date: "2024-03-25", pnl: -19.8, days: 25 },
  { ticker: "MRVL", date: "2025-01-17", pnl: -19.6, days: 10 },
];

const ITERATION_HISTORY = [
  { version: "v1", sharpe: 0.77, maxDD: -36.1, annual: 11.7, trades: 1502, pf: 1.36, note: "Baseline — too many trades" },
  { version: "v3", sharpe: 0.77, maxDD: -33.8, annual: 9.8, trades: 917, pf: 1.35, note: "Tighter entries" },
  { version: "v4", sharpe: 0.71, maxDD: -25.8, annual: 8.5, trades: 609, pf: 1.40, note: "+ Regime filter" },
  { version: "v5", sharpe: 0.69, maxDD: -23.3, annual: 7.1, trades: 414, pf: 1.35, note: "+ Vol scaling + cooldown" },
  { version: "v6", sharpe: 0.74, maxDD: -29.4, annual: 7.8, trades: 388, pf: 1.46, note: "+ RSI filter" },
  { version: "v7*", sharpe: 0.85, maxDD: -22.0, annual: 8.9, trades: 509, pf: 1.48, note: "FINAL — v3 + regime only" },
];

function StatCard({ label, value, sub, color }) {
  return (
    <div style={{ background: "#111126", borderRadius: 12, padding: "16px 20px", border: "1px solid #222244" }}>
      <div style={{ fontSize: 11, color: "#6666aa", textTransform: "uppercase", letterSpacing: 1, fontWeight: 500 }}>{label}</div>
      <div style={{ fontSize: 26, fontWeight: 700, color: color || "#e0e0ff", marginTop: 4, fontFamily: "'SF Mono', Menlo, monospace" }}>{value}</div>
      {sub && <div style={{ fontSize: 11, color: "#444466", marginTop: 2 }}>{sub}</div>}
    </div>
  );
}

function TradeRow({ trade, isWinner }) {
  const c = isWinner ? "#22c55e" : "#ef4444";
  return (
    <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", padding: "10px 16px", borderBottom: "1px solid #1a1a30" }}>
      <div style={{ display: "flex", alignItems: "center", gap: 10 }}>
        <span style={{ background: isWinner ? "#22c55e18" : "#ef444418", color: c, fontWeight: 700, fontSize: 13, padding: "3px 9px", borderRadius: 5, fontFamily: "monospace" }}>{trade.ticker}</span>
        <span style={{ color: "#555577", fontSize: 12 }}>{trade.date}</span>
      </div>
      <div style={{ display: "flex", alignItems: "center", gap: 14 }}>
        <span style={{ color: "#555577", fontSize: 11 }}>{trade.days}d</span>
        <span style={{ color: c, fontWeight: 700, fontSize: 14, fontFamily: "monospace", minWidth: 65, textAlign: "right" }}>{trade.pnl > 0 ? "+" : ""}{trade.pnl.toFixed(1)}%</span>
      </div>
    </div>
  );
}

const TABS = ["Overview", "Equity Curve", "Drawdown", "Trades", "Iterations"];

export default function Dashboard() {
  const [tab, setTab] = useState("Overview");
  const expectancy = (STATS.winRate * STATS.avgWinnerPct + (1 - STATS.winRate) * STATS.avgLoserPct).toFixed(2);
  const rrRatio = (STATS.avgWinnerPct / Math.abs(STATS.avgLoserPct)).toFixed(2);
  const fmtK = v => `$${(v / 1000).toFixed(0)}k`;

  return (
    <div style={{ background: "#0a0a16", color: "#d0d0ee", fontFamily: "-apple-system, BlinkMacSystemFont, 'Segoe UI', sans-serif", minHeight: "100vh" }}>

      {/* HEADER */}
      <div style={{ background: "linear-gradient(135deg, #0f0f28, #161640)", padding: "28px 36px 22px", borderBottom: "1px solid #222244" }}>
        <div style={{ display: "flex", justifyContent: "space-between", alignItems: "flex-start" }}>
          <div>
            <h1 style={{ margin: 0, fontSize: 24, fontWeight: 700, color: "#e8e8ff" }}>MACD Multi-Timeframe Scanner</h1>
            <p style={{ margin: "5px 0 0", color: "#5555aa", fontSize: 13 }}>Nasdaq 100 &middot; Backtest Jan 2015 — Apr 2026 &middot; v7 Final &middot; Paper Trading Live</p>
          </div>
          <div style={{ textAlign: "right" }}>
            <div style={{ fontSize: 10, color: "#5555aa", textTransform: "uppercase", letterSpacing: 1.5 }}>Total Return</div>
            <div style={{ fontSize: 38, fontWeight: 800, fontFamily: "'SF Mono', Menlo, monospace", color: "#22c55e", lineHeight: 1.1 }}>+{STATS.totalReturnPct}%</div>
            <div style={{ fontSize: 12, color: "#444466", marginTop: 2 }}>$100k → ${(STATS.finalEquity / 1000).toFixed(0)}k</div>
          </div>
        </div>

        <div style={{ display: "grid", gridTemplateColumns: "repeat(auto-fit, minmax(145px, 1fr))", gap: 10, marginTop: 20 }}>
          <StatCard label="Annual Return" value={`${STATS.annualizedReturn}%`} sub="CAGR" color="#3b82f6" />
          <StatCard label="Sharpe Ratio" value={STATS.sharpeRatio.toFixed(2)} sub="risk-adjusted" color="#f59e0b" />
          <StatCard label="Max Drawdown" value={`${STATS.maxDrawdown}%`} sub="peak to trough" color="#ef4444" />
          <StatCard label="Win Rate" value={`${(STATS.winRate * 100).toFixed(1)}%`} sub={`${STATS.winners}W / ${STATS.losers}L`} color="#8b5cf6" />
          <StatCard label="Profit Factor" value={STATS.profitFactor.toFixed(2)} sub="gain / loss ratio" color="#06b6d4" />
          <StatCard label="Expectancy" value={`+${expectancy}%`} sub="per trade avg" color="#22c55e" />
        </div>
      </div>

      {/* TABS */}
      <div style={{ display: "flex", borderBottom: "1px solid #222244", padding: "0 36px", background: "#0d0d20" }}>
        {TABS.map(t => (
          <button key={t} onClick={() => setTab(t)} style={{
            background: "none", border: "none", color: tab === t ? "#e0e0ff" : "#444466",
            fontSize: 13, fontWeight: tab === t ? 600 : 400, padding: "13px 18px",
            borderBottom: tab === t ? "2px solid #3b82f6" : "2px solid transparent",
            cursor: "pointer",
          }}>{t}</button>
        ))}
      </div>

      {/* CONTENT */}
      <div style={{ padding: "24px 36px" }}>

        {tab === "Overview" && (
          <div style={{ display: "grid", gridTemplateColumns: "1.2fr 0.8fr", gap: 20 }}>
            {/* Equity mini */}
            <div style={{ background: "#111126", borderRadius: 12, padding: 22, border: "1px solid #222244" }}>
              <div style={{ fontSize: 14, color: "#7777aa", fontWeight: 600, marginBottom: 14 }}>Equity Curve</div>
              <ResponsiveContainer width="100%" height={200}>
                <AreaChart data={EQUITY_DATA}>
                  <defs><linearGradient id="g1" x1="0" y1="0" x2="0" y2="1"><stop offset="0%" stopColor="#3b82f6" stopOpacity={0.3} /><stop offset="100%" stopColor="#3b82f6" stopOpacity={0} /></linearGradient></defs>
                  <CartesianGrid strokeDasharray="3 3" stroke="#1a1a35" />
                  <XAxis dataKey="date" tick={{ fill: "#444466", fontSize: 10 }} tickFormatter={d => d.slice(0, 4)} />
                  <YAxis tick={{ fill: "#444466", fontSize: 10 }} tickFormatter={fmtK} />
                  <Tooltip contentStyle={{ background: "#111126", border: "1px solid #3b82f6", borderRadius: 8, color: "#e0e0ff", fontSize: 12 }} formatter={v => [`$${v.toLocaleString()}`, "Equity"]} />
                  <Area type="monotone" dataKey="equity" stroke="#3b82f6" fill="url(#g1)" strokeWidth={2} dot={false} />
                </AreaChart>
              </ResponsiveContainer>
            </div>

            {/* Exit pie */}
            <div style={{ background: "#111126", borderRadius: 12, padding: 22, border: "1px solid #222244" }}>
              <div style={{ fontSize: 14, color: "#7777aa", fontWeight: 600, marginBottom: 14 }}>Exit Reasons</div>
              <ResponsiveContainer width="100%" height={200}>
                <PieChart>
                  <Pie data={EXIT_REASONS} dataKey="value" nameKey="name" cx="50%" cy="50%" innerRadius={45} outerRadius={75} paddingAngle={3}>
                    {EXIT_REASONS.map((e, i) => <Cell key={i} fill={e.color} />)}
                  </Pie>
                  <Tooltip contentStyle={{ background: "#111126", border: "1px solid #333355", borderRadius: 8, color: "#e0e0ff", fontSize: 12 }} />
                  <Legend wrapperStyle={{ fontSize: 11, color: "#7777aa" }} />
                </PieChart>
              </ResponsiveContainer>
            </div>

            {/* Stats grid */}
            <div style={{ background: "#111126", borderRadius: 12, padding: 22, border: "1px solid #222244" }}>
              <div style={{ fontSize: 14, color: "#7777aa", fontWeight: 600, marginBottom: 14 }}>Trade Profile</div>
              <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr", gap: 10 }}>
                {[
                  ["Total Trades", STATS.totalTrades],
                  ["Avg Hold", `${STATS.avgDaysHeld} days`],
                  ["Avg Winner", `+${STATS.avgWinnerPct}% (${STATS.avgWinnerDays}d)`],
                  ["Avg Loser", `${STATS.avgLoserPct}% (${STATS.avgLoserDays}d)`],
                  ["Risk/Reward", `${rrRatio}x`],
                  ["Expectancy", `+${expectancy}% / trade`],
                ].map(([l, v]) => (
                  <div key={l} style={{ padding: "9px 12px", background: "#0a0a16", borderRadius: 7 }}>
                    <div style={{ color: "#444466", fontSize: 10, textTransform: "uppercase" }}>{l}</div>
                    <div style={{ color: "#d0d0ee", fontSize: 15, fontWeight: 600, fontFamily: "monospace", marginTop: 2 }}>{v}</div>
                  </div>
                ))}
              </div>
            </div>

            {/* Parameters */}
            <div style={{ background: "#111126", borderRadius: 12, padding: 22, border: "1px solid #222244" }}>
              <div style={{ fontSize: 14, color: "#7777aa", fontWeight: 600, marginBottom: 14 }}>Strategy Parameters (v7 Final)</div>
              <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr", gap: 7 }}>
                {[
                  ["MACD", "12 / 26 / 9"],
                  ["Trend Filter", "200 SMA"],
                  ["Regime Filter", "QQQ 50>200 SMA"],
                  ["ATR Stop", "2.5x ATR(14)"],
                  ["Risk/Trade", "1.2%"],
                  ["Max Positions", "8"],
                  ["Weekly Exit", "15-week EMA"],
                  ["Pullback Bars", "3 min"],
                ].map(([l, v]) => (
                  <div key={l} style={{ display: "flex", justifyContent: "space-between", padding: "7px 11px", background: "#0a0a16", borderRadius: 5 }}>
                    <span style={{ color: "#444488", fontSize: 11 }}>{l}</span>
                    <span style={{ color: "#d0d0ee", fontSize: 11, fontFamily: "monospace", fontWeight: 600 }}>{v}</span>
                  </div>
                ))}
              </div>
            </div>
          </div>
        )}

        {tab === "Equity Curve" && (
          <div style={{ background: "#111126", borderRadius: 12, padding: 28, border: "1px solid #222244" }}>
            <div style={{ fontSize: 16, color: "#e0e0ff", fontWeight: 600, marginBottom: 18 }}>Portfolio Equity — $100k Starting Capital</div>
            <ResponsiveContainer width="100%" height={420}>
              <AreaChart data={EQUITY_DATA}>
                <defs><linearGradient id="g2" x1="0" y1="0" x2="0" y2="1"><stop offset="0%" stopColor="#3b82f6" stopOpacity={0.35} /><stop offset="100%" stopColor="#3b82f6" stopOpacity={0.02} /></linearGradient></defs>
                <CartesianGrid strokeDasharray="3 3" stroke="#1a1a35" />
                <XAxis dataKey="date" tick={{ fill: "#5555aa", fontSize: 11 }} />
                <YAxis tick={{ fill: "#5555aa", fontSize: 11 }} tickFormatter={fmtK} />
                <Tooltip contentStyle={{ background: "#111126", border: "1px solid #3b82f6", borderRadius: 8, color: "#e0e0ff" }} formatter={v => [`$${v.toLocaleString()}`, "Equity"]} />
                <Area type="monotone" dataKey="equity" stroke="#3b82f6" fill="url(#g2)" strokeWidth={2.5} dot={false} />
              </AreaChart>
            </ResponsiveContainer>
          </div>
        )}

        {tab === "Drawdown" && (
          <div style={{ background: "#111126", borderRadius: 12, padding: 28, border: "1px solid #222244" }}>
            <div style={{ fontSize: 16, color: "#e0e0ff", fontWeight: 600, marginBottom: 18 }}>Drawdown from Peak</div>
            <ResponsiveContainer width="100%" height={420}>
              <AreaChart data={EQUITY_DATA}>
                <defs><linearGradient id="g3" x1="0" y1="0" x2="0" y2="1"><stop offset="0%" stopColor="#ef4444" stopOpacity={0.05} /><stop offset="100%" stopColor="#ef4444" stopOpacity={0.35} /></linearGradient></defs>
                <CartesianGrid strokeDasharray="3 3" stroke="#1a1a35" />
                <XAxis dataKey="date" tick={{ fill: "#5555aa", fontSize: 11 }} />
                <YAxis tick={{ fill: "#5555aa", fontSize: 11 }} tickFormatter={v => `${v}%`} />
                <Tooltip contentStyle={{ background: "#111126", border: "1px solid #ef4444", borderRadius: 8, color: "#e0e0ff" }} formatter={v => [`${v}%`, "Drawdown"]} />
                <Area type="monotone" dataKey="drawdown" stroke="#ef4444" fill="url(#g3)" strokeWidth={2} dot={false} />
              </AreaChart>
            </ResponsiveContainer>
            <p style={{ color: "#555577", fontSize: 12, marginTop: 14 }}>
              Worst drawdown: -22.0%. The regime filter (QQQ must be above 50/200 SMA golden cross) kept the system out of the 2022 bear market entirely, sitting in cash while stocks crashed.
            </p>
          </div>
        )}

        {tab === "Trades" && (
          <div>
            {/* Win/loss bar */}
            <div style={{ background: "#111126", borderRadius: 12, padding: 22, border: "1px solid #222244", marginBottom: 20 }}>
              <div style={{ fontSize: 14, color: "#7777aa", fontWeight: 600, marginBottom: 12 }}>Win/Loss Distribution</div>
              <div style={{ display: "flex", borderRadius: 8, overflow: "hidden", height: 38 }}>
                <div style={{ width: `${STATS.winRate * 100}%`, background: "#22c55e", display: "flex", alignItems: "center", justifyContent: "center" }}>
                  <span style={{ color: "#fff", fontWeight: 700, fontSize: 13 }}>{STATS.winners}W ({(STATS.winRate * 100).toFixed(1)}%)</span>
                </div>
                <div style={{ flex: 1, background: "#ef4444", display: "flex", alignItems: "center", justifyContent: "center" }}>
                  <span style={{ color: "#fff", fontWeight: 700, fontSize: 13 }}>{STATS.losers}L ({((1 - STATS.winRate) * 100).toFixed(1)}%)</span>
                </div>
              </div>
              <p style={{ color: "#555577", fontSize: 12, marginTop: 10 }}>
                44% win rate with {rrRatio}x reward/risk ratio. Winners average +{STATS.avgWinnerPct}% held {STATS.avgWinnerDays} days, losers average {STATS.avgLoserPct}% cut at {STATS.avgLoserDays} days. Positive expectancy of +{expectancy}% per trade.
              </p>
            </div>

            <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr", gap: 20 }}>
              <div style={{ background: "#111126", borderRadius: 12, border: "1px solid #222244", overflow: "hidden" }}>
                <div style={{ padding: "14px 18px", borderBottom: "1px solid #1a1a30" }}>
                  <span style={{ fontSize: 14, fontWeight: 600, color: "#22c55e" }}>Top 5 Winners</span>
                </div>
                {TOP_WINNERS.map((t, i) => <TradeRow key={i} trade={t} isWinner />)}
              </div>
              <div style={{ background: "#111126", borderRadius: 12, border: "1px solid #222244", overflow: "hidden" }}>
                <div style={{ padding: "14px 18px", borderBottom: "1px solid #1a1a30" }}>
                  <span style={{ fontSize: 14, fontWeight: 600, color: "#ef4444" }}>Top 5 Losers</span>
                </div>
                {TOP_LOSERS.map((t, i) => <TradeRow key={i} trade={t} isWinner={false} />)}
              </div>
            </div>
          </div>
        )}

        {tab === "Iterations" && (
          <div style={{ background: "#111126", borderRadius: 12, padding: 22, border: "1px solid #222244" }}>
            <div style={{ fontSize: 16, color: "#e0e0ff", fontWeight: 600, marginBottom: 6 }}>Optimization History</div>
            <p style={{ color: "#555577", fontSize: 12, marginBottom: 18 }}>6 iterations tested. v7 selected as the best risk-adjusted version — highest Sharpe, lowest drawdown with acceptable returns.</p>
            <table style={{ width: "100%", borderCollapse: "collapse" }}>
              <thead>
                <tr style={{ borderBottom: "1px solid #222244" }}>
                  {["Version", "Sharpe", "Max DD", "Annual", "Trades", "PF", "Changes"].map(h => (
                    <th key={h} style={{ textAlign: "left", padding: "10px 14px", fontSize: 11, color: "#5555aa", textTransform: "uppercase", letterSpacing: 0.8 }}>{h}</th>
                  ))}
                </tr>
              </thead>
              <tbody>
                {ITERATION_HISTORY.map((r, i) => {
                  const isBest = r.version === "v7*";
                  return (
                    <tr key={i} style={{ borderBottom: "1px solid #1a1a30", background: isBest ? "#22c55e08" : "transparent" }}>
                      <td style={{ padding: "10px 14px", fontWeight: isBest ? 700 : 400, color: isBest ? "#22c55e" : "#d0d0ee", fontFamily: "monospace", fontSize: 13 }}>{r.version}</td>
                      <td style={{ padding: "10px 14px", fontFamily: "monospace", fontSize: 13, color: r.sharpe >= 0.85 ? "#22c55e" : r.sharpe >= 0.75 ? "#f59e0b" : "#ef4444" }}>{r.sharpe.toFixed(2)}</td>
                      <td style={{ padding: "10px 14px", fontFamily: "monospace", fontSize: 13, color: "#ef4444" }}>{r.maxDD}%</td>
                      <td style={{ padding: "10px 14px", fontFamily: "monospace", fontSize: 13, color: "#3b82f6" }}>{r.annual}%</td>
                      <td style={{ padding: "10px 14px", fontFamily: "monospace", fontSize: 13, color: "#8888aa" }}>{r.trades}</td>
                      <td style={{ padding: "10px 14px", fontFamily: "monospace", fontSize: 13, color: "#06b6d4" }}>{r.pf.toFixed(2)}</td>
                      <td style={{ padding: "10px 14px", fontSize: 12, color: "#666688" }}>{r.note}</td>
                    </tr>
                  );
                })}
              </tbody>
            </table>
          </div>
        )}
      </div>

      {/* Footer */}
      <div style={{ padding: "16px 36px", borderTop: "1px solid #222244", display: "flex", justifyContent: "space-between", fontSize: 11, color: "#333355", marginTop: 20 }}>
        <span>MACD(12,26,9) + 200 SMA + QQQ Regime Filter | ATR 2.5x Stop | 1.2% risk/trade | Max 8 positions</span>
        <span>Daily scan: 5 PM weekdays | Weekly review: Saturday 10 AM</span>
      </div>
    </div>
  );
}
