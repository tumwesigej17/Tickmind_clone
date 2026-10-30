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
def home(): return "Tiker AI SWING+SCALP LIVE ✅"
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
            return None, "No 15m data for this ticker", False
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
        if price > ema9 > ema21 and rsi_val > 50 and rsi_val < 70:
            sig = "🟢 SCALP BUY - Momentum"
            sl = price - atr*1.0
            tp1 = price + atr*1.0
            tp2 = price + atr*2.0
            is_strong = True
        elif price < ema9 and ema9 < ema21 and rsi_val < 50:
            sig = "🔴 SCALP SELL - Momentum"
            sl = price + atr*1.0
            tp1 = price - atr*1.0
            tp2 = price - atr*2.0
            is_strong = True
        elif rsi_val < 25:
            sig = "🔵 SCALP BUY - Oversold Bounce"
            sl = price - atr*0.8
            tp1 = price + atr*1.2
            tp2 = price + atr*2.5
            is_strong = True
        elif rsi_val > 75:
            sig = "🟠 SCALP SELL - Overbought Fade"
            sl = price + atr*0.8
            tp1 = price - atr*1.2
            tp2 = price - atr*2.5
            is_strong = True
        else:
            sig = f"⚪ NO SCALP - RSI {rsi_val:.1f}"
            sl = price - atr
            tp1 = price + atr
            tp2 = price + atr*2
            is_strong = False
        msg = f"""⚡ *{ticker.upper()} - SCALP (15min)* ⚡

💰 Price: ${price:.2f} ({change:+.2f}%) | ATR15m: ${atr:.2f}
EMA9: ${ema9:.2f} EMA21: ${ema21:.2f}
RSI: {rsi_val:.1f}

🚀 {sig}

🛑 SL: ${sl:.2f} ({(sl-price)/price*100:+.2f}%)
🎯 TP1: ${tp1:.2f} ({(tp1-price)/price*100:+.2f}%)
🎯 TP2: ${tp2:.2f}

⏱️ Hold: 5-60 min | Scalp Mode
"""
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
            return None, "Ticker not found / Yahoo blocked", False
        if isinstance(df.columns, pd.MultiIndex):
            df.columns = df.columns.get_level_values(0)
        price = float(df['Close'].iloc[-1])
        prev = float(df['Close'].iloc[-2])
        change = (price - prev) / prev * 100
        vol = float(df['Volume'].iloc[-1])
        avg_vol = float(df['Volume'].rolling(20).mean().iloc[-1])
        vol_ratio = vol / avg_vol if avg_vol else 1
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
        rs = gain / loss
        rsi = 100 - (100 / (1 + rs))
        rsi_val = float(rsi.iloc[-1])
        df['MACD'] = df['EMA12'] - df['EMA26']
        df['MACD_Sig'] = df['MACD'].ewm(span=9).mean()
        macd = float(df['MACD'].iloc[-1])
        macd_sig = float(df['MACD_Sig'].iloc[-1])
        df['BB_Mid'] = df['Close'].rolling(20).mean()
        df['BB_Std'] = df['Close'].rolling(20).std()
        bb_upper = float(df['BB_Mid'].iloc[-1] + df['BB_Std'].iloc[-1]*2)
        bb_lower = float(df['BB_Mid'].iloc[-1] - df['BB_Std'].iloc[-1]*2)
        hl = df['High'] - df['Low']
        hc = (df['High'] - df['Close'].shift()).abs()
        lc = (df['Low'] - df['Close'].shift()).abs()
        tr = pd.concat([hl, hc, lc], axis=1).max(axis=1)
        atr = float(tr.rolling(14).mean().iloc[-1])
        support = float(df['Low'].rolling(20).min().iloc[-1])
        resistance = float(df['High'].rolling(20).max().iloc[-1])
        is_strong = False
        if price > sma20 > sma50 and rsi_val < 68 and macd > macd_sig and change > 1:
            sig = "🟢🟢 STRONG BUY"
            is_strong = True
            sl = price - atr*1.5
            tp1 = price + atr*1.5
            tp2 = price + atr*3
        elif rsi_val < 30:
            sig = "🔵🔵 STRONG BUY - OVERSOLD"
            is_strong = True
            sl = price - atr*1.0
            tp1 = price + atr*2.0
            tp2 = price + atr*3.5
        elif price < sma20 and sma20 < sma50 and change < -1:
            sig = "🔴🔴 STRONG SELL"
            is_strong = True
            sl = price + atr*1.5
            tp1 = price - atr*1.5
            tp2 = price - atr*3
        elif rsi_val > 75:
            sig = "🟠🟠 STRONG SELL - OVERBOUGHT"
            is_strong = True
            sl = price + atr*1.0
            tp1 = price - atr*2.0
            tp2 = price - atr*3.5
        else:
            sig = f"⚪ WAIT - RSI {rsi_val:.1f}"
            sl = price - atr*1.5
            tp1 = price + atr*1.5
            tp2 = price + atr*2.5
        risk = abs(price - sl)
        rr1 = abs(tp1 - price)/risk if risk else 0
        rr2 = abs(tp2 - price)/risk if risk else 0
        msg = f"""🚨 *{ticker.upper()} - FULL SWING* 🚨

*💰 PRICE*
Price: ${price:.2f} ({change:+.2f}%) ATR: ${atr:.2f}

*📊 VOLUME*
Vol: {vol:,.0f} Avg: {avg_vol:,.0f} Ratio: {vol_ratio:.2f}x

*📈 TREND*
SMA20: ${sma20:.2f} SMA50: ${sma50:.2f} SMA200: ${sma200:.2f}
Trend: {'🟢 Uptrend' if sma20>sma50 else '🔴 Downtrend'}

*📉 MOMENTUM*
RSI: {rsi_val:.1f} MACD: {macd:.3f} vs {macd_sig:.3f}
BB: ${bb_upper:.2f} / ${bb_lower:.2f}

*🎯 LEVELS*
Support: ${support:.2f} Resist: ${resistance:.2f}
52W: ${float(df['High'].max()):.2f} / ${float(df['Low'].min()):.2f}

*🚀 SIGNAL*
{sig} {'✅ STRONG' if is_strong else '❌ WEAK'}

🛑 SL: ${sl:.2f}
🎯 TP1: ${tp1:.2f} R:R 1:{rr1:.1f}
🎯 TP2: ${tp2:.2f} R:R 1:{rr2:.1f}

💡 Swing hold 1-5 days
"""
        return msg, None, is_strong
    except Exception as e:
        return None, str(e), False

