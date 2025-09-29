# backtest_nvda_intraday.py (NVDA, 1m, RSI 14; Buy<20, Sell>65, 2% SL, 5-min hold)
import pandas as pd
import numpy as np
import yfinance as yf
import pytz

# ---- Params ----
SYMBOL = "NVDA"
RSI_WINDOW = 14
BUY_RSI = 20
SELL_RSI = 65
STOP_LOSS_PCT = 0.02      # 2% stop loss
MIN_HOLD_MINUTES = 5
SLIPPAGE_BPS = 2          # 0.02% per side
FEE_PER_TRADE = 0.00
START_CASH = 10000.0
DAYS_TO_TEST = 5          # last N trading days
# ----------------

TZ_NY = pytz.timezone("America/New_York")

def compute_rsi(series: pd.Series, window: int) -> pd.Series:
    delta = series.diff()
    gain = delta.clip(lower=0)
    loss = -delta.clip(upper=0)
    avg_gain = gain.ewm(alpha=1/window, adjust=False).mean()
    avg_loss = loss.ewm(alpha=1/window, adjust=False).mean().replace(0, np.nan)
    rs = avg_gain / avg_loss
    rsi = 100 - (100 / (1 + rs))
    return rsi.fillna(50)

def fetch_recent_days(symbol: str, days: int) -> pd.DataFrame:
    """
    Robust fetch: always return a DataFrame indexed by time with a single 'Close' column
    and a '__day__' helper column, regardless of whether yfinance used MultiIndex columns.
    """
    df = yf.download(symbol, period="7d", interval="1m", auto_adjust=True, progress=False)
    if df is None or df.empty:
        return pd.DataFrame()

    # Convert timezone to New York and keep regular hours only
    if df.index.tz is None:
        df.index = df.index.tz_localize("UTC").tz_convert(TZ_NY)
    else:
        df.index = df.index.tz_convert(TZ_NY)
    df = df.between_time("09:30", "16:00")

    # Find the Close series no matter how yfinance structured the columns
    close_series = None
    if isinstance(df.columns, pd.MultiIndex):
        # Preferred: ('Close', 'NVDA')
        key = ("Close", symbol)
        if key in df.columns:
            close_series = df[key]
        else:
            # Fallback: any ('Close', something)
            for col in df.columns:
                if isinstance(col, tuple) and str(col[0]).lower() == "close":
                    close_series = df[col]
                    break
    else:
        # Single-index columns
        if "Close" in df.columns:
            close_series = df["Close"]
        else:
            # Fallback: any column containing 'close' (defensive)
            for c in df.columns:
                if "close" in str(c).lower():
                    close_series = df[c]
                    break

    if close_series is None:
        print("Could not find a Close column. Columns were:", list(df.columns))
        return pd.DataFrame()

    # Build a clean output with a single 'Close' column and a day marker
    out = pd.DataFrame({"Close": pd.to_numeric(close_series, errors="coerce")}).dropna()
    out["__day__"] = out.index.date
    keep_days = sorted(out["__day__"].unique())[-days:]
    out = out[out["__day__"].isin(keep_days)]
    return out


def backtest_day(df_day: pd.DataFrame) -> tuple[list, dict]:
    if df_day.empty:
        return [], {}

    # Make sure Close is a numeric Series
    closes = pd.to_numeric(df_day["Close"], errors="coerce").astype(float)
    rsi = compute_rsi(closes, RSI_WINDOW)

    cash: float = float(START_CASH)
    shares: float = 0.0
    entry_price: float | None = None
    entry_time = None

    peak_equity: float = float(START_CASH)
    max_drawdown: float = 0.0
    trades: list[dict] = []

    # iterate with iat to guarantee a scalar float
    for i in range(len(closes)):
        ts = closes.index[i]
        price = float(closes.iat[i])
        cur_rsi = float(rsi.iat[i])

        equity = float(cash + shares * price)
        if equity > peak_equity:
            peak_equity = equity
        if peak_equity > 0:
            dd = (equity - peak_equity) / peak_equity
            if dd < max_drawdown:
                max_drawdown = dd

        if shares == 0.0:
            if cur_rsi < BUY_RSI:
                buy_px = price * (1 + SLIPPAGE_BPS / 1e4)
                if buy_px > 0 and cash > FEE_PER_TRADE:
                    shares = (cash - FEE_PER_TRADE) / buy_px
                    cash = 0.0
                    entry_price = float(buy_px)
                    entry_time = ts
                    trades.append({"Time": ts, "Side": "BUY", "Price": round(buy_px, 4), "RSI": round(cur_rsi, 2)})
        else:
            held_mins = int((ts - entry_time).total_seconds() // 60)
            stop_hit = price <= entry_price * (1 - STOP_LOSS_PCT)
            exit_signal = (cur_rsi > SELL_RSI) and (held_mins >= MIN_HOLD_MINUTES)

            if stop_hit or exit_signal:
                sell_px = price * (1 - SLIPPAGE_BPS / 1e4)
                cash = float(shares * sell_px - FEE_PER_TRADE)
                pnl = (sell_px - entry_price) / entry_price
                trades.append({
                    "Time": ts, "Side": "SELL", "Price": round(sell_px, 4),
                    "RSI": round(cur_rsi, 2), "Reason": "STOP" if stop_hit else "RSI>65",
                    "PnL_%": round(pnl * 100, 3)
                })
                shares = 0.0
                entry_price, entry_time = None, None

    # close any open position at end of day
    if shares > 0.0:
        last_ts = closes.index[-1]
        last_px = float(closes.iat[-1]) * (1 - SLIPPAGE_BPS / 1e4)
        cash = float(shares * last_px - FEE_PER_TRADE)
        pnl = (last_px - entry_price) / entry_price
        trades.append({
            "Time": last_ts, "Side": "SELL", "Price": round(last_px, 4),
            "RSI": round(float(rsi.iat[-1]), 2), "Reason": "EOD", "PnL_%": round(pnl * 100, 3)
        })
        shares = 0.0

    final_equity = float(cash)
    total_return = final_equity / START_CASH - 1.0
    pnl_list = [t["PnL_%"] for t in trades if t["Side"] == "SELL" and "PnL_%" in t]
    win_rate = (np.array(pnl_list) > 0).mean() * 100 if pnl_list else np.nan

    summary = {
        "trades": len(pnl_list),
        "final_equity": round(final_equity, 2),
        "total_return_%": round(total_return * 100, 2),
        "win_rate_%": None if np.isnan(win_rate) else round(float(win_rate), 1),
        "max_drawdown_%": round(abs(max_drawdown) * 100, 2),
    }
    return trades, summary

def run():
    df = fetch_recent_days(SYMBOL, DAYS_TO_TEST)
    if df.empty:
        print("No data returned; try during market week and check internet.")
        return

    df["__day__"] = df.index.date
    daily_rows = []
    all_trades = []
    for day, chunk in df.groupby("__day__"):
        trades, summ = backtest_day(chunk.drop(columns="__day__", errors="ignore"))
        summ["date"] = str(day)
        daily_rows.append(summ)
        for t in trades:
            t["date"] = str(day)
            all_trades.append(t)

    res = pd.DataFrame(daily_rows).sort_values("date")
    print("\n=== NVDA 1m RSI Backtest (last {} sessions) ===".format(len(res)))
    print(res.to_string(index=False))

    if all_trades:
        pd.DataFrame(all_trades).to_csv("nvda_1m_backtest_trades.csv", index=False)
        print("\nSaved trades -> nvda_1m_backtest_trades.csv")

if __name__ == "__main__":
    run()
