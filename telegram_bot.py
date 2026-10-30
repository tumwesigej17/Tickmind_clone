import os
import threading
import asyncio
from flask import Flask
import pandas as pd
from curl_cffi import requests as crequests
from telegram import Update
from telegram.ext import Application, CommandHandler, ContextTypes

TOKEN = os.environ.get("BOT_TOKEN") or os.environ.get("TELEGRAM_BOT_TOKEN")

flask_app = Flask(__name__)
@flask_app.route('/')
def home(): return "Tiker AI - DIRECT API LIVE ✅"
def run_flask(): flask_app.run(host='0.0.0.0', port=int(os.environ.get("PORT", 10000)))
threading.Thread(target=run_flask, daemon=True).start()

# ========== DIRECT YAHOO CHART API - WORKS ON RENDER ==========
def fetch_direct(ticker, period="1y"):
    """Bypass yfinance, call Yahoo directly - never blocked"""
    try:
        # Map period to range
        range_map = {"1y":"1y","6mo":"6mo","5d":"5d","1mo":"1mo"}
        y_range = range_map.get(period, "1y")
        
        url = f"https://query1.finance.yahoo.com/v8/finance/chart/{ticker}?range={y_range}&interval=1d&includePrePost=false&events=div%7Csplit"
        
        for imp in ["chrome120", "safari17_0", "chrome110"]:
            try:
                sess = crequests.Session(impersonate=imp)
                resp = sess.get(url, timeout=15)
                if resp.status_code != 200:
                    continue
                data = resp.json()
                if "chart" not in data or not data["chart"]["result"]:
                    continue
                
                result = data["chart"]["result"][0]
                timestamps = result["timestamp"]
                quote = result["indicators"]["quote"][0]
                
                df = pd.DataFrame({
                    'Close': quote['close'],
                    'High': quote['high'],
                    'Low': quote['low'],
                    'Open': quote['open'],
                    'Volume': quote['volume']
                })
                df.index = pd.to_datetime(timestamps, unit='s')
                df = df.dropna()
                if not df.empty:
                    print(f"Direct API success {imp} for {ticker}: {len(df)} rows")
                    return df
            except Exception as e:
                print(f"Direct {imp} failed {ticker}: {e}")
                continue
        return pd.DataFrame()
    except Exception as e:
        print(f"fetch_direct error {e}")
        return pd.DataFrame()

def get_data(ticker):
    # Fix common typo NVDIA -> NVDA
    if ticker.upper() == "NVDIA":
        ticker = "NVDA"
    
    df = fetch_direct(ticker, "1y")
    
    if df.empty:
        df = fetch_direct(ticker, "6mo")
    
    try:
        if df.empty:
            return f"❌ Yahoo still blocking {ticker}. Try in 2 mins: /strong NVDA or /strong BTC-USD\nRender IPs are rate-limited, retry works.", False

        price = float(df['Close'].iloc[-1])
        prev = float(df['Close'].iloc[-2])
        change = (price - prev) / prev * 100 if prev != 0 else 0

        df['SMA20'] = df['Close'].rolling(20).mean()
        df['SMA50'] = df['Close'].rolling(50).mean()
        sma20 = float(df['SMA20'].iloc[-1])
        sma50 = float(df['SMA50'].iloc[-1])

        delta = df['Close'].diff()
        gain = delta.where(delta>0,0).rolling(14).mean()
        loss = -delta.where(delta<0,0).rolling(14).mean()
        rsi = 100 - (100/(1+gain/loss))
        rsi_val = float(rsi.iloc[-1]) if not pd.isna(rsi.iloc[-1]) else 50.0
        atr = float((df['High']-df['Low']).rolling(14).mean().iloc[-1])

        if price > sma20 > sma50 and rsi_val < 68 and change > 1:
            signal = "🟢🟢 STRONG BUY"; is_strong=True; sl=price-atr*1.5; tp1=price+atr*1.5; tp2=price+atr*3.0
        elif rsi_val < 30:
            signal = "🔵🔵 STRONG BUY - OVERSOLD"; is_strong=True; sl=price-atr; tp1=price+atr*2; tp2=price+atr*3.5
        elif price < sma20 and change < -1:
            signal = "🔴🔴 STRONG SELL"; is_strong=True; sl=price+atr*1.5; tp1=price-atr*1.5; tp2=price-atr*3
        else:
            signal = f"⚪ WAIT - RSI {rsi_val:.1f}"; is_strong=False; sl=price-atr*1.5; tp1=price+atr*1.5; tp2=price+atr*2.5

        rr1 = abs(tp1-price)/abs(price-sl) if price!=sl else 0
        rr2 = abs(tp2-price)/abs(price-sl) if price!=sl else 0

        msg = f"🚨 *{ticker.upper()} - SWING SIGNAL* 🚨\n\n💰 ${price:.2f} ({change:+.2f}%) ATR ${atr:.2f} RSI {rsi_val:.1f}\nSMA20 ${sma20:.2f} SMA50 ${sma50:.2f}\n\n🚀 {signal}\n🛑 SL: ${sl:.2f}\n🎯 TP1: ${tp1:.2f} R:R 1:{rr1:.1f}\n🎯 TP2: ${tp2:.2f} R:R 1:{rr2:.1f}"
        return msg, is_strong
    except Exception as e:
        return f"❌ Error {ticker}: {str(e)[:120]}", False

async def strong_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not context.args:
        await update.message.reply_text("Use: /strong GC=F or /strong NVDA")
        return
    t = context.args[0].upper()
    if t == "NVDIA": t = "NVDA"
    await update.message.reply_text(f"⏳ Analyzing {t} via Direct API...")
    msg, strong = get_data(t)
    await update.message.reply_text(msg, parse_mode='Markdown')

async def scan_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("🔎 Scanning...")
    for t in ["NVDA","AAPL","BTC-USD","GC=F"]:
        msg, strong = get_data(t)
        if strong:
            await update.message.reply_text(msg, parse_mode='Markdown')

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("🚀 *OLD VERSION LIVE - DIRECT API!*\n/strong NVDA\n/strong GC=F\n/strong BTC-USD\n/scan", parse_mode='Markdown')

def main():
    if not TOKEN: print("No token"); return
    try: asyncio.set_event_loop(asyncio.new_event_loop())
    except: pass
    app = Application.builder().token(TOKEN).build()
    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("help", start))
    app.add_handler(CommandHandler("strong", strong_cmd))
    app.add_handler(CommandHandler("stock", strong_cmd))
    app.add_handler(CommandHandler("crypto", strong_cmd))
    app.add_handler(CommandHandler("analyze", strong_cmd))
    app.add_handler(CommandHandler("scan", scan_cmd))
    print("Bot starting...")
    app.run_polling(drop_pending_updates=True)

if __name__ == "__main__":
    main()
