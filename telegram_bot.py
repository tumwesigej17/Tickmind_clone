import os, threading
from flask import Flask
import yfinance as yf
import pandas as pd
from curl_cffi import requests as crequests
from telegram import Update
from telegram.ext import ApplicationBuilder, CommandHandler, ContextTypes

TOKEN = os.environ.get("BOT_TOKEN") or os.environ.get("TELEGRAM_BOT_TOKEN")

flask_app = Flask(__name__)
@flask_app.route('/')
def home(): 
    return "Tiker AI SWING+SCALP LIVE ✅"

def run_web():
    port = int(os.environ.get("PORT", 10000))
    flask_app.run(host='0.0.0.0', port=port)

threading.Thread(target=run_web, daemon=True).start()

session = crequests.Session(impersonate="chrome110")

def get_scalp_data(ticker):
    try:
        stk = yf.Ticker(ticker, session=session)
        df = stk.history(period="5d", interval="15m", auto_adjust=False)
        if df.empty:
            return None, "No 15m data for " + ticker, False
        if isinstance(df.columns, pd.MultiIndex):
            df.columns = df.columns.get_level_values(0)
        price = float(df['Close'].iloc[-1])
        prev = float(df['Close'].iloc[-2])
        change = (price - prev) / prev * 100
        df['EMA9'] = df['Close'].ewm(span=9).mean()
        df['EMA21'] = df['Close'].ewm(span=21).mean()
        ema9 = float(df['EMA9'].iloc[-1])
        ema21 = float(df['EMA21'].iloc[-1])
        delta = df['Close'].diff()
        gain = delta.where(delta > 0, 0).rolling(14).mean()
        loss = -delta.where(delta < 0, 0).rolling(14).mean()
        rs = gain / loss
        rsi = 100 - (100 / (1 + rs))
        rsi_val = float(rsi.iloc[-1])
        hl = df['High'] - df['Low']
        hc = (df['High'] - df['Close'].shift()).abs()
        lc = (df['Low'] - df['Close'].shift()).abs()
        tr = pd.concat([hl, hc, lc], axis=1).max(axis=1)
        atr = float(tr.rolling(14).mean().iloc[-1])
        if price > ema9 > ema21 and rsi_val > 50:
            sig = "🟢 SCALP BUY"; sl = price - atr*1.0; tp1 = price + atr*1.0; tp2 = price + atr*2.0; is_strong=True
        elif price < ema9 and ema9 < ema21 and rsi_val < 50:
            sig = "🔴 SCALP SELL"; sl = price + atr*1.0; tp1 = price - atr*1.0; tp2 = price - atr*2.0; is_strong=True
        elif rsi_val < 25:
            sig = "🔵 SCALP BUY - Oversold"; sl = price - atr*0.8; tp1 = price + atr*1.2; tp2 = price + atr*2.5; is_strong=True
        elif rsi_val > 75:
            sig = "🟠 SCALP SELL - Overbought"; sl = price + atr*0.8; tp1 = price - atr*1.2; tp2 = price - atr*2.5; is_strong=True
        else:
            sig = f"⚪ NO SCALP - RSI {rsi_val:.1f}"; sl = price - atr; tp1 = price + atr; tp2 = price + atr*2; is_strong=False
        msg = f"⚡ *{ticker.upper()} - SCALP (15min)* ⚡\n\n💰 Price: ${price:.2f} ({change:+.2f}%) | ATR15m: ${atr:.2f}\nEMA9: ${ema9:.2f} EMA21: ${ema21:.2f}\nRSI: {rsi_val:.1f}\n\n🚀 {sig}\n\n🛑 SL: ${sl:.2f}\n🎯 TP1: ${tp1:.2f}\n🎯 TP2: ${tp2:.2f}\n\n⏱️ Hold: 5-60 min"
        return msg, None, is_strong
    except Exception as e:
        return None, str(e), False

def get_data(ticker):
    try:
        stk = yf.Ticker(ticker, session=session)
        df = stk.history(period="1y", auto_adjust=False)
        if df.empty:
            df = yf.download(ticker, period="1y", session=session, progress=False)
        if df.empty:
            return None, "Ticker not found", False
        if isinstance(df.columns, pd.MultiIndex):
            df.columns = df.columns.get_level_values(0)
        price = float(df['Close'].iloc[-1])
        prev = float(df['Close'].iloc[-2])
        change = (price - prev) / prev * 100
        vol = float(df['Volume'].iloc[-1])
        avg_vol = float(df['Volume'].rolling(20).mean().iloc[-1])
        df['SMA20'] = df['Close'].rolling(20).mean()
        df['SMA50'] = df['Close'].rolling(50).mean()
        df['SMA200'] = df['Close'].rolling(200).mean()
        df['EMA12'] = df['Close'].ewm(span=12).mean()
        df['EMA26'] = df['Close'].ewm(span=26).mean()
        sma20 = float(df['SMA20'].iloc[-1])
        sma50 = float(df['SMA50'].iloc[-1])
        delta = df['Close'].diff()
        gain = delta.where(delta > 0, 0).rolling(14).mean()
        loss = -delta.where(delta < 0, 0).rolling(14).mean()
        rs = gain / loss
        rsi = 100 - (100 / (1 + rs))
        rsi_val = float(rsi.iloc[-1])
        df['MACD'] = df['EMA12'] - df['EMA26']
        df['MACD_Sig'] = df['MACD'].ewm(span=9).mean()
        macd = float(df['MACD'].iloc[-1])
        macd_sig = float(df['MACD_Sig'].iloc[-1])
        hl = df['High'] - df['Low']
        hc = (df['High'] - df['Close'].shift()).abs()
        lc = (df['Low'] - df['Close'].shift()).abs()
        tr = pd.concat([hl, hc, lc], axis=1).max(axis=1)
        atr = float(tr.rolling(14).mean().iloc[-1])
        if
