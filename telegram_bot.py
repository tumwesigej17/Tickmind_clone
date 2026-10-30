
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

# ========== FLASK FOR RENDER ==========
flask_app = Flask(__name__)

@flask_app.route('/')
def home():
    return "Tiker AI - OLD SWING VERSION LIVE ✅"

def run_flask():
    port = int(os.environ.get("PORT", 10000))
    flask_app.run(host='0.0.0.0', port=port)

threading.Thread(target=run_flask, daemon=True).start()

# ========== DATA FETCH WITH ANTI-BLOCK ==========
def get_data(ticker):
    df = pd.DataFrame()
    
    # Try 3 different browsers to bypass Yahoo block on Render
    for imp in ["chrome120", "chrome110", "safari17_0"]:
        try:
            sess = crequests.Session(impersonate=imp)
            stk = yf.Ticker(ticker, session=sess)
            df = stk.history(period="1y", auto_adjust=False)
            if not df.empty:
                print(f"Success with {imp} for {ticker}")
                break
            # Try download if history empty
            df = yf.download(ticker, period="1y", session=sess, progress=False, auto_adjust=False)
            if not df.empty:
                break
        except Exception as e:
            print(f"{imp} failed for {ticker}: {e}")
            continue
    
    # Last fallback without session
    if df.empty:
        try:
            print(f"Trying without session for {ticker}")
            df = yf.download(ticker, period="6mo", progress=False, auto_adjust=False)
        except Exception as e:
            print(f"Fallback failed: {e}")

    try:
        if df.empty:
            return f"❌ Yahoo blocked {ticker} temporarily on Render.\nWait 3 min and try another ticker:\n/strong NVDA or /strong BTC-USD\n\nGC=F is often blocked - try stocks first.", False
        
        if isinstance(df.columns, pd.MultiIndex):
            df.columns = df.columns.get_level_values(0)

        price = float(df['Close'].iloc[-1])
        prev = float(df['Close'].iloc[-2])
        change = (price - prev) / prev * 100
        vol = float(df['Volume'].iloc[-1]) if 'Volume' in df else 0

        df['SMA20'] = df['Close'].rolling(20).mean()
        df['SMA50'] = df['Close'].rolling(50).mean()
        df['SMA200'] = df['Close'].rolling(200).mean()

        sma20 = float(df['SMA20'].iloc[-1])
        sma50 = float(df['SMA50'].iloc[-1])
        sma200 = float(df['SMA200'].iloc[-1]) if not pd.isna(df['SMA200'].iloc[-1]) else sma50

        delta = df['Close'].diff()
        gain = delta.where(delta > 0, 0).rolling(14).mean()
        loss = -delta.where(delta < 0, 0).rolling(14).mean()
        rsi = 100 - (100 / (1 + gain / loss))
        rsi_val = float(rsi.iloc[-1])

        atr = float((df['High'] - df['Low']).rolling(14).mean().iloc[-1])

        # SIGNAL LOGIC - OLD VERSION
        if price > sma20 > sma50 and rsi_val < 68 and change > 1:
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
            f"SMA20: ${sma20:.2f} | SMA50: ${sma50:.2f}\n\n"
            f"🚀 {signal}\n\n"
            f"🛑 SL: ${sl:.2f}\n"
            f"🎯 TP1: ${tp1:.2f} R:R 1:{rr1:.1f}\n"
            f"🎯 TP2: ${tp2:.2f} R:R 1:{rr2:.1f}\n\n"
            f"💡 Swing hold 1-5 days"
        )
        return msg, is_strong

    except Exception as e:
        return f"❌ Error {ticker}: {str(e)[:150]}", False

# ========== TELEGRAM COMMANDS ==========
async def strong_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not context.args:
        await update.message.reply_text("Use: /strong GC=F  or  /strong AAPL")
        return
    t = context.args[0].upper()
    await update.message.reply_text(f"⏳ Analyzing {t}...")
    msg, strong = get_data(t)
    await update.message.reply_text(msg, parse_mode='Markdown')

async def scan_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    watchlist = ["AAPL", "NVDA", "BTC-USD", "MSFT", "GC=F", "TSLA"]
    await update.message.reply_text(f"🔎 Scanning {len(watchlist)} tickers...")
    found = 0
    for t in watchlist:
        msg, strong = get_data(t)
        if strong:
            found += 1
            await update.message.reply_text(msg, parse_mode='Markdown')
    if found == 0:
        await update.message.reply_text("⚪ No strong signals right now. Try /strong NVDA")

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        "🚀 *Tiker AI - OLD SWING MODE LIVE!* 🚀\n\n"
        "/strong GC=F - Gold\n"
        "/strong AAPL - Stocks\n"
        "/strong BTC-USD - Crypto\n"
        "/scan - Scan watchlist\n\n"
        "If GC=F says blocked, try NVDA or BTC-USD - Render IP rotates every few mins.",
        parse_mode='Markdown'
    )

def main():
    if not TOKEN:
        print("No BOT_TOKEN set!")
        return
    try:
        asyncio.set_event_loop(asyncio.new_event_loop())
    except:
        pass

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
