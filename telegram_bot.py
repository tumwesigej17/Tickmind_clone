import os
import threading
from flask import Flask
import yfinance as yf
import pandas as pd
from telegram import Update
from telegram.ext import ApplicationBuilder, CommandHandler, ContextTypes

TOKEN = os.environ.get("BOT_TOKEN") or os.environ.get("TELEGRAM_BOT_TOKEN")

flask_app = Flask(__name__)

@flask_app.route('/')
def home():
    return "Tiker AI LIVE ✅"

def run_web():
    port = int(os.environ.get("PORT", 10000))
    flask_app.run(host='0.0.0.0', port=port)

threading.Thread(target=run_web, daemon=True).start()

def get_scalp_data(ticker):
    try:
        df = yf.download(ticker, period="5d", interval="15m", progress=False, auto_adjust=False)
        if df.empty:
            return None, f"No 15m data for {ticker}", False
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
        rsi = 100 - (100 / (1 + gain / loss))
        rsi_val = float(rsi.iloc[-1])
        atr = float((df['High'] - df['Low']).rolling(14).mean().iloc[-1])

        if price > ema9 > ema21 and rsi_val > 50:
            sig = "🟢 SCALP BUY"
            sl = price - atr
            tp1 = price + atr
            tp2 = price + atr * 2
            strong = True
        elif price < ema9 and ema9 < ema21 and rsi_val < 50:
            sig = "🔴 SCALP SELL"
            sl = price + atr
            tp1 = price - atr
            tp2 = price - atr * 2
            strong = True
        else:
            sig = f"⚪ NO SCALP RSI {rsi_val:.1f}"
            sl = price - atr
            tp1 = price + atr
            tp2 = price + atr * 2
            strong = False

        msg = f"⚡ *{ticker.upper()} - SCALP 15m*\n\n💰 ${price:.2f} ({change:+.2f}%)\nEMA9 ${ema9:.2f} EMA21 ${ema21:.2f} RSI {rsi_val:.1f}\n\n🚀 {sig}\n🛑 SL ${sl:.2f}\n🎯 TP1 ${tp1:.2f} TP2 ${tp2:.2f}"
        return msg, None, strong
    except Exception as e:
        return None, str(e), False

def get_data(ticker):
    try:
        df = yf.download(ticker, period="1y", progress=False, auto_adjust=False)
        if df.empty:
            return None, "Ticker not found", False
        if isinstance(df.columns, pd.MultiIndex):
            df.columns = df.columns.get_level_values(0)
        price = float(df['Close'].iloc[-1])
        prev = float(df['Close'].iloc[-2])
        change = (price - prev) / prev * 100
        df['SMA20'] = df['Close'].rolling(20).mean()
        df['SMA50'] = df['Close'].rolling(50).mean()
        sma20 = float(df['SMA20'].iloc[-1])
        sma50 = float(df['SMA50'].iloc[-1])
        delta = df['Close'].diff()
        gain = delta.where(delta > 0, 0).rolling(14).mean()
        loss = -delta.where(delta < 0, 0).rolling(14).mean()
        rsi = 100 - (100 / (1 + gain / loss))
        rsi_val = float(rsi.iloc[-1])
        atr = float((df['High'] - df['Low']).rolling(14).mean().iloc[-1])

        if price > sma20 > sma50 and rsi_val < 68 and change > 1:
            sig = "🟢🟢 STRONG BUY"
            strong = True
            sl = price - atr * 1.5
            tp1 = price + atr * 1.5
            tp2 = price + atr * 3
        elif rsi_val < 30:
            sig = "🔵🔵 OVERSOLD BUY"
            strong = True
            sl = price - atr
            tp1 = price + atr * 2
            tp2 = price + atr * 3.5
        elif price < sma20 and change < -1:
            sig = "🔴🔴 STRONG SELL"
            strong = True
            sl = price + atr * 1.5
            tp1 = price - atr * 1.5
            tp2 = price - atr * 3
        else:
            sig = f"⚪ WAIT RSI {rsi_val:.1f}"
            strong = False
            sl = price - atr * 1.5
            tp1 = price + atr * 1.5
            tp2 = price + atr * 2.5

        msg = f"🚨 *{ticker.upper()} SWING*\n\n💰 ${price:.2f} ({change:+.2f}%) ATR ${atr:.2f}\nSMA20 ${sma20:.2f} SMA50 ${sma50:.2f} RSI {rsi_val:.1f}\n\n🚀 {sig}\n🛑 SL ${sl:.2f}\n🎯 TP1 ${tp1:.2f} TP2 ${tp2:.2f}"
        return msg, None, strong
    except Exception as e:
        return None, str(e), False

async def strong_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not context.args:
        await update.message.reply_text("Use: /strong GC=F")
        return
    t = context.args[0].upper()
    await update.message.reply_text(f"⏳ Analyzing {t}...")
    msg, err, strong = get_data(t)
    if msg:
        await update.message.reply_text(msg, parse_mode='Markdown')
    else:
        await update.message.reply_text(f"❌ {err}")

async def scalp_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not context.args:
        await update.message.reply_text("Use: /scalp GC=F")
        return
    t = context.args[0].upper()
    await update.message.reply_text(f"⚡ SCALP {t}...")
    msg, err, strong = get_scalp_data(t)
    if msg:
        await update.message.reply_text(msg, parse_mode='Markdown')
    else:
        await update.message.reply_text(f"❌ {err}")

async def scan_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("🔎 Scanning...")
    for t in ["AAPL", "GC=F", "BTC-USD", "NVDA"]:
        msg, err, strong = get_data(t)
        if strong and msg:
            await update.message.reply_text(msg, parse_mode='Markdown')

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("🚀 LIVE!\n/strong GC=F\n/scalp GC=F\n/scan", parse_mode='Markdown')

if TOKEN:
    app = ApplicationBuilder().token(TOKEN).build()
    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("help", start))
    app.add_handler(CommandHandler("strong", strong_cmd))
    app.add_handler(CommandHandler("scalp", scalp_cmd))
    app.add_handler(CommandHandler("scan", scan_cmd))
    app.add_handler(CommandHandler("stock", strong_cmd))
    app.add_handler(CommandHandler("crypto", strong_cmd))
    app.add_handler(CommandHandler("analyze", strong_cmd))
    app.run_polling(drop_pending_updates=True)
