# NVDA RSI 1-Minute — Backtest & Paper Trader

Backtest and paper-trade a simple intraday RSI thesis on **NVDA** using **1-minute** bars:
**RSI(14)**, **buy when RSI < 20**, **sell when RSI > 65**, optional **~2% stop-loss**.
Includes clean charts and daily CSV summaries for quick review.

> ⚠️ Educational project. Not financial advice. Markets are risky—test thoroughly and use at your own risk.

---

## ✨ Features

* **Backtest recent sessions** with per-day metrics (P&L, win rate, drawdown).
* **Paper trade intraday** (yfinance feed) with minute bars.
* **Auto charts**: 1-min price and RSI(14) with 20/65 guide lines.
* **Daily CSV outputs**: trades/summaries (even on 0-trade days if configured).
* **Tiny, readable code**—easy to tweak thresholds or add filters.

---

## 🗂 Project Structure

```
.
├─ backtest_nvda_intraday.py      # Backtest last few sessions, per-day results + trades CSV
├─ paper_test_nvda_yf.py          # Intraday paper trader (09:30–16:00 ET), logs decisions
├─ make_nvda_charts.py            # Generates price/RSI charts + 1-row summary CSV
├─ nvda_1m_backtest_trades.csv    # (output) Backtest trade log
├─ nvda_1m_paper_trades.csv       # (output) Paper trading log (if trades occur)
├─ nvda_1m_today_summary.csv      # (output) Today/last session summary (min/max RSI, thresholds hit)
├─ nvda_1m_price_today.png        # (output) Price chart (1-min)
├─ nvda_1m_rsi_today.png          # (output) RSI chart (1-min) with 20/65 lines
└─ README.md
```

---

## ⚙️ Requirements

* **Python** 3.9+ (3.11/3.12 OK)
* Packages: `yfinance pandas numpy pytz python-dateutil matplotlib`

---

## 🚀 Quick Start

```bash
# 1) Create & activate a virtual environment
python -m venv .venv
source .venv/bin/activate

# 2) Install deps
python -m pip install --upgrade pip
pip install yfinance pandas numpy pytz python-dateutil matplotlib
```

### A) Backtest (recent sessions)

```bash
python backtest_nvda_intraday.py
# Outputs table to console + writes nvda_1m_backtest_trades.csv
```

### B) Paper Trade (run during market hours, 09:30–16:00 ET)

```bash
python paper_test_nvda_yf.py
# Prints minute-by-minute status; writes nvda_1m_paper_trades.csv if trades occur
```

### C) Charts + Daily Summary (today or last session)

```bash
python make_nvda_charts.py
open nvda_1m_price_today.png
open nvda_1m_rsi_today.png
open nvda_1m_today_summary.csv
```

> Tip: In the paper trader, enable the “**always write a daily summary**” block so you get a CSV even on zero-trade days.

---

## 🧠 Strategy (default parameters)

* `SYMBOL = "NVDA"`
* `RSI_WINDOW = 14`
* **Entry**: `RSI < 20`
* **Exit/TP**: `RSI > 65`
* **Stop-loss**: ~`2%` (optional)
* Session window: **09:30–16:00** America/New_York

You can change these in the scripts; keeping them in a small config block makes testing variants easy.

---

## 📤 Outputs (what to look at)

* **Backtest table** (console): trades/day, final equity, total_return_%, win_rate_%, max_drawdown_%, date
* **`nvda_1m_backtest_trades.csv`**: all simulated fills (timestamp, side, price, P&L)
* **`nvda_1m_paper_trades.csv`**: intraday paper fills (when any)
* **`nvda_1m_today_summary.csv`**: one row with `min_RSI`, `max_RSI`, and threshold flags
* **`nvda_1m_price_today.png` / `nvda_1m_rsi_today.png`**: shareable charts

---

## 🔄 Structural Flow (high-level)

```mermaid
flowchart TD
  A[Start]
  B{Mode?}
  A --> B

  B -->|Backtest| C[Fetch recent 1m NVDA via yfinance]
  B -->|Paper Trade| D[Fetch latest 1m NVDA via yfinance (loop)]

  %% Backtest branch
  C --> E[Filter 09:30-16:00 ET<br/>Split by session/day]
  E --> F[Compute RSI(14)]
  F --> G{Signals<br/>RSI &lt; 20 => BUY<br/>RSI &gt; 65 => SELL}
  G --> H[Risk mgmt<br/>~2% stop, no overlap]
  H --> I[Log trades & P&amp;L]
  I --> J[Per-day summary<br/>P&amp;L, win rate, drawdown]
  J --> K[Write nvda_1m_backtest_trades.csv]
  K --> L[Done (Backtest)]

  %% Paper-trading branch
  D --> M[Filter 09:30-16:00 ET]
  M --> N[Loop each minute]
  N --> O[Compute RSI(14)]
  O --> P{Signals<br/>RSI &lt; 20 => BUY<br/>RSI &gt; 65 => SELL}
  P --> Q[Risk mgmt<br/>~2% stop, flat overnight]
  Q --> R[Log paper trades]
  R --> S[End of day]
  S --> T{Any trades?}
  T -->|Yes| U[Write nvda_1m_paper_trades.csv]
  T -->|No| V[Write nvda_1m_today_summary.csv]
  U --> W[Generate charts]
  V --> W[Generate charts]
  W --> X[Save PNGs: price & RSI]
  X --> Y[Done (Paper)]
```

---

## 🧪 How we judge “working”

* **Net positive P&L after fees/slippage**
* **Profit factor > 1.2** (avg win > avg loss)
* **Controlled drawdown** (e.g., < 3–5% on the test window)
* **No forced trades** (zero-trade days are fine)

---

## 🛠 Tweaks you can try (optional)

* **Entry threshold**: test `<25` or `<30` for more frequent entries.
* **Trend filter**: only buy if price above 50-EMA or 200-EMA (or EMA slope > 0).
* **Time-of-day guardrails**: avoid first/last N minutes.
* **Stop/exit**: add time stop (e.g., exit after N minutes if flat RSI).

Keep changes surgical; measure each tweak with the same metrics.

---

## 🧰 Troubleshooting

**`ModuleNotFoundError: No module named 'yfinance'`**
Activate your venv and reinstall:

```bash
source .venv/bin/activate
pip install yfinance
```

**Pandas “Series is ambiguous / can’t convert to float”**
Ensure you convert Series to scalar with `.iloc[-1]` (already handled in scripts).

**`KeyError: 'Close'` (MultiIndex columns)**
The scripts include an `extract_close(...)` helper that normalizes yfinance’s column shapes.

**No trades recorded today**
That’s expected on some days with `RSI<20` entry—check `nvda_1m_today_summary.csv` for min/max RSI and threshold flags.

---

## 📅 Roadmap

* Broker **paper/live** hook (Alpaca/IBKR) for execution testing
* Config file + CLI flags for params
* Rolling performance report (weekly summary)
* Simple ML filters (regime detection) without overfitting

---

## 📄 License

Choose a license (e.g., MIT) and add a `LICENSE` file.

---

## 🤝 Contributing

PRs welcome—keep changes small, measurable, and documented in the README.

---

## 🙋 FAQ

**Q: Why `RSI<20` and `RSI>65`?**
A: It’s a strict oversold/mean-reversion entry with a conservative take-profit. It trades selectively; that’s the point.

**Q: Why yfinance?**
A: It’s quick and free for research. For live trading, switch to a broker feed/API.

**Q: Why NVDA only?**
A: Start narrow. You can generalize to a list of tickers once the loop and reporting are solid.

---