async def strong_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not context.args:
        await update.message.reply_text("Use: /strong AAPL or /strong GC=F")
        return
    t = context.args[0].upper()
    await update.message.reply_text(f"⏳ SWING Analyzing {t}...")
    msg, err, strong = get_data(t)
    if err:
        await update.message.reply_text(f"❌ {err}")
    else:
        await update.message.reply_text(msg, parse_mode='Markdown')

async def scalp_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not context.args:
        await update.message.reply_text("Use: /scalp GC=F or /scalp XAUUSD=X")
        return
    t = context.args[0].upper()
    await update.message.reply_text(f"⚡ SCALP scanning {t} (15m)...")
    msg, err, strong = get_scalp_data(t)
    if err:
        await update.message.reply_text(f"❌ {err}")
    else:
        await update.message.reply_text(msg, parse_mode='Markdown')

async def scan_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    wl = ["AAPL", "GC=F", "BTC-USD", "NVDA"]
    await update.message.reply_text("🔎 Scanning SWING...")
    for t in wl:
        msg, err, strong = get_data(t)
        if strong and msg:
            await update.message.reply_text(msg, parse_mode='Markdown')

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("🚀 *SWING + SCALP LIVE!*\n\n/strong GC=F - Swing (daily)\n/scalp GC=F - Scalp (15min)\n/scan - Scan swing", parse_mode='Markdown')

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
    app.run_polling()
