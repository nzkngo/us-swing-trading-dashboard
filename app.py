import streamlit as st
import pandas as pd
import numpy as np
import yfinance as yf

st.set_page_config(page_title="US Swing Signals", page_icon="📈", layout="wide")
st.title("📈 US Swing Trading Signals")
st.caption("Educational research dashboard • Daily historical prices • Not investment advice")

DEFAULT = "AAPL,MSFT,NVDA,AMZN,META,GOOGL,TSLA"
tickers_text = st.text_input("US stock tickers (comma separated)", DEFAULT)
tickers = list(dict.fromkeys(t.strip().upper() for t in tickers_text.split(",") if t.strip()))[:20]
capital = st.number_input("Illustrative capital (USD)", min_value=100.0, value=10000.0, step=1000.0)
risk_pct = st.select_slider("Risk budget per trade (%)", options=[0.5, 1.0, 1.5, 2.0], value=1.0)

@st.cache_data(ttl=3600, show_spinner=False)
def prices(symbol):
    return yf.Ticker(symbol).history(period="3y", interval="1d", auto_adjust=True)

def indicators(df):
    d = df.copy()
    c = d["Close"]
    d["EMA20"] = c.ewm(span=20, adjust=False).mean()
    d["SMA50"] = c.rolling(50).mean()
    d["SMA200"] = c.rolling(200).mean()
    delta = c.diff()
    gain = delta.clip(lower=0).ewm(alpha=1/14, adjust=False).mean()
    loss = (-delta.clip(upper=0)).ewm(alpha=1/14, adjust=False).mean()
    rs = gain / loss.replace(0, np.nan)
    d["RSI14"] = (100 - 100/(1 + rs)).fillna(100)
    d.loc[(gain == 0) & (loss == 0), "RSI14"] = 50
    prev = c.shift()
    tr = pd.concat([d["High"] - d["Low"], (d["High"] - prev).abs(), (d["Low"] - prev).abs()], axis=1).max(axis=1)
    d["ATR14"] = tr.ewm(alpha=1/14, adjust=False).mean()
    d["Prior20High"] = d["High"].shift().rolling(20).max()
    return d

if st.button("Scan stocks", type="primary"):
    with st.spinner("Loading daily stock prices..."):
        try:
            spy = indicators(prices("SPY"))
            if len(spy) < 220:
                st.error("SPY data unavailable. Please try again later.")
                st.stop()
            spy_date = spy.index[-1].date()
            market_ok = bool(spy["Close"].iloc[-1] > spy["SMA200"].iloc[-1])
            st.info(f"SPY market filter: {'POSITIVE' if market_ok else 'NEGATIVE'} (latest SPY session: {spy_date})")
        except Exception as exc:
            st.error(f"Market data could not be loaded: {exc}")
            st.stop()
        results = []
        for ticker in tickers:
            try:
                d = indicators(prices(ticker))
                if len(d) < 220:
                    st.warning(f"{ticker}: insufficient historical data")
                    continue
                x = d.iloc[-1]
                buy = bool(market_ok and x["Close"] > x["SMA50"] and x["Close"] > x["SMA200"] and x["SMA50"] > x["SMA200"] and 50 <= x["RSI14"] <= 70 and x["Close"] > x["Prior20High"])
                warning = bool(x["Close"] < x["EMA20"])
                signal = "BUY CANDIDATE" if buy else ("EXIT WARNING (if held)" if warning else "NO NEW ENTRY")
                stop = float(x["Close"] - 2*x["ATR14"]) if buy else np.nan
                per_share_risk = float(x["Close"] - stop) if buy else 0
                shares = min(int(capital * risk_pct / 100 / per_share_risk), int(capital * 0.20 / x["Close"])) if buy and per_share_risk > 0 and stop > 0 else 0
                results.append({"Ticker": ticker, "Data date": str(d.index[-1].date()), "Close ($)": round(float(x["Close"]), 2), "RSI14": round(float(x["RSI14"]), 1), "ATR14 ($)": round(float(x["ATR14"]), 2), "Signal": signal, "Indicative stop ($)": round(stop, 2) if buy else None, "Illustrative shares": shares})
            except Exception as exc:
                st.warning(f"{ticker}: unable to calculate ({exc})")
        if results:
            st.dataframe(pd.DataFrame(results), hide_index=True, use_container_width=True)
            st.caption("Signals are calculated from each symbol's latest available daily bar. Bars may have different dates. Indicative stops use closing prices, not actual next-day fill prices. No trades are placed.")
        else:
            st.warning("No results. Try again later or change tickers.")

st.divider()
st.subheader("Strategy rules")
st.write("**BUY candidate:** SPY above SMA200; stock above SMA50 and SMA200; SMA50 above SMA200; RSI14 from 50 to 70; close above the prior 20-day high.")
st.write("**Exit warning:** stock closes below EMA20. An actual trading system also needs entry-based stops, a 20-session holding limit and position tracking.")
st.warning("Prototype only. Not backtested or validated. Free market data may be delayed, missing or revised. Stop orders may fill below the intended price during gaps. Paper trade before risking money.")
