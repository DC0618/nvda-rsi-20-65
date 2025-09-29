# paper_test_nvda_yf.py (VS Code live simulation, no broker)
import time
from datetime import datetime
import pandas as pd
import numpy as np
import yfinance as yf
import pytz

SYMBOL = "NVDA"
RSI_WINDOW = 14
BUY_RSI = 20
SELL_RSI = 65
STOP_LOSS_PCT = 0.02
MIN_HOLD_MINUTES = 5
SLIPPAGE_BPS = 2
FEE_PER_TRADE = 0.00
START_CASH = 10000.0

TZ_NY = pytz.timezone("America/New_York")

def compute_rsi(series: pd.Series, window: int) -> pd.Series:
    delta = series.diff()
    gain = delta.clip(lower=0)
    loss = -delta.clip(upper=0)
    avg_gain = gain.ewm(alpha=1/window, adjust=False).mean()
    avg_loss = loss.ewm(alpha=1/window, adjust=False).mean()
    rs = avg_gain / (avg_loss.replace(0, np.nan))
    rsi = 100 - (100 / (1 + rs))
    return rsi.fillna(50)

def get_today_1m(symbol: str) -> pd.DataFrame:
    df = yf.download(symbol, period="1d", interval="1m", auto_adjust=True, progress=False)
    if df is None or df.empty:
        return pd.DataFrame()
    if df.index.tz is None:
        df.index = df.index.tz_localize("UTC").tz_convert(TZ_NY)
    else:
        df.index = df.index.tz_convert(TZ_NY)
    return df.between_time("09:30", "16:00")

def run_loop():
    cash = START_CASH
    shares = 0.0
    entry_price, entry_time = None, None
    trades = []
    last_ts = None

    print("Starting NVDA 1m paper test (Ctrl+C to stop).")
    while True:
        now = datetime.now(TZ_NY)
        if now.hour > 16 or (now.hour == 16 and now.minute >= 1):
            print("Market closed. Exiting.")
            break

        df = get_today_1m(SYMBOL)
        if df.empty:
            time.sleep(5)
            continue

        closes = df["Close"]
        rsi = compute_rsi(closes, RSI_WINDOW)
        ts = closes.index[-1]
        price = float(closes.iloc[-1])
        cur_rsi = float(rsi.iloc[-1])

        if last_ts is not None and ts == last_ts:
            time.sleep(3)  # wait for new bar
            continue
        last_ts = ts

        equity = cash + shares * price
        print(f"[{ts}] Price={price:.2f}  RSI={cur_rsi:.1f}  Equity=${equity:,.2f}")

        if shares == 0:
            if cur_rsi < BUY_RSI:
                buy_px = price * (1 + SLIPPAGE_BPS/1e4)
                shares = (cash - FEE_PER_TRADE) / buy_px
                cash = 0.0
                entry_price, entry_time = buy_px, ts
                trades.append({"Time": ts, "Side": "BUY", "Price": round(buy_px, 4), "RSI": round(cur_rsi, 2)})
                print(f" -> BUY @ {buy_px:.2f}")
        else:
            held = int((ts - entry_time).total_seconds() // 60)
            stop_hit = price <= entry_price * (1 - STOP_LOSS_PCT)
            exit_signal = (cur_rsi > SELL_RSI) and (held >= MIN_HOLD_MINUTES)
            if stop_hit or exit_signal:
                sell_px = price * (1 - SLIPPAGE_BPS/1e4)
                cash = shares * sell_px - FEE_PER_TRADE
                pnl = (sell_px - entry_price) / entry_price
                trades.append({
                    "Time": ts, "Side": "SELL", "Price": round(sell_px, 4),
                    "RSI": round(cur_rsi, 2),
                    "Reason": "STOP" if stop_hit else "RSI>65",
                    "PnL_%": round(pnl*100, 3)
                })
                print(f" -> SELL ({'STOP' if stop_hit else 'RSI>65'}) @ {sell_px:.2f}  PnL={pnl*100:.2f}%")
                shares = 0.0
                entry_price, entry_time = None, None

        time.sleep(5)  # gentle polling

    if shares > 0:
        last_px = float(get_today_1m(SYMBOL)["Close"].iloc[-1]) * (1 - SLIPPAGE_BPS/1e4)
        cash = shares * last_px - FEE_PER_TRADE
        pnl = (last_px - entry_price) / entry_price
        trades.append({"Time": last_ts, "Side": "SELL", "Price": round(last_px, 4),
                       "RSI": round(cur_rsi, 2), "Reason": "EOD", "PnL_%": round(pnl*100, 3)})
        print(f" -> EOD SELL @ {last_px:.2f}  PnL={pnl*100:.2f}%")

    if trades:
        pd.DataFrame(trades).to_csv("nvda_1m_paper_trades.csv", index=False)
        print("Saved trades -> nvda_1m_paper_trades.csv")

if __name__ == "__main__":
    run_loop()
