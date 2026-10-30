import os
import threading
import asyncio
from flask import Flask
import yfinance as yf
import pandas as pd
from curl_cffi import requests as crequests
from telegram import Update
from telegram.ext import Application, CommandHandler, ContextTypes

TOKEN = os.environ.get("BOT_TOKEN") or os.environ.get("TELEGRAM_BOT_TOKEN")

# Flask for Render
flask_app = Flask(__name__)
@flask_app.route('/')
def home():
    return "Tiker AI SWING LIVE - OLD VERSION ✅"
def run_flask():
    flask_app.run(host='0.0.0.0', port=int(os.environ.get("PORT", 10000)))
threading.Thread(target=run_flask, daemon=True).start()

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
        df['SMA20'] = df['Close'].rolling(20).mean()
        df['SMA50'] = df['Close'].rolling(50).mean()
        sma20 = float(df['SMA20'].iloc[-1])
        sma50 = float(df['SMA50'].iloc[-1])
        delta = df['Close'].diff()
        gain = delta.where(delta>0,0).rolling(14).mean()
        loss = -delta.where(delta<0,0).rolling(14).mean()
        rsi = 100 - (100/(1+gain/loss))
        rsi_val = float(rsi.iloc[-1])
        atr = float((df['High']-df['Low']).rolling(14).mean().iloc[-1])

        if price > sma20 > sma50 and rsi_val < 68 and change > 1:
            sig = "🟢🟢 STRONG BUY"; strong=True; sl=price-atr*1.5; tp1=price+atr*1.5; tp2=price+atr*3.0
        elif rsi_val < 30:
            sig = "🔵🔵 STRONG BUY - OVERSOLD"; strong=True; sl=price-atr; tp1=price+atr*2; tp2=price+atr*3.5
        elif price < sma20 and change < -1:
            sig = "🔴🔴 STRONG SELL"; strong=True; sl=price+atr*1.5; tp1=price-atr*1.5; tp2=price-atr*3
        else:
            sig = f"⚪ WAIT - RSI {rsi_val:.1f}"; strong=False; sl=price-atr*1.5; tp1=price+atr*1.5; tp2=price+atr*2.5

        rr1 = abs(tp1-price)/abs(price-sl) if price!=sl else 0
        rr2 = abs(tp2-price)/abs(price-sl) if price!=sl else 0
        msg = f"🚨 *{ticker.upper()} - SWING SIGNAL* 🚨\n\n💰 ${price:.2f} ({change:+.2f}%) ATR ${atr:.2f} RSI {rsi_val:.1f}\nSMA20 ${sma20:.2f} SMA50 ${sma50:.2f}\n\n🚀 {sig}\n🛑 SL: ${sl:.2f}\n🎯 TP1: ${tp1:.2f} R:R 1:{rr1:.1f}\n🎯 TP2: ${tp2:.2f} R:R 1:{rr2:.1f}"
        return msg, strong
    except Exception as e:
        return f"❌ Error {ticker}: {str(e)[:100]}", False

async def strong_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not context.args:
        await update.message.reply_text("Use: /strong GC=F"); return
    t=context.args[0].upper()
    await update.message.reply_text(f"⏳ Analyzing {t}...")
    msg, strong = get_data(t)
    await update.message.reply_text(msg, parse_mode='Markdown')

async def scan_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("🔎 Scanning...")
    for t in ["AAPL","GC=F","BTC-USD","NVDA"]:
        msg, strong = get_data(t)
        if strong:
            await update.message.reply_text(msg, parse_mode='Markdown')

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("🚀 LIVE OLD VERSION!\n/strong GC=F\n/scan", parse_mode='Markdown')

def main():
    if not TOKEN:
        print("No BOT_TOKEN"); return
    # Fix event loop error on Render
    try:
        asyncio.set_event_loop(asyncio.new_event_loop())
    except: pass
    app = Application.builder().token(TOKEN).build()
    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("help", start))
    app.add_handler(CommandHandler("strong", strong_cmd))
    app.add_handler(CommandHandler("stock", strong_cmd))
    app.add_handler(CommandHandler("crypto", strong_cmd))
    app.add_handler(CommandHandler("analyze", strong_cmd))
    app.add_handler(CommandHandler("scan", scan_cmd))
    print("Bot starting polling...")
    app.run_polling(drop_pending_updates=True, allowed_updates=Update.ALL_TYPES)

if __name__ == "__main__":
    main()
