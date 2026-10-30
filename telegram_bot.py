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
def home(): return "Tiker AI - SCALP + SWING DIRECT API LIVE ✅"
def run_flask(): flask_app.run(host='0.0.0.0', port=int(os.environ.get("PORT", 10000)))
threading.Thread(target=run_flask, daemon=True).start()

# ========== DIRECT YAHOO API - NO YFINANCE ==========
def fetch_direct(ticker, y_range="1y", interval="1d"):
    url = f"https://query1.finance.yahoo.com/v8/finance/chart/{ticker}?range={y_range}&interval={interval}&includePrePost=false"
    for imp in ["chrome120", "safari17_0", "chrome110"]:
        try:
            sess = crequests.Session(impersonate=imp)
            resp = sess.get(url, timeout=15)
            if resp.status_code != 200: continue
            data = resp.json()
            if "chart" not in data or not data["chart"]["result"]: continue
            result = data["chart"]["result"][0]
            ts = result["timestamp"]
            quote = result["indicators"]["quote"][0]
            df = pd.DataFrame({
                'Close': quote['close'],
                'High': quote['high'],
                'Low': quote['low'],
                'Open': quote['open'],
                'Volume': quote['volume']
            })
            df.index = pd.to_datetime(ts, unit='s')
            df = df.dropna()
            if len(df) > 20:
                print(f"Direct {imp} {interval} {ticker}: {len(df)} rows")
                return df
        except Exception as e:
            print(f"Direct {imp} fail {ticker}: {e}")
            continue
    return pd.DataFrame()

# ========== SWING LOGIC ==========
def get_swing(ticker):
    if ticker.upper() == "NVDIA": ticker = "NVDA"
    df = fetch_direct(ticker, "1y", "1d")
    if df.empty: df = fetch_direct(ticker, "6mo", "1d")
    if df.empty:
        return f"❌ Swing: No data for {ticker}. Try /strong NVDA", False
    
    price = float(df['Close'].iloc[-1])
    prev = float(df['Close'].iloc[-2])
    change = (price-prev)/prev*100
    df['SMA20'] = df['Close'].rolling(20).mean()
    df['SMA50'] = df['Close'].rolling(50).mean()
    sma20 = float(df['SMA20'].iloc[-1])
    sma50 = float(df['SMA50'].iloc[-1])
    delta = df['Close'].diff()
    gain = delta.where(delta>0,0).rolling(14).mean()
    loss = -delta.where(delta<0,0).rolling(14).mean()
    rsi = 100 - (100/(1+gain/loss))
    rsi_val = float(rsi.iloc[-1]) if not pd.isna(rsi.iloc[-1]) else 50
    atr = float((df['High']-df['Low']).rolling(14).mean().iloc[-1])

    if price > sma20 > sma50 and rsi_val < 68 and change > 1:
        sig="🟢🟢 STRONG BUY"; strong=True; sl=price-atr*1.5; tp1=price+atr*1.5; tp2=price+atr*3.0
    elif rsi_val < 30:
        sig="🔵🔵 STRONG BUY - OVERSOLD"; strong=True; sl=price-atr; tp1=price+atr*2; tp2=price+atr*3.5
    elif price < sma20 and change < -1:
        sig="🔴🔴 STRONG SELL"; strong=True; sl=price+atr*1.5; tp1=price-atr*1.5; tp2=price-atr*3
    else:
        sig=f"⚪ WAIT - RSI {rsi_val:.1f}"; strong=False; sl=price-atr*1.5; tp1=price+atr*1.5; tp2=price+atr*2.5

    rr1 = abs(tp1-price)/abs(price-sl) if price!=sl else 0
    msg = f"🚨 *{ticker.upper()} - SWING* 🚨\n\n💰 ${price:.2f} ({change:+.2f}%) ATR ${atr:.2f} RSI {rsi_val:.1f}\nSMA20 ${sma20:.2f} SMA50 ${sma50:.2f}\n\n🚀 {sig}\n🛑 SL: ${sl:.2f}\n🎯 TP1: ${tp1:.2f} 1:{rr1:.1f}\n🎯 TP2: ${tp2:.2f}"
    return msg, strong

