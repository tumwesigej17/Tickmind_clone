import os
import threading
import asyncio
from flask import Flask
import pandas as pd
from curl_cffi import requests as crequests
from telegram import Update
from telegram.ext import Application, CommandHandler, ContextTypes, MessageHandler, filters

TOKEN = os.environ.get("BOT_TOKEN") or os.environ.get("TELEGRAM_BOT_TOKEN")

# CONFIG - YOUR CHANNELS
PRIVATE_CHANNEL_ID = -1003988456999
PUBLIC_CHANNEL_ID = -1004318804875
GC_TO_SPOT_OFFSET = 9.55  # $3923 futures - $3913 spot = 9.55

flask_app = Flask(__name__)
@flask_app.route('/')
def home(): return "Tiker AI - SCALP 5M + SWING + 3 ENTRIES + FORWARD LIVE ✅"
def run_flask(): flask_app.run(host='0.0.0.0', port=int(os.environ.get("PORT", 10000)))
threading.Thread(target=run_flask, daemon=True).start()

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

def get_swing(ticker):
    if ticker.upper() == "NVDIA": ticker = "NVDA"
    orig = ticker.upper()
    df = fetch_direct(ticker, "1y", "1d")
    if df.empty: df = fetch_direct(ticker, "6mo", "1d")
    if df.empty:
        return f"❌ Swing: No data for {ticker}. Try /strong NVDA", False
    
    price_raw = float(df['Close'].iloc[-1])
    price = price_raw - GC_TO_SPOT_OFFSET if orig == "GC=F" else price_raw
    show = "XAUUSD" if orig == "GC=F" else orig
    prev = float(df['Close'].iloc[-2])
    change = (price_raw-prev)/prev*100
    
    df['SMA20'] = df['Close'].rolling(20).mean()
    df['SMA50'] = df['Close'].rolling(50).mean()
    sma20_raw = float(df['SMA20'].iloc[-1])
    sma50_raw = float(df['SMA50'].iloc[-1])
    sma20 = sma20_raw - (GC_TO_SPOT_OFFSET if orig == "GC=F" else 0)
    sma50 = sma50_raw - (GC_TO_SPOT_OFFSET if orig == "GC=F" else 0)
    
    delta = df['Close'].diff()
    gain = delta.where(delta>0,0).rolling(14).mean()
    loss = -delta.where(delta<0,0).rolling(14).mean()
    rsi = 100 - (100/(1+gain/loss))
    rsi_val = float(rsi.iloc[-1]) if not pd.isna(rsi.iloc[-1]) else 50
    atr = float((df['High']-df['Low']).rolling(14).mean().iloc[-1])

    if price_raw > float(df['SMA20'].iloc[-1]) > float(df['SMA50'].iloc[-1]) and rsi_val < 68 and change > 1:
        sig="🟢🟢 STRONG BUY"; strong=True; sl=price-atr*1.5; tp1=price+atr*1.5; tp2=price+atr*3.0
        e1,e2,e3 = price, sma20, sma50
    elif rsi_val < 30:
        sig="🔵🔵 STRONG BUY - OVERSOLD"; strong=True; sl=price-atr; tp1=price+atr*2; tp2=price+atr*3.5
        e1,e2,e3 = price, price-atr*0.5, price-atr
    elif price_raw < float(df['SMA20'].iloc[-1]) and change < -1:
        sig="🔴🔴 STRONG SELL"; strong=True; sl=price+atr*1.5; tp1=price-atr*1.5; tp2=price-atr*3
        e1,e2,e3 = price, sma20, sma50
    else:
        sig=f"⚪ WAIT - RSI {rsi_val:.1f}"; strong=False; sl=price-atr*1.5; tp1=price+atr*1.5; tp2=price+atr*2.5
        e1,e2,e3 = price, sma20, sma50

    rr1 = abs(tp1-price)/abs(price-sl) if price!=sl else 0
    msg = f"🚨 *{show} - SWING* 🚨\n\n💰 ${price:.2f} ({change:+.2f}%) ATR ${atr:.2f} RSI {rsi_val:.1f}\nSMA20 ${sma20:.2f} SMA50 ${sma50:.2f}\n\n🚀 {sig}\n\n📍 ENTRY 1: ${e1:.2f} MARKET\n📍 ENTRY 2: ${e2:.2f} LIMIT\n📍 ENTRY 3: ${e3:.2f} LIMIT\n\n🛑 SL: ${sl:.2f}\n🎯 TP1: ${tp1:.2f} 1:{rr1:.1f}\n🎯 TP2: ${tp2:.2f}"
    return msg, strong

