import os
from datetime import datetime
import pandas as pd
import numpy as np
import yfinance as yf
import pytz
import matplotlib.pyplot as plt
import matplotlib.dates as mdates

TZ_NY = pytz.timezone("America/New_York")
SYMBOL = "NVDA"
RSI_WINDOW = 14
BUY_RSI = 20
SELL_RSI = 65

def compute_rsi(series: pd.Series, window: int) -> pd.Series:
    delta = series.diff()
    gain = delta.clip(lower=0)
    loss = -delta.clip(upper=0)
    avg_gain = gain.ewm(alpha=1/window, adjust=False).mean()
    avg_loss = loss.ewm(alpha=1/window, adjust=False).mean().replace(0, np.nan)
    rs = avg_gain / avg_loss
    rsi = 100 - (100 / (1 + rs))
    return rsi.fillna(50)

def extract_close(df: pd.DataFrame, symbol: str) -> pd.Series:
    """Return a 1-D float Series of Close prices regardless of yfinance column shape."""
    if isinstance(df.columns, pd.MultiIndex):
        if ("Close", symbol) in df.columns:
            s = df[("Close", symbol)]
        elif "Close" in df.columns.get_level_values(0):
            s = df.loc[:, "Close"].iloc[:, 0]
        else:
            close_cols = [c for c in df.columns if isinstance(c, tuple) and str(c[0]).lower() == "close"]
            if not close_cols:
                raise KeyError(f"No Close column. Columns: {list(df.columns)}")
            s = df[close_cols[0]]
    else:
        if "Close" in df.columns:
            s = df["Close"]
        else:
            matches = [c for c in df.columns if "close" in str(c).lower()]
            if not matches:
                raise KeyError(f"No Close column. Columns: {list(df.columns)}")
            s = df[matches[0]]
    return pd.to_numeric(s, errors="coerce").dropna().astype(float)

def get_session_1m(symbol: str) -> pd.DataFrame:
    # download a week to be safe, then filter to today's NY session (fallback to last session if after hours)
    df = yf.download(symbol, period="7d", interval="1m", auto_adjust=True, progress=False)
    if df is None or df.empty:
        return pd.DataFrame()
    if df.index.tz is None:
        df.index = df.index.tz_localize("UTC").tz_convert(TZ_NY)
    else:
        df.index = df.index.tz_convert(TZ_NY)
    df = df.between_time("09:30", "16:00")
    df["__day__"] = df.index.date

    today_ny = datetime.now(TZ_NY).date()
    if (df["__day__"] == today_ny).any():
        out = df[df["__day__"] == today_ny].copy()
    else:
        # market closed or weekend — use the most recent trading day
        last_day = sorted(df["__day__"].unique())[-1]
        out = df[df["__day__"] == last_day].copy()

    out.drop(columns="__day__", inplace=True, errors="ignore")
    return out

def main():
    df = get_session_1m(SYMBOL)
    if df.empty:
        print("No data returned. Try on a market day between 9:30–16:00 ET.")
        return

    close = extract_close(df, SYMBOL)
    rsi = compute_rsi(close, RSI_WINDOW)
    session_date = close.index[0].date().isoformat()

    # Price chart
    fig1, ax1 = plt.subplots(figsize=(10, 4.5))
    ax1.plot(close.index, close.values)
    ax1.set_title(f"{SYMBOL} price — {session_date} (1m)")
    ax1.set_ylabel("Price")
    ax1.xaxis.set_major_formatter(mdates.DateFormatter("%H:%M"))
    fig1.tight_layout()
    fig1.savefig("nvda_1m_price_today.png", dpi=150)
    plt.close(fig1)

    # RSI chart with 20/65 guides
    fig2, ax2 = plt.subplots(figsize=(10, 4.5))
    ax2.plot(rsi.index, rsi.values)
    ax2.axhline(BUY_RSI, linestyle="--")
    ax2.axhline(SELL_RSI, linestyle="--")
    ax2.set_ylim(0, 100)
    ax2.set_title(f"RSI({RSI_WINDOW}) — {session_date} (1m)")
    ax2.set_ylabel("RSI")
    ax2.xaxis.set_major_formatter(mdates.DateFormatter("%H:%M"))
    fig2.tight_layout()
    fig2.savefig("nvda_1m_rsi_today.png", dpi=150)
    plt.close(fig2)

    # One-row summary CSV
    summary = pd.DataFrame([{
        "date": session_date,
        "min_RSI": round(float(rsi.min()), 1),
        "max_RSI": round(float(rsi.max()), 1),
        "hit_buy_threshold(<20)": bool((rsi < BUY_RSI).any()),
        "hit_sell_threshold(>65)": bool((rsi > SELL_RSI).any()),
    }])
    summary.to_csv("nvda_1m_today_summary.csv", index=False)

    # Optional overlay of trades if exists
    trades_path = "nvda_1m_paper_trades.csv"
    if os.path.exists(trades_path):
        trades = pd.read_csv(trades_path, parse_dates=["Time"])
        fig3, ax3 = plt.subplots(figsize=(10, 4.5))
        ax3.plot(close.index, close.values)
        buys = trades[trades["Side"] == "BUY"]
        sells = trades[trades["Side"] == "SELL"]
        if not buys.empty:
            ax3.scatter(buys["Time"], buys["Price"], marker="^", s=40)
        if not sells.empty:
            ax3.scatter(sells["Time"], sells["Price"], marker="v", s=40)
        ax3.set_title(f"{SYMBOL} price with trades — {session_date} (1m)")
        ax3.set_ylabel("Price")
        ax3.xaxis.set_major_formatter(mdates.DateFormatter("%H:%M"))
        fig3.tight_layout()
        fig3.savefig("nvda_1m_price_trades_today.png", dpi=150)
        plt.close(fig3)

    print("Saved: nvda_1m_price_today.png, nvda_1m_rsi_today.png, nvda_1m_today_summary.csv")
    if os.path.exists(trades_path):
        print("Saved: nvda_1m_price_trades_today.png (with trade markers)")

if __name__ == "__main__":
    main()