# ========== SCALP LOGIC - 5 MIN ==========
def get_scalp(ticker):
    if ticker.upper() == "NVDIA": ticker = "NVDA"
    # 5d of 5m candles = 390+ rows
    df = fetch_direct(ticker, "5d", "5m")
    if df.empty: df = fetch_direct(ticker, "1d", "5m")
    if df.empty:
        return f"❌ Scalp: No 5m data for {ticker}. Try /scalp NVDA", False
    
    price = float(df['Close'].iloc[-1])
    df['EMA9'] = df['Close'].ewm(span=9).mean()
    df['EMA21'] = df['Close'].ewm(span=21).mean()
    df['EMA50'] = df['Close'].ewm(span=50).mean()
    ema9 = float(df['EMA9'].iloc[-1])
    ema21 = float(df['EMA21'].iloc[-1])
    ema50 = float(df['EMA50'].iloc[-1])

    delta = df['Close'].diff()
    gain = delta.where(delta>0,0).rolling(14).mean()
    loss = -delta.where(delta<0,0).rolling(14).mean()
    rsi = 100 - (100/(1+gain/loss))
    rsi_val = float(rsi.iloc[-1]) if not pd.isna(rsi.iloc[-1]) else 50
    
    high_low = df['High'] - df['Low']
    atr = float(high_low.rolling(14).mean().iloc[-1])
    change = float((price - df['Close'].iloc[-2])/df['Close'].iloc[-2]*100)

    # Scalp signals - fast EMA cross
    if ema9 > ema21 > ema50 and rsi_val > 45 and rsi_val < 70 and price > ema9:
        sig="🟢 SCALP BUY - EMA BULL"; strong=True; sl=price-atr*1.2; tp1=price+atr*1.0; tp2=price+atr*2.0
    elif ema9 < ema21 < ema50 and rsi_val < 55 and price < ema9:
        sig="🔴 SCALP SELL - EMA BEAR"; strong=True; sl=price+atr*1.2; tp1=price-atr*1.0; tp2=price-atr*2.0
    elif rsi_val < 28:
        sig="🔵 SCALP BUY - OVERSOLD 5M"; strong=True; sl=price-atr; tp1=price+atr*1.5; tp2=price+atr*2.5
    elif rsi_val > 72:
        sig="🟠 SCALP SELL - OVERBOUGHT 5M"; strong=True; sl=price+atr; tp1=price-atr*1.5; tp2=price-atr*2.5
    else:
        sig=f"⚪ SCALP WAIT - RSI {rsi_val:.1f}"; strong=False; sl=price-atr; tp1=price+atr; tp2=price+atr*2

    rr = abs(tp1-price)/abs(price-sl) if price!=sl else 0
    msg = f"⚡ *{ticker.upper()} - SCALP 5M* ⚡\n\n💰 ${price:.2f} ({change:+.2f}%) RSI {rsi_val:.1f}\nEMA9 ${ema9:.2f} EMA21 ${ema21:.2f} EMA50 ${ema50:.2f}\nATR ${atr:.2f}\n\n🚀 {sig}\n🛑 SL: ${sl:.2f}\n🎯 TP1: ${tp1:.2f} 1:{rr:.1f}\n🎯 TP2: ${tp2:.2f}\n\n⏱️ Hold 5-60 min"
    return msg, strong

# ========== COMMANDS ==========
async def strong_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not context.args:
        await update.message.reply_text("Use: /strong GC=F or /strong NVDA"); return
    t = context.args[0].upper()
    await update.message.reply_text(f"⏳ Swing Analyzing {t}...")
    msg, _ = get_swing(t)
    await update.message.reply_text(msg, parse_mode='Markdown')

async def scalp_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not context.args:
        await update.message.reply_text("Use: /scalp GC=F or /scalp NVDA"); return
    t = context.args[0].upper()
    await update.message.reply_text(f"⚡ Scalp Analyzing {t} (5m)...")
    msg, _ = get_scalp(t)
    await update.message.reply_text(msg, parse_mode='Markdown')

async def scan_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("🔎 Scanning SWING...")
    for t in ["NVDA","AAPL","BTC-USD","GC=F"]:
        msg, strong = get_swing(t)
        if strong: await update.message.reply_text(msg, parse_mode='Markdown')
    await update.message.reply_text("🔎 Scanning SCALP 5M...")
    for t in ["NVDA","GC=F","BTC-USD"]:
        msg, strong = get_scalp(t)
        if strong: await update.message.reply_text(msg, parse_mode='Markdown')

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        "🚀 *Tiker AI - SCALP + SWING LIVE!* 🚀\n\n"
        "SWING (1-5 days):\n/strong GC=F\n/strong NVDA\n/strong BTC-USD\n\n"
        "SCALP (5-60 min):\n/scalp GC=F\n/scalp NVDA\n/scalp BTC-USD\n\n"
        "/scan - Scan both\n"
        "DIRECT API - NO BLOCK ✅",
        parse_mode='Markdown'
    )

def main():
    if not TOKEN: print("No BOT_TOKEN"); return
    try: asyncio.set_event_loop(asyncio.new_event_loop())
    except: pass
    app = Application.builder().token(TOKEN).build()
    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("help", start))
    app.add_handler(CommandHandler("strong", strong_cmd))
    app.add_handler(CommandHandler("stock", strong_cmd))
    app.add_handler(CommandHandler("crypto", strong_cmd))
    app.add_handler(CommandHandler("analyze", strong_cmd))
    app.add_handler(CommandHandler("scalp", scalp_cmd))
    app.add_handler(CommandHandler("scan", scan_cmd))
    print("Bot SCALP+SWING starting...")
    app.run_polling(drop_pending_updates=True)

if __name__ == "__main__":
    main()