def get_scalp(ticker):
    if ticker.upper() == "NVDIA": ticker = "NVDA"
    orig = ticker.upper()
    df = fetch_direct(ticker, "5d", "5m")
    if df.empty: df = fetch_direct(ticker, "1d", "5m")
    if df.empty:
        return f"❌ Scalp: No 5m data for {ticker}. Try /scalp NVDA", False
    
    price_raw = float(df['Close'].iloc[-1])
    price = price_raw - GC_TO_SPOT_OFFSET if orig == "GC=F" else price_raw
    show = "XAUUSD" if orig == "GC=F" else orig

    df['EMA9'] = df['Close'].ewm(span=9).mean()
    df['EMA21'] = df['Close'].ewm(span=21).mean()
    df['EMA50'] = df['Close'].ewm(span=50).mean()
    ema9_raw = float(df['EMA9'].iloc[-1])
    ema21_raw = float(df['EMA21'].iloc[-1])
    ema50_raw = float(df['EMA50'].iloc[-1])
    ema9 = ema9_raw - (GC_TO_SPOT_OFFSET if orig == "GC=F" else 0)
    ema21 = ema21_raw - (GC_TO_SPOT_OFFSET if orig == "GC=F" else 0)
    ema50 = ema50_raw - (GC_TO_SPOT_OFFSET if orig == "GC=F" else 0)

    delta = df['Close'].diff()
    gain = delta.where(delta>0,0).rolling(14).mean()
    loss = -delta.where(delta<0,0).rolling(14).mean()
    rsi = 100 - (100/(1+gain/loss))
    rsi_val = float(rsi.iloc[-1]) if not pd.isna(rsi.iloc[-1]) else 50
    atr = float((df['High']-df['Low']).rolling(14).mean().iloc[-1])
    change = float((price_raw - df['Close'].iloc[-2])/df['Close'].iloc[-2]*100)

    if ema9_raw > ema21_raw > ema50_raw and rsi_val > 45 and rsi_val < 70 and price_raw > ema9_raw:
        sig="🟢 SCALP BUY - EMA BULL"; strong=True; sl=price-atr*1.2; tp1=price+atr*1.0; tp2=price+atr*2.0
        e1,e2,e3 = price, ema9, ema21
    elif ema9_raw < ema21_raw < ema50_raw and rsi_val < 55 and price_raw < ema9_raw:
        sig="🔴 SCALP SELL - EMA BEAR"; strong=True; sl=price-atr*1.2; tp1=price-atr*1.0; tp2=price-atr*2.0
        e1,e2,e3 = price, ema9, ema21
    elif rsi_val < 28:
        sig="🔵 SCALP BUY - OVERSOLD 5M"; strong=True; sl=price-atr; tp1=price+atr*1.5; tp2=price+atr*2.5
        e1,e2,e3 = price, price-atr*0.5, price-atr
    elif rsi_val > 72:
        sig="🟠 SCALP SELL - OVERBOUGHT 5M"; strong=True; sl=price+atr; tp1=price-atr*1.5; tp2=price-atr*2.5
        e1,e2,e3 = price, price+atr*0.5, price+atr
    else:
        sig=f"⚪ SCALP WAIT - RSI {rsi_val:.1f}"; strong=False; sl=price-atr; tp1=price+atr; tp2=price+atr*2
        e1,e2,e3 = price, ema9, ema21

    rr = abs(tp1-price)/abs(price-sl) if price!=sl else 0
    msg = (
        f"⚡ *{show} - SCALP 5M* ⚡\n\n"
        f"💰 ${price:.2f} ({change:+.2f}%) RSI {rsi_val:.1f}\n"
        f"EMA9 ${ema9:.2f} EMA21 ${ema21:.2f} EMA50 ${ema50:.2f}\nATR ${atr:.2f}\n\n"
        f"🚀 {sig}\n\n"
        f"📍 ENTRY 1: ${e1:.2f} MARKET\n"
        f"📍 ENTRY 2: ${e2:.2f} LIMIT (EMA9) ⭐ MAIN\n"
        f"📍 ENTRY 3: ${e3:.2f} LIMIT (EMA21)\n\n"
        f"🛑 SL: ${sl:.2f}\n"
        f"🎯 TP1: ${tp1:.2f} 1:{rr:.1f}\n"
        f"🎯 TP2: ${tp2:.2f}\n\n"
        f"⏱️ Hold 5-60 min"
    )
    return msg, strong

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
        "DIRECT API - NO BLOCK + XAUUSD FIX ✅",
        parse_mode='Markdown'
    )

async def channel_post_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not update.channel_post: return
    if update.channel_post.chat_id == PRIVATE_CHANNEL_ID:
        try:
            await context.bot.copy_message(
                chat_id=PUBLIC_CHANNEL_ID,
                from_chat_id=PRIVATE_CHANNEL_ID,
                message_id=update.channel_post.message_id
            )
            print(f"✅ Forwarded Private {PRIVATE_CHANNEL_ID} -> Public {PUBLIC_CHANNEL_ID}")
        except Exception as e:
            print(f"❌ Forward fail: {e} - Make bot admin in both channels with Post permission")

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
    app.add_handler(MessageHandler(filters.UpdateType.CHANNEL_POST, channel_post_handler))
    print(f"Bot SCALP+SWING starting... Private {PRIVATE_CHANNEL_ID} -> Public {PUBLIC_CHANNEL_ID} Offset {GC_TO_SPOT_OFFSET}")
    app.run_polling(drop_pending_updates=True)

if __name__ == "__main__":
    main()
