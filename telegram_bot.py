import os
import threading
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
    return "Tiker AI SWING LIVE ✅"

def run_web():
    port = int(os.environ.get("PORT", 10000))
    flask_app.run(host='0.0.0.0', port=port)

threading.Thread(target=run_web, daemon=True).start()

session = crequests.Session(impersonate="chrome110")

def get_data(ticker):
    try:
        stk = yf.Ticker(ticker, session=session)
        df = stk.history(period="1y", auto_adjust=False)
        if df.empty:
            df = yf.download(ticker, period="1y", session=session, progress=False, auto_adjust=False)
        if df.empty:
            return f"❌ No data for {ticker}", False
        if isinstance(df.columns, pd.MultiIndex):
            df.columns = df.columns.get_level_values(0)

        price = float(df['Close'].iloc[-1])
        prev = float(df['Close'].iloc[-2])
        change = (price - prev) / prev * 100
        vol = float(df['Volume'].iloc[-1])

        df['SMA20'] = df['Close'].rolling(20).mean()
        df['SMA50'] = df['Close'].rolling(50).mean()
        df['SMA200'] = df['Close'].rolling(200).mean()
        df['EMA12'] = df['Close'].ewm(span=12).mean()
        df['EMA26'] = df['Close'].ewm(span=26).mean()

        sma20 = float(df['SMA20'].iloc[-1])
        sma50 = float(df['SMA50'].iloc[-1])
        sma200 = float(df['SMA200'].iloc[-1])

        delta = df['Close'].diff()
        gain = delta.where(delta > 0, 0).rolling(14).mean()
        loss = -delta.where(delta < 0, 0).rolling(14).mean()
        rsi = 100 - (100 / (1 + gain / loss))
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

        # SIGNAL LOGIC
        if price > sma20 > sma50 and rsi_val < 68 and macd > macd_sig and change > 1:
            signal = "🟢🟢 STRONG BUY"
            is_strong = True
            sl = price - atr * 1.5
            tp1 = price + atr * 1.5
            tp2 = price + atr * 3.0
        elif rsi_val < 30:
            signal = "🔵🔵 STRONG BUY - OVERSOLD"
            is_strong = True
            sl = price - atr * 1.0
            tp1 = price + atr * 2.0
            tp2 = price + atr * 3.5
        elif price < sma20 and sma20 < sma50 and change < -1:
            signal = "🔴🔴 STRONG SELL"
            is_strong = True
            sl = price + atr * 1.5
            tp1 = price - atr * 1.5
            tp2 = price - atr * 3.0
        elif rsi_val > 75:
            signal = "🟠🟠 STRONG SELL - OVERBOUGHT"
            is_strong = True
            sl = price + atr * 1.0
            tp1 = price - atr * 2.0
            tp2 = price - atr * 3.5
        else:
            signal = f"⚪ WAIT - RSI {rsi_val:.1f}"
            is_strong = False
            sl = price - atr * 1.5
            tp1 = price + atr * 1.5
            tp2 = price + atr * 2.5

        rr1 = abs(tp1 - price) / abs(price - sl) if price != sl else 0
        rr2 = abs(tp2 - price) / abs(price - sl) if price != sl else 0

        msg = (
            f"🚨 *{ticker.upper()} - SWING SIGNAL* 🚨\n\n"
            f"💰 Price: ${price:.2f} ({change:+.2f}%)\n"
            f"📊 ATR: ${atr:.2f} | RSI: {rsi_val:.1f}\n"
            f"SMA20: ${sma20:.2f} | SMA50: ${sma50:.2f}\n"
            f"MACD: {macd:.3f} vs {macd_sig:.3f}\n\n"
            f"🚀 {signal}\n\n"
            f"🛑 SL: ${sl:.2f}\n"
            f"🎯 TP1: ${tp1:.2f} R:R 1:{rr1:.1f}\n"
            f"🎯 TP2: ${tp2:.2f} R:R 1:{rr2:.1f}\n\n"
            f"💡 Swing hold 1-5 days | Vol: {vol:,.0f}"
        )
        return msg, is_strong

    except Exception as e:
        return f"❌ Error {ticker}: {str(e)[:120]}", False

async def strong_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not context.args:
        await update.message.reply_text("Use: /strong AAPL  or  /strong GC=F")
        return
    t = context.args[0].upper()
    await update.message.reply_text(f"⏳ Analyzing {t}...")
    msg, strong = get_data(t)
    await update.message.reply_text(msg, parse_mode='Markdown')

async def scan_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    watchlist = ["AAPL", "GC=F", "BTC-USD", "NVDA", "TSLA", "MSFT"]
    await update.message.reply_text(f"🔎 Scanning {len(watchlist)} tickers for STRONG signals...")
    found = 0
    for t in watchlist:
        msg, strong = get_data(t)
        if strong:
            found += 1
            await update.message.reply_text(msg, parse_mode='Markdown')
    if found == 0:
        await update.message.reply_text("⚪ No strong signals right now. Try /strong GC=F")

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        "🚀 *Tiker AI - SWING MODE LIVE!*\n\n"
        "/strong GC=F - Gold\n"
        "/strong AAPL - Stocks\n"
        "/strong BTC-USD - Crypto\n"
        "/scan - Scan watchlist\n\n"
        "TP1 = 1:2 | TP2 = 1:3.5",
        parse_mode='Markdown'
    )

if TOKEN:
    app = ApplicationBuilder().token(TOKEN).build()
    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("help", start))
    app.add_handler(CommandHandler("strong", strong_cmd))
    app.add_handler(CommandHandler("stock", strong_cmd))
    app.add_handler(CommandHandler("crypto", strong_cmd))
    app.add_handler(CommandHandler("analyze", strong_cmd))
    app.add_handler(CommandHandler("scan", scan_cmd))
    app.run_polling(drop_pending_updates=True)
